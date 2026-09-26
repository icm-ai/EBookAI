import zipfile
from pathlib import Path

from book.compiler.epub import EpubCompiler
from book.domain.models import Book, BookMetadata, BookNode, NodeType


def test_epub_compiler_writes_required_epub_structure(tmp_path: Path):
    book = Book(
        metadata=BookMetadata(
            title="Human Readable Book",
            author="EBookAI",
            language="en",
            identifier="urn:test:epub",
        ),
        nodes=[
            BookNode(
                id="heading-1",
                type=NodeType.HEADING,
                content="Introduction",
                attrs={"level": 2},
            ),
            BookNode(
                id="paragraph-1",
                type=NodeType.PARAGRAPH,
                content="A readable paragraph.",
            ),
        ],
    )

    output = EpubCompiler().compile(book, tmp_path / "book.epub")

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype").decode() == "application/epub+zip"
        assert "META-INF/container.xml" in names
        assert "EPUB/package.opf" in names
        assert "EPUB/nav.xhtml" in names
        assert "EPUB/text/section-1.xhtml" in names

        chapter = archive.read("EPUB/text/section-1.xhtml").decode()
        assert "Introduction" in chapter
        assert "A readable paragraph." in chapter


def test_epub_compiler_requires_epub_extension(tmp_path: Path):
    book = Book(metadata=BookMetadata(title="Book"))

    try:
        EpubCompiler().compile(book, tmp_path / "book.zip")
    except ValueError as exc:
        assert ".epub" in str(exc)
    else:
        raise AssertionError("Compiler accepted a non-EPUB output path")
