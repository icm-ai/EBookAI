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


def test_book_ir_json_round_trip_preserves_provenance_and_patches():
    node = BookNode(
        id="node-1",
        type=NodeType.PARAGRAPH,
        content="第一段正文",
        source=[
            SourceRef(
                page_index=3,
                bbox=(10.0, 20.0, 300.0, 400.0),
                parser="pymupdf",
                source_id="abc123",
            )
        ],
        confidence=Confidence(
            extraction=0.99,
            structure=0.91,
            reading_order=0.95,
        ),
        attrs={"font": "Example"},
    )
    patch = Patch(
        id="patch-1",
        operation=PatchOperation.REPLACE_CONTENT,
        target_node_id=node.id,
        payload={"content": "第一段正文。"},
        reason="restore punctuation",
        confidence=0.88,
    )
    original = Book(
        metadata=BookMetadata(
            title="测试书",
            author="作者",
            language="zh-CN",
            identifier="urn:test:book",
        ),
        nodes=[node],
        patches=[patch],
    )

    restored = Book.from_json(original.to_json())

    assert restored.to_dict() == original.to_dict()
    assert restored.find_node("node-1") is not None
    assert restored.find_node("node-1").source[0].page_index == 3


def test_confidence_rejects_values_outside_unit_interval():
    try:
        Confidence(extraction=1.1)
    except ValueError as exc:
        assert "extraction confidence" in str(exc)
    else:
        raise AssertionError("Confidence accepted an invalid value")


def test_book_rejects_unknown_schema_version():
    payload = Book(metadata=BookMetadata()).to_dict()
    payload["schema_version"] = "99"

    try:
        Book.from_dict(payload)
    except ValueError as exc:
        assert "Unsupported BookIR schema version" in str(exc)
    else:
        raise AssertionError("Book accepted an unknown schema version")
