"""Human review planning for sparse gold corpus expansion."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from book.benchmark.gold import GOLD_TASKS, load_gold_annotation
from book.benchmark.models import CorpusManifest

REVIEW_PLAN_SCHEMA_VERSION = "1"
_ALLOWED_PRIORITIES = {"high", "medium", "low"}


@dataclass(frozen=True)
class ReviewTarget:
    document_id: str
    page_index: int
    tasks: Tuple[str, ...]
    difficulty_tags: Tuple[str, ...] = ()
    priority: str = "medium"
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("Review target document_id must not be empty")
        if self.page_index < 0:
            raise ValueError("Review target page_index must be >= 0")
        if not self.tasks:
            raise ValueError("Review target must include at least one task")
        unknown = sorted(set(self.tasks) - GOLD_TASKS)
        if unknown:
            raise ValueError("Unknown review tasks: " + ", ".join(unknown))
        if self.priority not in _ALLOWED_PRIORITIES:
            raise ValueError(f"Unsupported review priority: {self.priority!r}")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewTarget":
        return cls(
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
            tasks=tuple(str(item) for item in value.get("tasks", [])),
            difficulty_tags=tuple(
                str(item) for item in value.get("difficulty_tags", [])
            ),
            priority=str(value.get("priority", "medium")),
            rationale=str(value.get("rationale", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_index": self.page_index,
            "tasks": list(self.tasks),
            "difficulty_tags": list(self.difficulty_tags),
            "priority": self.priority,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ReviewPlan:
    corpus_id: str
    targets: Tuple[ReviewTarget, ...]
    schema_version: str = REVIEW_PLAN_SCHEMA_VERSION
    description: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REVIEW_PLAN_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported review plan schema: {self.schema_version!r}"
            )
        if not self.corpus_id.strip():
            raise ValueError("Review plan corpus_id must not be empty")
        keys = [(target.document_id, target.page_index) for target in self.targets]
        if len(keys) != len(set(keys)):
            raise ValueError("Review plan contains duplicate document/page targets")
        if not self.targets:
            raise ValueError("Review plan must contain at least one target")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewPlan":
        targets = value.get("targets")
        if not isinstance(targets, list):
            raise ValueError("Review plan targets must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            corpus_id=str(value["corpus_id"]),
            description=str(value.get("description", "")),
            targets=tuple(ReviewTarget.from_dict(item) for item in targets),
        )

    @classmethod
    def load(cls, path: Path) -> "ReviewPlan":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Review plan root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "description": self.description,
            "targets": [target.to_dict() for target in self.targets],
        }


def validate_review_plan(
    plan: ReviewPlan,
    manifest: CorpusManifest,
) -> List[str]:
    """Validate review targets against immutable corpus metadata."""

    if plan.corpus_id != manifest.corpus_id:
        raise ValueError(
            f"Review plan corpus_id {plan.corpus_id!r} does not match "
            f"manifest {manifest.corpus_id!r}"
        )
    by_id = {document.id: document for document in manifest.documents}
    errors: List[str] = []
    for target in plan.targets:
        spec = by_id.get(target.document_id)
        if spec is None:
            errors.append(f"unknown document: {target.document_id}")
            continue
        if target.page_index >= spec.page_count:
            errors.append(
                f"{target.document_id}: page {target.page_index} outside "
                f"page_count={spec.page_count}"
            )
    if errors:
        raise ValueError("; ".join(sorted(errors)))
    return []


def review_plan_summary(
    plan: ReviewPlan,
    *,
    document_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    selected = set(document_ids) if document_ids is not None else None
    targets = [
        target
        for target in plan.targets
        if selected is None or target.document_id in selected
    ]
    task_counts = Counter(task for target in targets for task in target.tasks)
    difficulty_counts = Counter(
        tag for target in targets for tag in target.difficulty_tags
    )
    priority_counts = Counter(target.priority for target in targets)
    documents = sorted({target.document_id for target in targets})
    return {
        "target_count": len(targets),
        "document_count": len(documents),
        "documents": documents,
        "task_counts": dict(sorted(task_counts.items())),
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
    }




def review_plan_coverage(
    plan: ReviewPlan,
    manifest: CorpusManifest,
    manifest_path: Path,
) -> Dict[str, Any]:
    """Classify each target as unannotated, draft, or reviewed."""

    by_document = {document.id: document for document in manifest.documents}
    status_by_page: Dict[Tuple[str, int], str] = {}
    for document_id in sorted({target.document_id for target in plan.targets}):
        spec = by_document.get(document_id)
        if spec is None:
            continue
        annotation = load_gold_annotation(manifest_path, spec)
        if annotation is None:
            continue
        for page in annotation.pages:
            status_by_page[(document_id, page.page_index)] = annotation.status

    target_statuses = [
        {
            "document_id": target.document_id,
            "page_index": target.page_index,
            "status": status_by_page.get(
                (target.document_id, target.page_index), "unannotated"
            ),
        }
        for target in plan.targets
    ]
    counts = Counter(item["status"] for item in target_statuses)
    return {
        "target_count": len(target_statuses),
        "unannotated": counts["unannotated"],
        "draft": counts["draft"],
        "reviewed": counts["reviewed"],
        "targets": target_statuses,
    }


def render_review_plan_markdown(plan: ReviewPlan) -> str:
    summary = review_plan_summary(plan)
    lines = [
        "# Gold Review Plan",
        "",
        f"- Corpus: `{plan.corpus_id}`",
        f"- Documents: {summary['document_count']}",
        f"- Target pages: {summary['target_count']}",
        "",
        "> These are review targets, not reviewed gold. A target becomes leaderboard "
        "evidence only after its annotation is explicitly marked reviewed.",
        "",
        "| Priority | Document | PDF page index | Tasks | Difficulty | Rationale |",
        "|---|---|---:|---|---|---|",
    ]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for target in sorted(
        plan.targets,
        key=lambda item: (
            priority_order[item.priority],
            item.document_id,
            item.page_index,
        ),
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    target.priority,
                    f"`{target.document_id}`",
                    str(target.page_index),
                    ", ".join(target.tasks),
                    ", ".join(target.difficulty_tags) or "—",
                    target.rationale.replace("|", "\\|").replace("\n", " "),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
