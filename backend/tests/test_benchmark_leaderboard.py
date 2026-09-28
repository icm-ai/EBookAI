from pathlib import Path

from book.benchmark import (
    BackendRunResult,
    BenchmarkReport,
    LeaderboardPolicy,
    ParserLeaderboard,
    build_leaderboard,
    compare_leaderboards,
    render_leaderboard_markdown,
    write_leaderboard,
)


def _run(
    *,
    document_id: str,
    backend: str,
    text_f1: float,
    order_accuracy: float,
    elapsed: float,
    quality: float,
    annotation_status: str = "reviewed",
    pages=(0,),
) -> BackendRunResult:
    return BackendRunResult(
        document_id=document_id,
        backend=backend,
        status="success",
        elapsed_seconds=elapsed,
        metrics={"quality_score": quality},
        gold_metrics={
            "annotation_status": annotation_status,
            "annotated_pages": list(pages),
            "text": {"f1": text_f1},
            "reading_order": {"pair_accuracy": order_accuracy},
            "structures": {
                "headings": None,
                "lists": None,
                "tables": None,
                "figures": None,
                "captions": None,
                "footnotes": None,
                "formulas": None,
            },
        },
    )


def _report() -> BenchmarkReport:
    return BenchmarkReport(
        corpus_id="fixture-corpus",
        manifest_path="manifest.json",
        documents=[{"id": "doc-a"}, {"id": "doc-b"}],
        runs=[
            _run(
                document_id="doc-a",
                backend="alpha",
                text_f1=0.9,
                order_accuracy=1.0,
                elapsed=2.0,
                quality=0.8,
            ),
            _run(
                document_id="doc-b",
                backend="alpha",
                text_f1=0.8,
                order_accuracy=0.5,
                elapsed=4.0,
                quality=0.6,
            ),
            _run(
                document_id="doc-a",
                backend="beta",
                text_f1=1.0,
                order_accuracy=1.0,
                elapsed=1.0,
                quality=0.9,
                annotation_status="draft",
            ),
        ],
    )


def test_reviewed_only_leaderboard_is_coverage_aware():
    board = build_leaderboard(
        _report(),
        policy=LeaderboardPolicy(
            minimum_annotated_documents=2,
            minimum_annotated_pages=2,
        ),
    )

    by_backend = {entry.backend: entry for entry in board.entries}
    alpha = by_backend["alpha"]
    beta = by_backend["beta"]

    assert alpha.eligible is True
    assert alpha.rank == 1
    assert alpha.metrics["text.f1"] == 0.85
    assert alpha.metrics["reading_order.pair_accuracy"] == 0.75
    assert alpha.accuracy_macro == 0.8
    assert alpha.annotated_documents == 2
    assert alpha.annotated_pages == 2
    assert alpha.mean_elapsed_seconds == 3.0
    assert alpha.mean_quality_score == 0.7

    assert beta.eligible is False
    assert beta.rank is None
    assert beta.accuracy_macro is None
    assert "reviewed document coverage 0 < 2" in beta.exclusion_reasons
    assert "no eligible gold accuracy metrics" in beta.exclusion_reasons


def test_draft_can_be_opted_into_exploratory_leaderboard():
    board = build_leaderboard(
        _report(),
        policy=LeaderboardPolicy(
            include_draft=True,
            minimum_annotated_documents=1,
            minimum_annotated_pages=1,
        ),
    )

    by_backend = {entry.backend: entry for entry in board.entries}
    assert by_backend["beta"].eligible is True
    assert by_backend["beta"].accuracy_macro == 1.0
    assert by_backend["beta"].rank == 1
    assert by_backend["alpha"].rank == 2


def test_latency_and_quality_do_not_change_accuracy_rank():
    report = BenchmarkReport(
        corpus_id="fixture-corpus",
        manifest_path="manifest.json",
        runs=[
            _run(
                document_id="doc",
                backend="accurate-slow",
                text_f1=0.9,
                order_accuracy=0.9,
                elapsed=10.0,
                quality=0.1,
            ),
            _run(
                document_id="doc",
                backend="fast-proxy-high",
                text_f1=0.8,
                order_accuracy=0.8,
                elapsed=0.1,
                quality=1.0,
            ),
        ],
    )

    board = build_leaderboard(report)

    assert board.entries[0].backend == "accurate-slow"
    assert board.entries[0].rank == 1
    assert board.entries[1].rank == 2


def test_leaderboard_regression_compares_metrics_not_rank():
    baseline = build_leaderboard(_report())
    current_report = _report()
    current_report.runs[0].gold_metrics["text"]["f1"] = 0.7
    current = build_leaderboard(current_report)

    failures = compare_leaderboards(
        current,
        baseline,
        maximum_metric_regression=0.05,
    )

    assert failures == ["alpha:text.f1: baseline 0.85, current 0.75, drop 0.1 > 0.05"]


def test_leaderboard_round_trip_and_markdown(tmp_path):
    board = build_leaderboard(_report())

    json_path, markdown_path = write_leaderboard(board, tmp_path)
    loaded = ParserLeaderboard.load(json_path)
    markdown = markdown_path.read_text(encoding="utf-8")

    assert loaded.to_dict() == board.to_dict()
    assert "Parser Gold Leaderboard" in markdown
    assert "accuracy rank" in markdown
    assert "text.f1" in markdown
    assert render_leaderboard_markdown(board) == markdown
    assert Path(json_path).is_file()


def test_policy_rejects_unsupported_schema():
    try:
        LeaderboardPolicy.from_dict({"schema_version": "999"})
    except ValueError as exc:
        assert "Unsupported leaderboard policy schema" in str(exc)
    else:
        raise AssertionError("unsupported policy schema must fail")
