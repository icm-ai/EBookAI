"""Human-readable reporting for parser benchmark JSON results."""

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional

from book.benchmark.models import BackendRunResult, BenchmarkReport


def _fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mean_metric(runs: Iterable[BackendRunResult], name: str) -> Optional[float]:
    values = []
    for run in runs:
        value = run.metrics.get(name)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return round(mean(values), 4) if values else None


def _nested_metric(value: Dict[str, object], path: str) -> object:
    current: object = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def render_markdown(report: BenchmarkReport) -> str:
    """Render a comparison report without turning proxies into truth labels."""

    payload = report.to_dict()
    summary = payload["summary"]
    lines: List[str] = [
        "# Real-world Parser Benchmark",
        "",
        f"- Corpus: `{report.corpus_id}`",
        f"- Documents: {summary['document_count']}",
        f"- Backends: {summary['backend_count']}",
        f"- Runs: {summary['run_count']}",
        "",
        "> Proxy metrics and Gold Accuracy are intentionally separated. "
        "Cross-backend agreement is not a correctness label; gold metrics are "
        "computed only for explicitly annotated pages/tasks bound to exact PDF bytes.",
        "",
        "## Backend summary",
        "",
        "| Backend | Success | Skipped | Failed | Timeout | Runnable success | "
        "Mean time (s) | Mean quality | Mean relative text |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for backend, backend_summary in sorted(summary["by_backend"].items()):
        backend_runs = [
            run
            for run in report.runs
            if run.backend == backend and run.status == "success"
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    backend,
                    str(backend_summary["success"]),
                    str(backend_summary["skipped"]),
                    str(backend_summary["failed"]),
                    str(backend_summary["timeout"]),
                    _fmt(backend_summary["runnable_success_rate"]),
                    _fmt(backend_summary["mean_elapsed_seconds"]),
                    _fmt(_mean_metric(backend_runs, "quality_score")),
                    _fmt(_mean_metric(backend_runs, "relative_text_coverage")),
                ]
            )
            + " |"
        )

    documents: Dict[str, Dict[str, object]] = {
        str(item.get("id")): item for item in report.documents
    }
    for document_id in sorted({run.document_id for run in report.runs}):
        spec = documents.get(document_id, {})
        title = str(spec.get("title") or document_id)
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                f"Document id: `{document_id}`",
                "",
                "| Backend | Status | Time (s) | Text chars | Page coverage | "
                "Order proxy | Semantic fraction | Structure recovery | Quality | "
                "Consensus Jaccard |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        document_runs = sorted(
            (run for run in report.runs if run.document_id == document_id),
            key=lambda item: item.backend,
        )
        for run in document_runs:
            metrics = run.metrics
            lines.append(
                "| "
                + " | ".join(
                    [
                        run.backend,
                        run.status,
                        _fmt(run.elapsed_seconds, 3),
                        _fmt(metrics.get("text_char_count")),
                        _fmt(metrics.get("page_coverage")),
                        _fmt(metrics.get("reading_order_proxy")),
                        _fmt(metrics.get("semantic_node_fraction")),
                        _fmt(metrics.get("expected_structure_recovery")),
                        _fmt(metrics.get("quality_score")),
                        _fmt(metrics.get("text_consensus_jaccard_mean")),
                    ]
                )
                + " |"
            )
        gold_runs = [run for run in document_runs if run.gold_metrics]
        if gold_runs:
            lines.extend(
                [
                    "",
                    "### Gold Accuracy",
                    "",
                    "| Backend | Annotation | Text P | Text R | Text F1 | "
                    "Order pair | Heading P | Heading R | Heading F1 | "
                    "Heading level | Gate |",
                    "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
                ]
            )
            for run in gold_runs:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            run.backend,
                            _fmt(run.gold_metrics.get("annotation_status")),
                            _fmt(_nested_metric(run.gold_metrics, "text.precision")),
                            _fmt(_nested_metric(run.gold_metrics, "text.recall")),
                            _fmt(_nested_metric(run.gold_metrics, "text.f1")),
                            _fmt(
                                _nested_metric(
                                    run.gold_metrics,
                                    "reading_order.pair_accuracy",
                                )
                            ),
                            _fmt(
                                _nested_metric(
                                    run.gold_metrics,
                                    "structures.headings.precision",
                                )
                            ),
                            _fmt(
                                _nested_metric(
                                    run.gold_metrics,
                                    "structures.headings.recall",
                                )
                            ),
                            _fmt(
                                _nested_metric(
                                    run.gold_metrics,
                                    "structures.headings.f1",
                                )
                            ),
                            _fmt(
                                _nested_metric(
                                    run.gold_metrics,
                                    "structures.headings.level_accuracy",
                                )
                            ),
                            (
                                "PASS"
                                if not run.gold_gate_failures
                                else "FAIL: "
                                + "; ".join(run.gold_gate_failures)
                            ),
                        ]
                    )
                    + " |"
                )
            lines.extend(
                [
                    "",
                    "Gold values marked `—` were not annotated for that task. "
                    "Draft annotations are informational and cannot enforce gates.",
                ]
            )

        diagnostics = [
            (run.backend, message)
            for run in document_runs
            for message in ([run.error] if run.error else []) + run.warnings
        ]
        if diagnostics:
            lines.extend(["", "### Diagnostics", ""])
            for backend, message in diagnostics:
                lines.append(f"- `{backend}`: {message}")

    return "\n".join(lines) + "\n"


def write_markdown(report: BenchmarkReport, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(report), encoding="utf-8")
    return output_path
