from pathlib import Path

from book.publication import ExternalEpubCheckRunner
from book.regression import GoldenCaseSpec, GoldenCorpusHarness, RenderEvidence
from book.regression.synthetic import build_fixture

CASES = Path(__file__).parent / "golden" / "cases"


def _specs():
    return [GoldenCaseSpec.load(path) for path in sorted(CASES.glob("*.json"))]


def test_golden_corpus_end_to_end(tmp_path):
    harness = GoldenCorpusHarness()
    failures = []

    for spec in _specs():
        source = build_fixture(spec.fixture_kind, tmp_path / f"{spec.id}.pdf")
        result = harness.evaluate(source, spec, tmp_path / spec.id)
        if not result.passed:
            failures.append((spec.id, result.failures, result.metrics))

    assert not failures, failures


def test_golden_corpus_with_external_epubcheck_when_available(tmp_path):
    runner = ExternalEpubCheckRunner()
    if runner.resolve_command() is None:
        return

    harness = GoldenCorpusHarness(epubcheck_runner=runner)
    for spec in _specs():
        source = build_fixture(spec.fixture_kind, tmp_path / f"{spec.id}.pdf")
        result = harness.evaluate(source, spec, tmp_path / f"external-{spec.id}")
        assert result.passed, (spec.id, result.failures, result.metrics)


def test_baseline_drift_fails_even_above_absolute_threshold():
    spec = GoldenCaseSpec.from_dict(
        {
            "id": "drift-check",
            "category": "unit",
            "fixture_kind": "digital_basic",
            "thresholds": {
                "semantic_score_min": 0.8,
            },
            "baseline_metrics": {
                "semantic_score": 1.0,
            },
            "max_regression": {
                "semantic_score": 0.05,
            },
        }
    )
    metrics = {
        "node_type_counts": {},
        "quality_issue_codes": [],
        "footnote_reference_count": 0,
        "publication_ready": True,
        "semantic_score": 0.9,
        "text_recall": 1.0,
        "reading_order": 1.0,
        "provenance_coverage": 1.0,
        "bbox_coverage": 1.0,
        "epub_text_recall": 1.0,
        "epub_reproducible": True,
        "epubcheck": None,
    }
    evidence = RenderEvidence(
        xhtml_digest="",
        flow_digest="",
        stylesheet_digest="",
        section_count=0,
    )
    deltas = GoldenCorpusHarness._baseline_deltas(spec, metrics)
    failures = GoldenCorpusHarness._failures(
        spec,
        metrics,
        None,
        evidence,
        deltas,
    )

    assert metrics["semantic_score"] >= spec.thresholds.semantic_score_min
    assert deltas["semantic_score"] == -0.1
    assert any("semantic_score regression" in failure for failure in failures)


def test_baseline_drift_allows_improvement():
    spec = GoldenCaseSpec.from_dict(
        {
            "id": "drift-improvement",
            "category": "unit",
            "fixture_kind": "digital_basic",
            "baseline_metrics": {
                "quality_score": 0.9,
            },
            "max_regression": {
                "quality_score": 0.0,
            },
        }
    )
    metrics = {
        "node_type_counts": {},
        "quality_issue_codes": [],
        "footnote_reference_count": 0,
        "publication_ready": True,
        "quality_score": 0.95,
        "text_recall": 1.0,
        "reading_order": 1.0,
        "provenance_coverage": 1.0,
        "bbox_coverage": 1.0,
        "epub_text_recall": 1.0,
        "epub_reproducible": True,
        "epubcheck": None,
    }
    evidence = RenderEvidence(
        xhtml_digest="",
        flow_digest="",
        stylesheet_digest="",
        section_count=0,
    )
    deltas = GoldenCorpusHarness._baseline_deltas(spec, metrics)
    failures = GoldenCorpusHarness._failures(
        spec,
        metrics,
        None,
        evidence,
        deltas,
    )

    assert deltas["quality_score"] == 0.05
    assert not failures
