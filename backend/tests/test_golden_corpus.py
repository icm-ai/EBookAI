from pathlib import Path

from book.publication import ExternalEpubCheckRunner
from book.regression import GoldenCaseSpec, GoldenCorpusHarness
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
