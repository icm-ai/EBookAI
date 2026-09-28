import base64
import hashlib
import json
import time
from pathlib import Path

from book.benchmark import CorpusStore, ParserBenchmarkRunner, render_markdown
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.parsers import ParserCapabilities, ParserRegistry
from book.parsers.base import BookParserAdapter, ParserBackendError


class FakeSuccessAdapter(BookParserAdapter):
    name = "fake-success"
    supported_extensions = frozenset({".pdf"})
    capabilities = ParserCapabilities(
        native_text=True,
        reading_order=True,
        headings=True,
        bbox=True,
        semantic_output=True,
    )

    def parse(self, path: Path) -> Book:
        source = SourceRef(
            page_index=0,
            bbox=(10.0, 10.0, 200.0, 30.0),
            parser=self.name,
            source_id="fake-source",
        )
        return Book(
            metadata=BookMetadata(
                title="Fixture",
                source_path=str(path),
                extra={
                    "page_count": 1,
                    "parser": self.name,
                    "parser_profile": self.profile(),
                },
            ),
            nodes=[
                BookNode(
                    id="heading",
                    type=NodeType.HEADING,
                    content="Heading",
                    source=[source],
                    confidence=Confidence(1.0, 0.95, 0.95),
                    attrs={"level": 1},
                ),
                BookNode(
                    id="paragraph",
                    type=NodeType.PARAGRAPH,
                    content="A real parser result surrogate.",
                    source=[source],
                    confidence=Confidence(1.0, 0.95, 0.95),
                ),
            ],
        )


class FakeUnavailableAdapter(BookParserAdapter):
    name = "fake-unavailable"
    supported_extensions = frozenset({".pdf"})

    def is_available(self) -> bool:
        return False

    def parse(self, path: Path) -> Book:
        raise AssertionError("unavailable adapter must never be invoked")


class FakeFailureAdapter(BookParserAdapter):
    name = "fake-failure"
    supported_extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> Book:
        raise ParserBackendError("intentional parser failure")


class FakeSlowAdapter(BookParserAdapter):
    name = "fake-slow"
    supported_extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> Book:
        time.sleep(2.0)
        raise AssertionError("timeout should terminate this worker")


def _store(tmp_path: Path) -> CorpusStore:
    raw = b"%PDF-1.4\nbenchmark-runner-fixture\n"
    asset = tmp_path / "fixture.pdf.b64"
    asset.write_bytes(base64.b64encode(raw))
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "document_id": "fixture",
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "status": "reviewed",
                "annotated_by": "Fixture Annotator",
                "reviewed_by": "Fixture Reviewer",
                "pages": [
                    {
                        "page_index": 0,
                        "tasks": ["headings"],
                        "elements": [
                            {
                                "id": "heading",
                                "type": "heading",
                                "text": "Heading",
                                "level": 1,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "runner-test",
                "documents": [
                    {
                        "id": "fixture",
                        "title": "Runner fixture",
                        "source_url": "https://example.invalid/fixture.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "Test-only bytes are explicitly redistributable.",
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "document_class": "test",
                        "language": "en",
                        "page_count": 1,
                        "expected_capabilities": ["headings"],
                        "redistributable": True,
                        "embedded_base64_path": asset.name,
                        "gold_annotations_path": gold_path.name,
                        "gold_thresholds": {
                            "fake-success": {
                                "structures.headings.f1_min": 1.0
                            }
                        },
                        "gold_baselines": {
                            "fake-success": {
                                "structures.headings.f1": 1.0
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return CorpusStore(manifest_path, tmp_path / "cache")


def test_runner_records_success_skip_failure_and_report(tmp_path):
    store = _store(tmp_path)
    registry = ParserRegistry(
        [FakeSuccessAdapter(), FakeUnavailableAdapter(), FakeFailureAdapter()]
    )
    runner = ParserBenchmarkRunner(store, tmp_path / "output", registry=registry)

    report = runner.run(
        document_ids=["fixture"],
        backends=["fake-success", "fake-unavailable", "fake-failure"],
        timeout=5.0,
    )

    statuses = {run.backend: run.status for run in report.runs}
    assert statuses == {
        "fake-success": "success",
        "fake-unavailable": "skipped",
        "fake-failure": "failed",
    }

    success = next(run for run in report.runs if run.backend == "fake-success")
    assert success.metrics["page_coverage"] == 1.0
    assert success.metrics["expected_structure_recovery"] == 1.0
    assert success.metrics["relative_text_coverage"] == 1.0
    assert success.metrics["text_consensus_jaccard_mean"] is None
    assert success.gold_metrics["structures"]["headings"]["f1"] == 1.0
    assert success.gold_metrics["baseline_deltas"] == {
        "structures.headings.f1": 0.0
    }
    assert success.gold_gate_failures == []
    assert Path(success.bookir_path).is_file()
    assert (
        tmp_path
        / "output"
        / "fixture"
        / "fake-success"
        / "gold-evidence.json"
    ).is_file()
    assert (tmp_path / "output" / "benchmark-results.json").is_file()

    markdown = render_markdown(report)
    assert "Proxy metrics and Gold Accuracy" in markdown
    assert "### Gold Accuracy" in markdown
    assert "fake-unavailable" in markdown
    assert "intentional parser failure" in markdown


def test_runner_enforces_backend_timeout(tmp_path):
    store = _store(tmp_path)
    runner = ParserBenchmarkRunner(
        store,
        tmp_path / "timeout-output",
        registry=ParserRegistry([FakeSlowAdapter()]),
    )

    report = runner.run(
        document_ids=["fixture"],
        backends=["fake-slow"],
        timeout=0.05,
    )

    assert report.runs[0].status == "timeout"
    assert "exceeded timeout" in report.runs[0].error
