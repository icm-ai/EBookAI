"""Reviewer assignment batches for benchmark gold operations."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import ConsensusProvenanceRegistry
from book.benchmark.review_plan import ReviewPlan, ReviewTarget, validate_review_plan

REVIEW_BATCH_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ReviewerAssignment:
    document_id: str
    page_index: int
    reviewer_a: str
    reviewer_b: str
    adjudicator: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("Reviewer assignment document_id must not be empty")
        if self.page_index < 0:
            raise ValueError("Reviewer assignment page_index must be >= 0")
        reviewers = (self.reviewer_a.strip(), self.reviewer_b.strip())
        if not all(reviewers):
            raise ValueError("Reviewer assignment requires reviewer A and reviewer B")
        if reviewers[0] == reviewers[1]:
            raise ValueError("Reviewer A and reviewer B must be distinct")
        if self.adjudicator.strip() and self.adjudicator.strip() in set(reviewers):
            raise ValueError("Adjudicator must differ from both reviewers")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewerAssignment":
        return cls(
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
            reviewer_a=str(value["reviewer_a"]),
            reviewer_b=str(value["reviewer_b"]),
            adjudicator=str(value.get("adjudicator", "")),
            note=str(value.get("note", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_index": self.page_index,
            "reviewer_a": self.reviewer_a,
            "reviewer_b": self.reviewer_b,
            "adjudicator": self.adjudicator,
            "note": self.note,
        }


@dataclass(frozen=True)
class ReviewBatch:
    batch_id: str
    corpus_id: str
    assignments: Tuple[ReviewerAssignment, ...]
    created_by: str
    created_at: str
    description: str = ""
    schema_version: str = REVIEW_BATCH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REVIEW_BATCH_SCHEMA_VERSION:
            raise ValueError(f"Unsupported review batch schema: {self.schema_version!r}")
        if not self.batch_id.strip():
            raise ValueError("Review batch id must not be empty")
        if not self.corpus_id.strip():
            raise ValueError("Review batch corpus_id must not be empty")
        if not self.created_by.strip():
            raise ValueError("Review batch created_by must not be empty")
        if not self.assignments:
            raise ValueError("Review batch must contain at least one assignment")
        keys = [
            (assignment.document_id, assignment.page_index)
            for assignment in self.assignments
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Review batch contains duplicate document/page assignments")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewBatch":
        assignments = value.get("assignments")
        if not isinstance(assignments, list):
            raise ValueError("Review batch assignments must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            batch_id=str(value["batch_id"]),
            corpus_id=str(value["corpus_id"]),
            assignments=tuple(
                ReviewerAssignment.from_dict(item) for item in assignments
            ),
            created_by=str(value["created_by"]),
            created_at=str(value["created_at"]),
            description=str(value.get("description", "")),
        )

    @classmethod
    def load(cls, path: Path) -> "ReviewBatch":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Review batch root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "corpus_id": self.corpus_id,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "description": self.description,
            "assignments": [item.to_dict() for item in self.assignments],
        }

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path


def validate_review_batch(
    batch: ReviewBatch,
    plan: ReviewPlan,
    manifest: CorpusManifest,
) -> None:
    validate_review_plan(plan, manifest)
    if batch.corpus_id != manifest.corpus_id:
        raise ValueError(
            f"Review batch corpus_id {batch.corpus_id!r} does not match "
            f"manifest {manifest.corpus_id!r}"
        )
    targets = {
        (target.document_id, target.page_index): target for target in plan.targets
    }
    errors: List[str] = []
    for assignment in batch.assignments:
        if (assignment.document_id, assignment.page_index) not in targets:
            errors.append(
                f"{assignment.document_id} page {assignment.page_index} is not "
                "in the review plan"
            )
    if errors:
        raise ValueError("; ".join(sorted(errors)))


def create_review_batch(
    *,
    batch_id: str,
    created_by: str,
    reviewer_a: str,
    reviewer_b: str,
    plan: ReviewPlan,
    manifest: CorpusManifest,
    adjudicator: str = "",
    priorities: Optional[Iterable[str]] = None,
    document_ids: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    description: str = "",
) -> ReviewBatch:
    priority_filter = set(priorities) if priorities is not None else None
    document_filter = set(document_ids) if document_ids is not None else None
    targets: List[ReviewTarget] = [
        target
        for target in plan.targets
        if (
            priority_filter is None
            or target.priority in priority_filter
        )
        and (
            document_filter is None
            or target.document_id in document_filter
        )
    ]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    targets.sort(
        key=lambda item: (
            priority_order[item.priority],
            item.document_id,
            item.page_index,
        )
    )
    if limit is not None:
        if limit <= 0:
            raise ValueError("Review batch limit must be > 0")
        targets = targets[:limit]
    if not targets:
        raise ValueError("Review batch selection produced no targets")
    batch = ReviewBatch(
        batch_id=batch_id,
        corpus_id=plan.corpus_id,
        assignments=tuple(
            ReviewerAssignment(
                document_id=target.document_id,
                page_index=target.page_index,
                reviewer_a=reviewer_a,
                reviewer_b=reviewer_b,
                adjudicator=adjudicator,
            )
            for target in targets
        ),
        created_by=created_by,
        created_at=datetime.now(timezone.utc).isoformat(),
        description=description,
    )
    validate_review_batch(batch, plan, manifest)
    return batch


def review_batch_progress(
    batch: ReviewBatch,
    *,
    provenance_registry: ConsensusProvenanceRegistry,
) -> Dict[str, Any]:
    completed = set()
    for record in provenance_registry.records:
        for review in record.reviews:
            completed.add((record.document_id, review.page_index))

    assignments = []
    for assignment in batch.assignments:
        key = (assignment.document_id, assignment.page_index)
        assignments.append(
            {
                **assignment.to_dict(),
                "status": "reviewed" if key in completed else "assigned",
            }
        )
    counts = Counter(item["status"] for item in assignments)
    return {
        "batch_id": batch.batch_id,
        "assignment_count": len(assignments),
        "assigned": counts["assigned"],
        "reviewed": counts["reviewed"],
        "completion_ratio": round(
            counts["reviewed"] / len(assignments),
            4,
        ),
        "assignments": assignments,
    }


def render_review_batch_markdown(
    batch: ReviewBatch,
    *,
    progress: Optional[Dict[str, Any]] = None,
) -> str:
    status_by_key: Dict[Tuple[str, int], str] = {}
    if progress is not None:
        status_by_key = {
            (str(item["document_id"]), int(item["page_index"])): str(item["status"])
            for item in progress.get("assignments", [])
        }
    lines = [
        f"# Review Batch — {batch.batch_id}",
        "",
        f"- Corpus: `{batch.corpus_id}`",
        f"- Created by: `{batch.created_by}`",
        f"- Created at: {batch.created_at}",
        f"- Assignments: {len(batch.assignments)}",
    ]
    if progress is not None:
        lines.extend(
            [
                f"- Reviewed: {progress['reviewed']}",
                f"- Remaining: {progress['assigned']}",
                f"- Completion: {progress['completion_ratio']:.1%}",
            ]
        )
    if batch.description:
        lines.extend(["", batch.description])
    lines.extend(
        [
            "",
            "| Status | Document | Page | Reviewer A | Reviewer B | Adjudicator |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for assignment in batch.assignments:
        status = status_by_key.get(
            (assignment.document_id, assignment.page_index),
            "assigned",
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    status,
                    f"`{assignment.document_id}`",
                    str(assignment.page_index),
                    f"`{assignment.reviewer_a}`",
                    f"`{assignment.reviewer_b}`",
                    (
                        f"`{assignment.adjudicator}`"
                        if assignment.adjudicator
                        else "—"
                    ),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
