from pathlib import Path

from book.domain.models import NodeType
from book.parsers import (
    MarkerAdapter,
    MinerUAdapter,
    ParserRegistry,
    PyMuPDFAdapter,
)


def _assert_conformant(book, parser_name):
    assert book.schema_version == "0.1"
    assert book.metadata.extra["parser"] == parser_name
    assert book.metadata.extra["parser_profile"]["name"] == parser_name

    ids = [node.id for node in book.walk()]
    assert len(ids) == len(set(ids))
    for node in book.walk():
        assert node.id
        if node.content or node.type in {
            NodeType.TABLE,
            NodeType.FIGURE,
            NodeType.FORMULA,
        }:
            assert node.source
            assert all(source.parser == parser_name for source in node.source)


def test_parser_capabilities_distinguish_native_and_semantic_backends():
    native = PyMuPDFAdapter()
    mineru = MinerUAdapter()
    marker = MarkerAdapter()

    assert native.capabilities.supports("native_text", "bbox")
    assert not native.capabilities.ocr
    assert mineru.capabilities.supports("ocr", "tables", "formulas", "footnotes")
    assert marker.capabilities.supports("ocr", "layout", "multi_column")


def test_registry_filters_by_format_and_required_capabilities():
    registry = ParserRegistry([PyMuPDFAdapter(), MinerUAdapter(), MarkerAdapter()])

    candidates = registry.candidates(
        Path("book.pdf"),
        required_features=("ocr", "tables"),
        available_only=False,
    )

    assert [adapter.name for adapter in candidates] == ["mineru", "marker"]


def test_mineru_structured_content_normalizes_to_semantic_bookir():
    payload = {
        "pages": [
            {
                "page_idx": 0,
                "blocks": [
                    {
                        "type": "doc_title",
                        "level": 1,
                        "content": "A Semantic Book",
                        "bbox": [0.1, 0.05, 0.9, 0.12],
                    },
                    {
                        "type": "text",
                        "content": "First paragraph.",
                        "bbox": [0.1, 0.2, 0.9, 0.3],
                    },
                    {
                        "type": "table",
                        "content": "| A | B |",
                        "bbox": [0.1, 0.4, 0.9, 0.6],
                        "captions": [
                            {
                                "bbox": [0.1, 0.37, 0.5, 0.39],
                                "content": "Table 1",
                            }
                        ],
                    },
                    {
                        "type": "page_footnote",
                        "content": "[1] Footnote",
                        "bbox": [0.1, 0.9, 0.9, 0.95],
                    },
                ],
            }
        ],
        "file_suffix": "pdf",
        "effort": "standard",
        "parse_mode": "ocr",
        "mineru_version": "4.0",
    }
    adapter = MinerUAdapter()

    first = adapter.from_structured_content(
        payload,
        Path("fixture.pdf"),
        source_id="fixture-source",
    )
    second = adapter.from_structured_content(
        payload,
        Path("fixture.pdf"),
        source_id="fixture-source",
    )

    _assert_conformant(first, "mineru")
    assert first.metadata.title == "A Semantic Book"
    assert [node.type for node in first.nodes] == [
        NodeType.HEADING,
        NodeType.PARAGRAPH,
        NodeType.TABLE,
        NodeType.FOOTNOTE,
    ]
    assert first.nodes[0].attrs["level"] == 1
    assert first.nodes[2].children[0].type == NodeType.CAPTION
    assert first.nodes[2].source[0].bbox == (0.1, 0.4, 0.9, 0.6)
    assert [node.id for node in first.walk()] == [node.id for node in second.walk()]


def test_marker_json_normalizes_page_block_tree_to_bookir():
    payload = {
        "block_type": "Document",
        "metadata": {"table_of_contents": []},
        "children": [
            {
                "id": "/page/0/Page/0",
                "block_type": "Page",
                "polygon": [[0, 0], [612, 0], [612, 792], [0, 792]],
                "children": [
                    {
                        "id": "/page/0/SectionHeader/0",
                        "block_type": "SectionHeader",
                        "html": "<h1>Introduction</h1>",
                        "polygon": [[50, 60], [500, 60], [500, 100], [50, 100]],
                        "children": None,
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                    {
                        "id": "/page/0/Text/1",
                        "block_type": "Text",
                        "html": "<p>Hello <b>BookIR</b>.</p>",
                        "polygon": [[50, 120], [500, 120], [500, 200], [50, 200]],
                        "children": None,
                    },
                    {
                        "id": "/page/0/Table/2",
                        "block_type": "Table",
                        "html": "<table><tr><td>A</td><td>B</td></tr></table>",
                        "polygon": [[50, 250], [500, 250], [500, 400], [50, 400]],
                        "children": [
                            {
                                "id": "/page/0/Caption/3",
                                "block_type": "Caption",
                                "html": "<p>Table 1</p>",
                                "polygon": [
                                    [50, 410],
                                    [300, 410],
                                    [300, 430],
                                    [50, 430],
                                ],
                                "children": None,
                            }
                        ],
                    },
                    {
                        "id": "/page/0/Footnote/4",
                        "block_type": "Footnote",
                        "html": "<p>[1] A note.</p>",
                        "polygon": [[50, 700], [500, 700], [500, 740], [50, 740]],
                        "children": None,
                    },
                ],
            }
        ],
    }
    adapter = MarkerAdapter(mode="fast")

    first = adapter.from_json_output(
        payload,
        Path("fixture.pdf"),
        source_id="fixture-source",
    )
    second = adapter.from_json_output(
        payload,
        Path("fixture.pdf"),
        source_id="fixture-source",
    )

    _assert_conformant(first, "marker")
    assert first.metadata.title == "Introduction"
    assert [node.type for node in first.nodes] == [
        NodeType.HEADING,
        NodeType.PARAGRAPH,
        NodeType.TABLE,
        NodeType.FOOTNOTE,
    ]
    assert first.nodes[0].attrs["level"] == 1
    assert first.nodes[1].content == "Hello BookIR ."
    assert first.nodes[2].children[0].type == NodeType.CAPTION
    assert first.nodes[2].source[0].bbox == (50.0, 250.0, 500.0, 400.0)
    assert [node.id for node in first.walk()] == [
        node.id for node in second.walk()
    ]


def test_parser_profiles_do_not_require_optional_backend_imports():
    profiles = ParserRegistry(
        [PyMuPDFAdapter(), MinerUAdapter(), MarkerAdapter()]
    ).profiles()

    names = [profile["name"] for profile in profiles]
    assert names == ["marker", "mineru", "pymupdf"]
    for profile in profiles:
        assert "available" in profile
        assert "capabilities" in profile
        assert "supported_extensions" in profile
