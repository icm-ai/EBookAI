import zipfile
from pathlib import Path

import pytest

from book.compiler import EpubCompiler, TypographyProfile
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


def test_epub_compiler_is_byte_reproducible_without_explicit_identifier(tmp_path: Path):
    book = Book(
        metadata=BookMetadata(
            title="Deterministic Book",
            author="EBookAI",
            language="en",
        ),
        nodes=[
            BookNode(
                id="paragraph-1",
                type=NodeType.PARAGRAPH,
                content="Stable output.",
            )
        ],
    )

    first = EpubCompiler().compile(book, tmp_path / "first.epub")
    second = EpubCompiler().compile(book, tmp_path / "second.epub")

    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("profile", "percent"),
    [
        (TypographyProfile.COMPACT, 85),
        ("extra-compact", 75),
    ],
)
def test_epub_typography_profile_only_changes_css(
    tmp_path: Path,
    profile: TypographyProfile | str,
    percent: int,
):
    book = Book(
        metadata=BookMetadata(title="Profile Test", language="en"),
        nodes=[
            BookNode(
                id="paragraph",
                type=NodeType.PARAGRAPH,
                content="Reader-adjustable text.",
            )
        ],
    )
    default = EpubCompiler().compile(book, tmp_path / "default.epub")
    compact = EpubCompiler().compile(
        book, tmp_path / "compact.epub", typography_profile=profile
    )

    with zipfile.ZipFile(default) as normal, zipfile.ZipFile(compact) as adjusted:
        assert normal.testzip() is None
        assert adjusted.testzip() is None
        assert normal.namelist() == adjusted.namelist()
        assert normal.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert adjusted.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        for name in normal.namelist():
            if name == "EPUB/styles/book.css":
                continue
            assert normal.read(name) == adjusted.read(name)

        base_css = normal.read("EPUB/styles/book.css").decode("utf-8")
        css = adjusted.read("EPUB/styles/book.css").decode("utf-8")
        assert "font-size:" not in base_css
        assert f"font-size: {percent}%;" in css
        assert css.startswith(base_css)
        assert "!important" not in css
        assert "font-size: 12px" not in css


def test_epub_default_typography_profile_preserves_original_bytes(tmp_path: Path):
    book = Book(
        metadata=BookMetadata(title="Backward-compatible"),
        nodes=[],
    )
    implicit = EpubCompiler().compile(book, tmp_path / "implicit.epub")
    explicit = EpubCompiler().compile(
        book,
        tmp_path / "explicit.epub",
        typography_profile=TypographyProfile.READER_DEFAULT,
    )
    assert implicit.read_bytes() == explicit.read_bytes()


@pytest.mark.parametrize("invalid_profile", ["large", "85%", "", None])
def test_epub_rejects_unknown_typography_profile_before_writing(
    tmp_path: Path, invalid_profile: str | None
):
    target = tmp_path / "invalid.epub"
    with pytest.raises(ValueError, match="Unsupported EPUB typography profile"):
        EpubCompiler().compile(
            Book(metadata=BookMetadata(title="Invalid")),
            target,
            typography_profile=invalid_profile,
        )
    assert not target.exists()


@pytest.mark.parametrize(
    "profile",
    [TypographyProfile.COMPACT, TypographyProfile.EXTRA_COMPACT],
)
def test_epub_typography_profile_builds_are_reproducible(
    tmp_path: Path, profile: TypographyProfile
):
    book = Book(
        metadata=BookMetadata(title="Reproducible", language="zh-Hans"),
        nodes=[BookNode(id="text", type=NodeType.PARAGRAPH, content="可调整字号")],
    )
    first = EpubCompiler().compile(
        book, tmp_path / "first.epub", typography_profile=profile
    )
    second = EpubCompiler().compile(
        book, tmp_path / "second.epub", typography_profile=profile
    )
    assert first.read_bytes() == second.read_bytes()
