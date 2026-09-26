import pytest

from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    Patch,
    PatchOperation,
    SourceRef,
)
from book.repair import PatchEngine, PatchValidationError


def _source(page):
    return SourceRef(
        page_index=page,
        bbox=(10.0, 20.0, 300.0, 400.0),
        parser="fixture",
        source_id="fixture-source",
    )


def _book():
    return Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="a",
                type=NodeType.PARAGRAPH,
                content="Alpha",
                source=[_source(0)],
                confidence=Confidence(0.9, 0.8, 0.9),
                attrs={"kind": "body"},
            ),
            BookNode(
                id="b",
                type=NodeType.PARAGRAPH,
                content="Beta",
                source=[_source(1)],
                confidence=Confidence(0.8, 0.7, 0.8),
            ),
            BookNode(
                id="parent",
                type=NodeType.SECTION,
                content="Section",
                children=[
                    BookNode(
                        id="child",
                        type=NodeType.PARAGRAPH,
                        content="Child",
                        source=[_source(2)],
                    )
                ],
            ),
        ],
    )


def test_replace_content_is_audited_and_does_not_mutate_input():
    original = _book()
    patch = Patch(
        id="replace",
        operation=PatchOperation.REPLACE_CONTENT,
        target_node_id="a",
        payload={"content": "Revised"},
        reason="Fix OCR",
        confidence=0.95,
    )

    result = PatchEngine().apply(original, patch)

    assert original.find_node("a").content == "Alpha"
    assert result.find_node("a").content == "Revised"
    assert result.find_node("a").source == original.find_node("a").source
    assert result.patches[0].applied is True
    assert result.patches[0].payload["_audit"]["before_content"] == "Alpha"


def test_set_attribute_replaces_existing_proposal_with_applied_patch():
    proposal = Patch(
        id="heading-fix",
        operation=PatchOperation.SET_ATTRIBUTE,
        target_node_id="a",
        payload={"key": "level", "value": 2},
        applied=False,
    )
    book = _book()
    book.patches.append(proposal)

    result = PatchEngine().apply(book, proposal)

    assert result.find_node("a").attrs["level"] == 2
    assert len(result.patches) == 1
    assert result.patches[0].applied is True
    assert result.patches[0].payload["_audit"]["attribute_existed"] is False


def test_delete_node_records_full_before_snapshot():
    patch = Patch(
        id="delete",
        operation=PatchOperation.DELETE_NODE,
        target_node_id="child",
    )

    result = PatchEngine().apply(_book(), patch)

    assert result.find_node("child") is None
    audit = result.patches[0].payload["_audit"]
    assert audit["before_node"]["id"] == "child"
    assert audit["parent_id"] == "parent"


def test_insert_node_supports_child_position():
    inserted = BookNode(
        id="new-child",
        type=NodeType.PARAGRAPH,
        content="Inserted",
        source=[_source(3)],
    )
    patch = Patch(
        id="insert",
        operation=PatchOperation.INSERT_NODE,
        target_node_id="parent",
        payload={"position": "child", "node": inserted.to_dict()},
    )

    result = PatchEngine().apply(_book(), patch)

    assert [node.id for node in result.find_node("parent").children] == [
        "child",
        "new-child",
    ]


def test_move_node_prevents_descendant_cycles_and_supports_root_move():
    invalid = Patch(
        id="bad-move",
        operation=PatchOperation.MOVE_NODE,
        target_node_id="parent",
        payload={"parent_id": "child", "index": 0},
    )
    with pytest.raises(PatchValidationError):
        PatchEngine().apply(_book(), invalid)

    valid = Patch(
        id="move",
        operation=PatchOperation.MOVE_NODE,
        target_node_id="child",
        payload={"parent_id": None, "index": 1},
    )
    result = PatchEngine().apply(_book(), valid)

    assert [node.id for node in result.nodes] == ["a", "child", "b", "parent"]
    assert result.find_node("parent").children == []


def test_merge_nodes_preserves_all_source_provenance():
    patch = Patch(
        id="merge",
        operation=PatchOperation.MERGE_NODES,
        target_node_id="a",
        payload={"node_ids": ["a", "b"], "content": "Alpha Beta"},
    )

    result = PatchEngine().apply(_book(), patch)

    assert [node.id for node in result.nodes] == ["a", "parent"]
    merged = result.find_node("a")
    assert merged.content == "Alpha Beta"
    assert [source.page_index for source in merged.source] == [0, 1]
    assert merged.attrs["merged_from"] == ["a", "b"]
    assert result.patches[0].payload["_audit"]["before_nodes"][1]["id"] == "b"


def test_merge_nodes_rejects_non_contiguous_siblings():
    book = _book()
    patch = Patch(
        id="bad-merge",
        operation=PatchOperation.MERGE_NODES,
        target_node_id="a",
        payload={"node_ids": ["a", "parent"]},
    )

    with pytest.raises(PatchValidationError, match="contiguous"):
        PatchEngine().apply(book, patch)


def test_split_node_creates_stable_siblings_and_keeps_provenance():
    patch = Patch(
        id="split",
        operation=PatchOperation.SPLIT_NODE,
        target_node_id="a",
        payload={"parts": ["Alpha one", "Alpha two"]},
    )
    engine = PatchEngine()

    first = engine.apply(_book(), patch)
    second = engine.apply(_book(), patch)

    assert first.nodes[0].id == "a"
    assert first.nodes[1].id == second.nodes[1].id
    assert first.nodes[0].content == "Alpha one"
    assert first.nodes[1].content == "Alpha two"
    assert first.nodes[1].source[0].page_index == 0
    assert first.nodes[1].attrs["split_from"] == "a"


def test_apply_many_is_atomic_with_respect_to_input_book():
    original = _book()
    patches = [
        Patch(
            id="good",
            operation=PatchOperation.REPLACE_CONTENT,
            target_node_id="a",
            payload={"content": "Changed"},
        ),
        Patch(
            id="bad",
            operation=PatchOperation.REPLACE_CONTENT,
            target_node_id="missing",
            payload={"content": "Never"},
        ),
    ]

    with pytest.raises(PatchValidationError):
        PatchEngine().apply_many(original, patches)

    assert original.find_node("a").content == "Alpha"


def test_applied_patch_cannot_be_reapplied():
    patch = Patch(
        id="once",
        operation=PatchOperation.REPLACE_CONTENT,
        target_node_id="a",
        payload={"content": "Once"},
    )
    once = PatchEngine().apply(_book(), patch)

    with pytest.raises(PatchValidationError, match="already applied"):
        PatchEngine().apply(once, patch)
