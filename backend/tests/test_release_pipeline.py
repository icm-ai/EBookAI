import json
import sys
import zipfile
from pathlib import Path

import pytest
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.publication import (
    EpubCheckMessage,
    EpubCheckResult,
    ExternalEpubCheckRunner,
    ReleasePipeline,
)
from book.quality import QualityReport


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
                content="A reproducible publication.",
                source=[
                    SourceRef(
                        page_index=0,
                        bbox=(10.0, 20.0, 300.0, 80.0),
                        parser="fixture",
                        source_id="fixture-source",
                    )
                ],
                confidence=Confidence(0.99, 0.99, 0.99),
            )
        ],
    )


def _quality_report():
    return QualityReport(
        issues=[],
        score=1.0,
        node_count=1,
    )


class StaticRunner:
    def __init__(self, result):
        self.result = result

    def run(self, epub_path):
        assert Path(epub_path).is_file()
        return self.result


def _passed_epubcheck():
    return EpubCheckResult(
        available=True,
        executed=True,
        valid=True,
        version="5.4.0",
        exit_code=0,
        counts={
            "fatal": 0,
            "error": 0,
            "warning": 0,
            "usage": 0,
            "info": 0,
        },
    )


def test_release_pipeline_is_byte_reproducible_and_self_verifying(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))

    first = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release-one",
        require_epubcheck=True,
    )
    second = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release-two",
        require_epubcheck=True,
    )

    assert first.manifest.release_ready is True
    assert first.manifest.release_id == second.manifest.release_id
    assert first.bundle_path.read_bytes() == second.bundle_path.read_bytes()
    assert pipeline.verify_bundle(first.bundle_path) == {
        "valid": True,
        "release_id": first.manifest.release_id,
        "errors": [],
    }

    with zipfile.ZipFile(first.bundle_path) as archive:
        assert {
            "manifest.json",
            "source/source.pdf",
            "book/bookir.json",
            "publication/book.epub",
            "reports/publication-qa.json",
            "reports/epubcheck.json",
        }.issubset(set(archive.namelist()))


def test_release_pipeline_detects_tampered_artifact(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(_passed_epubcheck()))
    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "release",
    )

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(result.bundle_path) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    entries["book/bookir.json"] += b"\n"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])

    verification = pipeline.verify_bundle(tampered)

    assert verification["valid"] is False
    assert "SHA-256 mismatch: book/bookir.json" in verification["errors"]


def test_required_unavailable_epubcheck_blocks_release(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    unavailable = EpubCheckResult(
        available=False,
        executed=False,
        valid=None,
        error="not installed",
    )
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(unavailable))

    optional = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "optional",
        require_epubcheck=False,
    )
    required = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "required",
        require_epubcheck=True,
    )

    assert optional.manifest.release_ready is True
    assert optional.manifest.epubcheck_status == "unavailable"
    assert required.manifest.release_ready is False


def test_available_but_failing_epubcheck_always_blocks_release(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    failed = EpubCheckResult(
        available=True,
        executed=True,
        valid=False,
        version="5.4.0",
        exit_code=1,
        counts={
            "fatal": 0,
            "error": 1,
            "warning": 0,
            "usage": 0,
            "info": 0,
        },
        messages=[
            EpubCheckMessage(
                id="RSC-001",
                severity="ERROR",
                message="Missing resource",
            )
        ],
    )
    pipeline = ReleasePipeline(epubcheck_runner=StaticRunner(failed))

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "failed",
        require_epubcheck=False,
    )

    assert result.manifest.release_ready is False
    assert result.manifest.epubcheck_status == "failed"


def test_external_epubcheck_runner_consumes_json_report(tmp_path):
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"fixture")
    script = tmp_path / "fake_epubcheck.py"
    script.write_text(
        """import json
print(json.dumps({
    "checker": {
        "checkerVersion": "5.4.0",
        "nFatal": 0,
        "nError": 0,
        "nWarning": 1,
        "nUsage": 0,
        "nInfo": 0
    },
    "messages": [{
        "ID": "ACC-001",
        "severity": "WARNING",
        "message": "Accessibility metadata recommended.",
        "locations": [{
            "path": "EPUB/package.opf",
            "line": 4,
            "column": 2,
            "context": None
        }]
    }]
}))
""",
        encoding="utf-8",
    )
    runner = ExternalEpubCheckRunner(command=[sys.executable, str(script)])

    result = runner.run(epub)

    assert result.status == "passed"
    assert result.valid is True
    assert result.version == "5.4.0"
    assert result.counts["warning"] == 1
    assert result.messages[0].id == "ACC-001"
    assert result.messages[0].locations[0]["path"] == "EPUB/package.opf"


@pytest.mark.skipif(
    ExternalEpubCheckRunner().resolve_command() is None,
    reason="External EPUBCheck runtime is not installed",
)
def test_real_epubcheck_accepts_compiler_release_epub(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfixture\n")
    pipeline = ReleasePipeline()

    result = pipeline.build(
        source_path=source,
        source_filename="fixture.pdf",
        book=_book(),
        quality_report=_quality_report(),
        issue_resolutions={},
        output_dir=tmp_path / "real",
        require_epubcheck=True,
    )

    assert result.epubcheck_result.available is True
    assert result.epubcheck_result.executed is True
    assert result.epubcheck_result.valid is True, json.dumps(
        result.epubcheck_result.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    assert result.manifest.release_ready is True
