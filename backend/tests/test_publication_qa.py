import zipfile

from book.compiler import EpubCompiler
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.publication import PublicationQAEngine, PublicationSeverity
from book.quality import IssueSeverity, QualityIssue, QualityReport


def _source():
    return SourceRef(
        page_index=0,
        bbox=(10.0, 20.0, 300.0, 80.0),
        parser="fixture",
        source_id="fixture-source",
    )


def _book():
    return Book(
        metadata=BookMetadata(
            title="Release Fixture",
            author="EBookAI",
            language="en",
        ),
        nodes=[
            BookNode(
                id="p1",
                type=NodeType.PARAGRAPH,
                content="Ready for publication.",
                source=[_source()],
                confidence=Confidence(0.99, 0.99, 0.99),
            )
        ],
    )


def _report(issue=None):
    issues = [issue] if issue is not None else []
    return QualityReport(
        issues=issues,
        score=1.0 if not issues else 0.9,
        node_count=1,
    )


def test_valid_compiled_epub_is_release_ready(tmp_path):
    book = _book()
    epub_path = tmp_path / "book.epub"
    EpubCompiler().compile(book, epub_path)

    report = PublicationQAEngine().analyze(
        book,
        _report(),
        issue_resolutions={},
        epub_path=epub_path,
    )

    assert report.release_ready is True
    assert report.epub_checked is True
    assert report.counts["error"] == 0


def test_open_review_issue_blocks_release_but_explicit_waiver_does_not(tmp_path):
    book = _book()
    epub_path = tmp_path / "book.epub"
    EpubCompiler().compile(book, epub_path)
    issue = QualityIssue(
        id="review-issue",
        code="needs_review",
        severity=IssueSeverity.REVIEW,
        message="Reviewer must inspect this node.",
        node_ids=("p1",),
    )
    engine = PublicationQAEngine()

    open_report = engine.analyze(
        book,
        _report(issue),
        issue_resolutions={"review-issue": "open"},
        epub_path=epub_path,
    )
    waived_report = engine.analyze(
        book,
        _report(issue),
        issue_resolutions={"review-issue": "waived"},
        epub_path=epub_path,
    )

    assert open_report.release_ready is False
    assert any(
        finding.code == "unresolved_review_issue"
        and finding.severity == PublicationSeverity.ERROR
        for finding in open_report.findings
    )
    assert waived_report.release_ready is True
    assert any(
        finding.code == "waived_review_issue"
        and finding.severity == PublicationSeverity.WARNING
        for finding in waived_report.findings
    )


def test_error_issue_remains_blocking_even_if_human_rejected_it(tmp_path):
    book = _book()
    epub_path = tmp_path / "book.epub"
    EpubCompiler().compile(book, epub_path)
    issue = QualityIssue(
        id="error-issue",
        code="missing_provenance",
        severity=IssueSeverity.ERROR,
        message="Source provenance is missing.",
        node_ids=("p1",),
    )

    report = PublicationQAEngine().analyze(
        book,
        _report(issue),
        issue_resolutions={"error-issue": "waived"},
        epub_path=epub_path,
    )

    assert report.release_ready is False
    assert any(
        finding.code == "blocking_quality_error"
        for finding in report.findings
    )


def test_epub_missing_required_file_fails_structural_qa(tmp_path):
    epub_path = tmp_path / "broken.epub"
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/package.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        archive.writestr(
            "EPUB/package.opf",
            """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <manifest></manifest><spine></spine>
</package>""",
        )

    report = PublicationQAEngine().analyze(
        _book(),
        _report(),
        epub_path=epub_path,
    )

    assert report.release_ready is False
    assert any(
        finding.code == "epub_required_files"
        and "EPUB/nav.xhtml" in finding.evidence["missing"]
        for finding in report.findings
    )
