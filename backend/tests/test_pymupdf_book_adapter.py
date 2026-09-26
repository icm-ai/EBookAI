from pathlib import Path

import fitz
from book.domain.models import NodeType
from book.parsers.pymupdf import PyMuPDFAdapter


def test_pymupdf_adapter_preserves_source_location_and_font(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    document = fitz.open()
    page = document.new_page(width=400, height=500)
    page.insert_text(
        (72, 100),
        "Hello BookIR",
        fontsize=14,
        fontname="helv",
    )
    document.set_metadata({"title": "Fixture Book", "author": "EBookAI"})
    document.save(str(pdf_path))
    document.close()

    book = PyMuPDFAdapter().parse(pdf_path)

    assert book.metadata.title == "Fixture Book"
    assert book.metadata.author == "EBookAI"
    assert book.metadata.extra["parser"] == "pymupdf"
    assert len(book.nodes) == 1

    node = book.nodes[0]
    assert node.type == NodeType.TEXT_BLOCK
    assert "Hello BookIR" in node.content
    assert len(node.source) == 1
    assert node.source[0].page_index == 0
    assert node.source[0].parser == "pymupdf"
    assert node.source[0].bbox is not None
    assert len(node.attrs["spans"]) == 1
    assert node.attrs["spans"][0]["font"]
    assert node.confidence.extraction == 1.0


def test_pymupdf_adapter_uses_stable_node_ids(tmp_path: Path):
    pdf_path = tmp_path / "stable.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Stable")
    document.save(str(pdf_path))
    document.close()

    adapter = PyMuPDFAdapter()

    first = adapter.parse(pdf_path)
    second = adapter.parse(pdf_path)

    assert [node.id for node in first.nodes] == [node.id for node in second.nodes]
