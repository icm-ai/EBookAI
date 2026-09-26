from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.reconstruction import (
    FootnoteAssociationPass,
    HeaderFooterRemovalPass,
    HeadingInferencePass,
    ParagraphMergePass,
    ReconstructionPipeline,
)


def _node(
    node_id,
    text,
    *,
    page,
    bbox,
    size=11.0,
    font="Times-Roman",
    page_height=1000.0,
):
    return BookNode(
        id=node_id,
        type=NodeType.TEXT_BLOCK,
        content=text,
        source=[
            SourceRef(
                page_index=page,
                bbox=bbox,
                parser="fixture",
                source_id="fixture-source",
            )
        ],
        confidence=Confidence(
            extraction=1.0,
            structure=0.25,
            reading_order=0.9,
        ),
        attrs={
            "page_height": page_height,
            "page_width": 700.0,
            "spans": [
                {
                    "text": text,
                    "bbox": list(bbox),
                    "font": font,
                    "size": size,
                    "flags": 0,
                }
            ],
        },
    )


def _book(nodes, page_count=4):
    return Book(
        metadata=BookMetadata(
            title="Fixture",
            language="en",
            extra={"page_count": page_count},
        ),
        nodes=nodes,
    )


def test_header_footer_removal_uses_repetition_and_keeps_audit_copy():
    nodes = []
    for page in range(4):
        nodes.extend(
            [
                _node(
                    f"header-{page}",
                    "Running Title",
                    page=page,
                    bbox=(50, 20, 300, 55),
                    size=9,
                ),
                _node(
                    f"body-{page}",
                    f"Body page {page}",
                    page=page,
                    bbox=(50, 200, 650, 700),
                ),
                _node(
                    f"footer-{page}",
                    str(page + 1),
                    page=page,
                    bbox=(330, 950, 370, 980),
                    size=9,
                ),
            ]
        )

    result = HeaderFooterRemovalPass().apply(_book(nodes))

    assert [node.id for node in result.nodes] == [
        "body-0",
        "body-1",
        "body-2",
        "body-3",
    ]
    suppressed = result.metadata.extra["reconstruction"]["suppressed_nodes"]
    assert len(suppressed) == 8
    assert {item["source"][0]["page_index"] for item in suppressed} == {
        0,
        1,
        2,
        3,
    }


def test_paragraph_merge_joins_cross_page_hyphenation_and_sources():
    first = _node(
        "p1",
        "This paragraph con-",
        page=0,
        bbox=(60, 760, 640, 950),
    )
    second = _node(
        "p2",
        "tinues on the next page.",
        page=1,
        bbox=(60, 50, 640, 220),
    )

    result = ParagraphMergePass().apply(_book([first, second], page_count=2))

    assert len(result.nodes) == 1
    paragraph = result.nodes[0]
    assert paragraph.type == NodeType.PARAGRAPH
    assert paragraph.content == "This paragraph continues on the next page."
    assert [source.page_index for source in paragraph.source] == [0, 1]
    assert paragraph.attrs["merged_from"] == ["p1", "p2"]


def test_paragraph_merge_does_not_cross_a_completed_sentence():
    first = _node(
        "p1",
        "This paragraph is complete.",
        page=0,
        bbox=(60, 760, 640, 950),
    )
    second = _node(
        "p2",
        "A new paragraph starts here.",
        page=1,
        bbox=(60, 50, 640, 220),
    )

    result = ParagraphMergePass().apply(_book([first, second], page_count=2))

    assert len(result.nodes) == 2
    assert all(node.type == NodeType.PARAGRAPH for node in result.nodes)


def test_paragraph_merge_concatenates_cjk_without_inserting_space():
    first = _node(
        "p1",
        "这是跨页的",
        page=0,
        bbox=(60, 760, 640, 950),
    )
    second = _node(
        "p2",
        "一个完整段落",
        page=1,
        bbox=(60, 50, 640, 220),
    )

    result = ParagraphMergePass().apply(_book([first, second], page_count=2))

    assert result.nodes[0].content == "这是跨页的一个完整段落"


def test_heading_inference_uses_typography_and_chapter_patterns():
    heading = _node(
        "h1",
        "Chapter 1",
        page=0,
        bbox=(60, 180, 640, 230),
        size=18,
        font="Times-Bold",
    )
    body = _node(
        "p1",
        "Normal body copy.",
        page=0,
        bbox=(60, 260, 640, 500),
        size=11,
    )

    result = HeadingInferencePass().apply(_book([heading, body], page_count=1))

    assert result.nodes[0].type == NodeType.HEADING
    assert result.nodes[0].attrs["level"] == 1
    assert result.nodes[0].attrs["inferred_heading"] is True
    assert result.nodes[1].type == NodeType.TEXT_BLOCK


def test_footnote_association_marks_definition_and_reference():
    body = _node(
        "body",
        "Claim with a source[1]",
        page=0,
        bbox=(60, 200, 640, 650),
        size=11,
    )
    footnote = _node(
        "note",
        "[1] Supporting note.",
        page=0,
        bbox=(60, 820, 640, 900),
        size=8,
    )

    result = FootnoteAssociationPass().apply(_book([body, footnote], page_count=1))

    assert result.nodes[1].type == NodeType.FOOTNOTE
    assert result.nodes[1].attrs["marker"] == "[1]"
    assert result.nodes[1].attrs["reference_node_ids"] == ["body"]


def test_default_pipeline_preserves_source_provenance():
    heading = _node(
        "heading",
        "Chapter 1",
        page=0,
        bbox=(60, 180, 640, 230),
        size=18,
        font="Times-Bold",
    )
    first = _node(
        "first",
        "A long para-",
        page=0,
        bbox=(60, 760, 640, 950),
        size=11,
    )
    second = _node(
        "second",
        "graph continues.",
        page=1,
        bbox=(60, 50, 640, 220),
        size=11,
    )

    result = ReconstructionPipeline().run(_book([heading, first, second], page_count=2))

    assert result.nodes[0].type == NodeType.HEADING
    assert result.nodes[1].type == NodeType.PARAGRAPH
    assert result.nodes[1].content == "A long paragraph continues."
    assert [source.page_index for source in result.nodes[1].source] == [0, 1]
