from pathlib import Path

from book.benchmark import CorpusStore, ParserBenchmarkRunner
from book.parsers import MarkerAdapter, MinerUAdapter

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmark" / "corpus" / "manifest.json"


def test_real_rights_cleared_pdf_smoke_benchmark(tmp_path, monkeypatch):
    monkeypatch.setattr(MinerUAdapter, "is_available", lambda self: False)
    monkeypatch.setattr(MarkerAdapter, "is_available", lambda self: False)

    store = CorpusStore(MANIFEST, tmp_path / "corpus")
    materialized = store.fetch(["nist-ballot-definition-prototype"])[0]
    assert materialized.sha256 == (
        "98649f6216af762aa9ff1290665f42dc7978d90523ae6ddd9e50c460a8e540a0"
    )

    runner = ParserBenchmarkRunner(store, tmp_path / "benchmark")
    report = runner.run(
        document_ids=["nist-ballot-definition-prototype"],
        backends=["pymupdf", "mineru", "marker"],
        timeout=30.0,
        fetch_missing=False,
    )

    runs = {run.backend: run for run in report.runs}
    assert runs["pymupdf"].status == "success"
    assert runs["mineru"].status == "skipped"
    assert runs["marker"].status == "skipped"

    metrics = runs["pymupdf"].metrics
    assert metrics["expected_page_count"] == 1
    assert 0.0 <= metrics["page_coverage"] <= 1.0
    assert metrics["node_count"] >= 0
    assert metrics["text_char_count"] >= 0
    assert Path(runs["pymupdf"].bookir_path).is_file()
