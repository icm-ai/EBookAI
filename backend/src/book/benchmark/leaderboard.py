"""Coverage-aware parser leaderboard over reviewed gold benchmark results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from book.benchmark.models import BackendRunResult, BenchmarkReport

LEADERBOARD_SCHEMA_VERSION = "1"
DEFAULT_ACCURACY_PATHS: Tuple[str, ...] = (
    "text.f1",
    "reading_order.pair_accuracy",
    "structures.headings.f1",
    "structures.lists.f1",
    "structures.tables.f1",
    "structures.figures.f1",
    "structures.captions.f1",
    "structures.footnotes.f1",
    "structures.formulas.f1",
)


def _metric_at_path(payload: Dict[str, Any], path: str) -> Optional[float]:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    return float(current)


def _mean(values: Iterable[float]) -> Optional[float]:
    items = list(values)
    return round(mean(items), 4) if items else None


@dataclass(frozen=True)
class LeaderboardPolicy:
    """Eligibility and aggregation policy for a benchmark leaderboard."""

    accuracy_paths: Tuple[str, ...] = DEFAULT_ACCURACY_PATHS
    include_draft: bool = False
    minimum_annotated_pages: int = 1
    minimum_annotated_documents: int = 1
    maximum_metric_regression: float = 0.0

    def __post_init__(self) -> None:
        if not self.accuracy_paths:
            raise ValueError("Leaderboard policy requires at least one accuracy metric")
        if len(self.accuracy_paths) != len(set(self.accuracy_paths)):
            raise ValueError("Leaderboard accuracy paths must be unique")
        if self.minimum_annotated_pages < 0:
            raise ValueError("minimum_annotated_pages must be >= 0")
        if self.minimum_annotated_documents < 0:
            raise ValueError("minimum_annotated_documents must be >= 0")
        if self.maximum_metric_regression < 0:
            raise ValueError("maximum_metric_regression must be >= 0")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "LeaderboardPolicy":
        schema_version = str(
            value.get("schema_version", LEADERBOARD_SCHEMA_VERSION)
        )
        if schema_version != LEADERBOARD_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported leaderboard policy schema: {schema_version!r}"
            )
        return cls(
            accuracy_paths=tuple(
                str(item)
                for item in value.get("accuracy_paths", DEFAULT_ACCURACY_PATHS)
            ),
            include_draft=bool(value.get("include_draft", False)),
            minimum_annotated_pages=int(value.get("minimum_annotated_pages", 1)),
            minimum_annotated_documents=int(
                value.get("minimum_annotated_documents", 1)
            ),
            maximum_metric_regression=float(
                value.get("maximum_metric_regression", 0.0)
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "LeaderboardPolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Leaderboard policy root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": LEADERBOARD_SCHEMA_VERSION,
            "accuracy_paths": list(self.accuracy_paths),
            "include_draft": self.include_draft,
            "minimum_annotated_pages": self.minimum_annotated_pages,
            "minimum_annotated_documents": self.minimum_annotated_documents,
            "maximum_metric_regression": self.maximum_metric_regression,
        }


@dataclass(frozen=True)
class BackendLeaderboardEntry:
    backend: str
    rank: Optional[int]
    eligible: bool
    accuracy_macro: Optional[float]
    metrics: Dict[str, Optional[float]]
    annotated_documents: int
    annotated_pages: int
    evaluated_metric_count: int
    mean_elapsed_seconds: Optional[float]
    mean_quality_score: Optional[float]
    statuses: Dict[str, int] = field(default_factory=dict)
    exclusion_reasons: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "rank": self.rank,
            "eligible": self.eligible,
            "accuracy_macro": self.accuracy_macro,
            "metrics": self.metrics,
            "coverage": {
                "annotated_documents": self.annotated_documents,
                "annotated_pages": self.annotated_pages,
                "evaluated_metric_count": self.evaluated_metric_count,
            },
            "mean_elapsed_seconds": self.mean_elapsed_seconds,
            "mean_quality_score": self.mean_quality_score,
            "statuses": self.statuses,
            "exclusion_reasons": list(self.exclusion_reasons),
        }


@dataclass(frozen=True)
class ParserLeaderboard:
    corpus_id: str
    policy: LeaderboardPolicy
    entries: Tuple[BackendLeaderboardEntry, ...]
    schema_version: str = LEADERBOARD_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "policy": self.policy.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ParserLeaderboard":
        if str(value.get("schema_version", "")) != LEADERBOARD_SCHEMA_VERSION:
            raise ValueError("Unsupported leaderboard schema")
        policy = LeaderboardPolicy.from_dict(dict(value.get("policy", {})))
        entries = []
        for item in value.get("entries", []):
            coverage = dict(item.get("coverage", {}))
            entries.append(
                BackendLeaderboardEntry(
                    backend=str(item["backend"]),
                    rank=(
                        int(item["rank"]) if item.get("rank") is not None else None
                    ),
                    eligible=bool(item.get("eligible", False)),
                    accuracy_macro=(
                        float(item["accuracy_macro"])
                        if item.get("accuracy_macro") is not None
                        else None
                    ),
                    metrics={
                        str(name): (
                            float(metric) if metric is not None else None
                        )
                        for name, metric in dict(item.get("metrics", {})).items()
                    },
                    annotated_documents=int(
                        coverage.get("annotated_documents", 0)
                    ),
                    annotated_pages=int(coverage.get("annotated_pages", 0)),
                    evaluated_metric_count=int(
                        coverage.get("evaluated_metric_count", 0)
                    ),
                    mean_elapsed_seconds=(
                        float(item["mean_elapsed_seconds"])
                        if item.get("mean_elapsed_seconds") is not None
                        else None
                    ),
                    mean_quality_score=(
                        float(item["mean_quality_score"])
                        if item.get("mean_quality_score") is not None
                        else None
                    ),
                    statuses={
                        str(name): int(count)
                        for name, count in dict(item.get("statuses", {})).items()
                    },
                    exclusion_reasons=tuple(
                        str(reason)
                        for reason in item.get("exclusion_reasons", [])
                    ),
                )
            )
        return cls(
            corpus_id=str(value["corpus_id"]),
            policy=policy,
            entries=tuple(entries),
        )

    @classmethod
    def load(cls, path: Path) -> "ParserLeaderboard":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Leaderboard root must be an object")
        return cls.from_dict(payload)


def _annotation_is_eligible(run: BackendRunResult, policy: LeaderboardPolicy) -> bool:
    status = run.gold_metrics.get("annotation_status")
    return status == "reviewed" or (policy.include_draft and status == "draft")


def _backend_entry(
    backend: str,
    runs: Sequence[BackendRunResult],
    policy: LeaderboardPolicy,
) -> BackendLeaderboardEntry:
    successful = [run for run in runs if run.status == "success"]
    gold_runs = [
        run
        for run in successful
        if run.gold_metrics and _annotation_is_eligible(run, policy)
    ]

    metric_values: Dict[str, List[float]] = {
        path: [] for path in policy.accuracy_paths
    }
    annotated_documents = set()
    annotated_pages = set()
    for run in gold_runs:
        annotated_documents.add(run.document_id)
        for page in run.gold_metrics.get("annotated_pages", []):
            annotated_pages.add((run.document_id, int(page)))
        for path in policy.accuracy_paths:
            value = _metric_at_path(run.gold_metrics, path)
            if value is not None:
                metric_values[path].append(value)

    metrics = {
        path: _mean(values)
        for path, values in metric_values.items()
    }
    available_metrics = [
        value for value in metrics.values() if value is not None
    ]
    accuracy_macro = _mean(available_metrics)
    exclusion_reasons: List[str] = []
    if len(annotated_documents) < policy.minimum_annotated_documents:
        exclusion_reasons.append(
            "reviewed document coverage "
            f"{len(annotated_documents)} < {policy.minimum_annotated_documents}"
        )
    if len(annotated_pages) < policy.minimum_annotated_pages:
        exclusion_reasons.append(
            "reviewed page coverage "
            f"{len(annotated_pages)} < {policy.minimum_annotated_pages}"
        )
    if not available_metrics:
        exclusion_reasons.append("no eligible gold accuracy metrics")

    status_names = ("success", "skipped", "failed", "timeout")
    statuses = {
        status: sum(run.status == status for run in runs)
        for status in status_names
    }
    elapsed = [run.elapsed_seconds for run in successful]
    quality = [
        float(run.metrics["quality_score"])
        for run in successful
        if isinstance(run.metrics.get("quality_score"), (int, float))
    ]
    return BackendLeaderboardEntry(
        backend=backend,
        rank=None,
        eligible=not exclusion_reasons,
        accuracy_macro=accuracy_macro,
        metrics=metrics,
        annotated_documents=len(annotated_documents),
        annotated_pages=len(annotated_pages),
        evaluated_metric_count=len(available_metrics),
        mean_elapsed_seconds=_mean(elapsed),
        mean_quality_score=_mean(quality),
        statuses=statuses,
        exclusion_reasons=tuple(exclusion_reasons),
    )


def build_leaderboard(
    report: BenchmarkReport,
    *,
    policy: Optional[LeaderboardPolicy] = None,
) -> ParserLeaderboard:
    """Aggregate backend accuracy without letting draft or sparse gold hide coverage."""

    resolved_policy = policy or LeaderboardPolicy()
    backends = sorted({run.backend for run in report.runs})
    entries = [
        _backend_entry(
            backend,
            [run for run in report.runs if run.backend == backend],
            resolved_policy,
        )
        for backend in backends
    ]
    ranked = sorted(
        (entry for entry in entries if entry.eligible),
        key=lambda entry: (
            -(entry.accuracy_macro or 0.0),
            entry.mean_elapsed_seconds
            if entry.mean_elapsed_seconds is not None
            else float("inf"),
            entry.backend,
        ),
    )
    rank_by_backend = {entry.backend: index + 1 for index, entry in enumerate(ranked)}
    ranked_entries = tuple(
        BackendLeaderboardEntry(
            backend=entry.backend,
            rank=rank_by_backend.get(entry.backend),
            eligible=entry.eligible,
            accuracy_macro=entry.accuracy_macro,
            metrics=entry.metrics,
            annotated_documents=entry.annotated_documents,
            annotated_pages=entry.annotated_pages,
            evaluated_metric_count=entry.evaluated_metric_count,
            mean_elapsed_seconds=entry.mean_elapsed_seconds,
            mean_quality_score=entry.mean_quality_score,
            statuses=entry.statuses,
            exclusion_reasons=entry.exclusion_reasons,
        )
        for entry in sorted(
            entries,
            key=lambda item: (
                rank_by_backend.get(item.backend, 10**9),
                item.backend,
            ),
        )
    )
    return ParserLeaderboard(
        corpus_id=report.corpus_id,
        policy=resolved_policy,
        entries=ranked_entries,
    )


def compare_leaderboards(
    current: ParserLeaderboard,
    baseline: ParserLeaderboard,
    *,
    maximum_metric_regression: Optional[float] = None,
) -> List[str]:
    """Return deterministic reviewed-gold regressions against a saved snapshot."""

    allowed = (
        current.policy.maximum_metric_regression
        if maximum_metric_regression is None
        else float(maximum_metric_regression)
    )
    if allowed < 0:
        raise ValueError("maximum_metric_regression must be >= 0")
    baseline_by_backend = {entry.backend: entry for entry in baseline.entries}
    failures: List[str] = []
    for entry in current.entries:
        previous = baseline_by_backend.get(entry.backend)
        if previous is None:
            continue
        for path in current.policy.accuracy_paths:
            before = previous.metrics.get(path)
            after = entry.metrics.get(path)
            if before is None or after is None:
                continue
            drop = round(before - after, 4)
            if drop > allowed:
                failures.append(
                    f"{entry.backend}:{path}: baseline {before}, current {after}, "
                    f"drop {drop} > {allowed}"
                )
    return sorted(failures)


def render_leaderboard_markdown(leaderboard: ParserLeaderboard) -> str:
    lines = [
        "# Parser Gold Leaderboard",
        "",
        f"- Corpus: `{leaderboard.corpus_id}`",
        f"- Gold mode: {'reviewed + draft' if leaderboard.policy.include_draft else 'reviewed only'}",
        f"- Minimum documents: {leaderboard.policy.minimum_annotated_documents}",
        f"- Minimum pages: {leaderboard.policy.minimum_annotated_pages}",
        "",
        "> Ranking is based only on eligible gold metrics. Latency and Quality Engine "
        "scores are shown as separate engineering dimensions and do not alter accuracy rank.",
        "",
        "| Rank | Backend | Eligible | Accuracy macro | Gold docs | Gold pages | "
        "Metrics | Mean time (s) | Mean quality |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in leaderboard.entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(entry.rank) if entry.rank is not None else "—",
                    entry.backend,
                    "yes" if entry.eligible else "no",
                    (
                        f"{entry.accuracy_macro:.4f}"
                        if entry.accuracy_macro is not None
                        else "—"
                    ),
                    str(entry.annotated_documents),
                    str(entry.annotated_pages),
                    str(entry.evaluated_metric_count),
                    (
                        f"{entry.mean_elapsed_seconds:.4f}"
                        if entry.mean_elapsed_seconds is not None
                        else "—"
                    ),
                    (
                        f"{entry.mean_quality_score:.4f}"
                        if entry.mean_quality_score is not None
                        else "—"
                    ),
                ]
            )
            + " |"
        )
        if entry.exclusion_reasons:
            lines.append(
                f"<!-- {entry.backend}: "
                + "; ".join(entry.exclusion_reasons)
                + " -->"
            )

    lines.extend(
        [
            "",
            "## Accuracy dimensions",
            "",
            "| Backend | "
            + " | ".join(leaderboard.policy.accuracy_paths)
            + " |",
            "|---|" + "|".join("---:" for _ in leaderboard.policy.accuracy_paths) + "|",
        ]
    )
    for entry in leaderboard.entries:
        lines.append(
            "| "
            + " | ".join(
                [entry.backend]
                + [
                    (
                        f"{entry.metrics[path]:.4f}"
                        if entry.metrics.get(path) is not None
                        else "—"
                    )
                    for path in leaderboard.policy.accuracy_paths
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_leaderboard(
    leaderboard: ParserLeaderboard,
    output_dir: Path,
) -> Tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "leaderboard.json"
    markdown_path = output_dir / "leaderboard.md"
    json_path.write_text(leaderboard.to_json() + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_leaderboard_markdown(leaderboard),
        encoding="utf-8",
    )
    return json_path, markdown_path
