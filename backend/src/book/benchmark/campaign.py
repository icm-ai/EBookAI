"""First reviewed-gold campaign orchestration and strict baseline activation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from book.benchmark.baseline import (
    ReviewedBaselineRegistry,
    build_reviewed_baseline,
    register_reviewed_baseline,
    write_reviewed_baseline,
)
from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import load_gold_annotation
from book.benchmark.governance import (
    BenchmarkGovernancePolicy,
    build_governance_release_manifest,
    evaluate_governance,
    write_governance_outputs,
)
from book.benchmark.leaderboard import (
    LeaderboardPolicy,
    build_leaderboard,
    write_leaderboard,
)
from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import ConsensusProvenanceRegistry
from book.benchmark.review_batch import (
    ReviewBatch,
    ReviewerAssignment,
    validate_review_batch,
)
from book.benchmark.review_plan import ReviewPlan, validate_review_plan
from book.benchmark.review_workbench import GoldReviewStore
from book.benchmark.runner import ParserBenchmarkRunner

CAMPAIGN_SCHEMA_VERSION = "1"
_CAMPAIGN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _safe_slug(value: str) -> str:
    slug = "".join(
        character.lower()
        if character.isalnum()
        else "-"
        for character in value.strip()
    )
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "reviewer"


@dataclass(frozen=True)
class CampaignTarget:
    document_id: str
    page_index: int

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("Campaign target document_id must not be empty")
        if self.page_index < 0:
            raise ValueError("Campaign target page_index must be >= 0")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CampaignTarget":
        return cls(
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_index": self.page_index,
        }


@dataclass(frozen=True)
class ReviewedGoldCampaign:
    campaign_id: str
    corpus_id: str
    targets: Tuple[CampaignTarget, ...]
    review_backend: str
    benchmark_backends: Tuple[str, ...]
    baseline_id: str
    baseline_filename: str
    description: str = ""
    schema_version: str = CAMPAIGN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CAMPAIGN_SCHEMA_VERSION:
            raise ValueError(f"Unsupported campaign schema: {self.schema_version!r}")
        if not _CAMPAIGN_ID_RE.fullmatch(self.campaign_id):
            raise ValueError(f"Invalid campaign id: {self.campaign_id!r}")
        if not self.corpus_id.strip():
            raise ValueError("Campaign corpus_id must not be empty")
        if not self.targets:
            raise ValueError("Campaign requires at least one target")
        keys = [(item.document_id, item.page_index) for item in self.targets]
        if len(keys) != len(set(keys)):
            raise ValueError("Campaign contains duplicate document/page targets")
        if not self.review_backend.strip():
            raise ValueError("Campaign review_backend must not be empty")
        if not self.benchmark_backends:
            raise ValueError("Campaign requires at least one benchmark backend")
        if len(self.benchmark_backends) != len(set(self.benchmark_backends)):
            raise ValueError("Campaign benchmark backends must be unique")
        if not _CAMPAIGN_ID_RE.fullmatch(self.baseline_id):
            raise ValueError(f"Invalid campaign baseline id: {self.baseline_id!r}")
        baseline_path = Path(self.baseline_filename)
        if (
            not self.baseline_filename
            or baseline_path.name != self.baseline_filename
            or baseline_path.suffix != ".json"
        ):
            raise ValueError("Campaign baseline_filename must be a plain .json filename")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewedGoldCampaign":
        targets = value.get("targets")
        if not isinstance(targets, list):
            raise ValueError("Campaign targets must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            campaign_id=str(value["campaign_id"]),
            corpus_id=str(value["corpus_id"]),
            targets=tuple(CampaignTarget.from_dict(item) for item in targets),
            review_backend=str(value.get("review_backend", "pymupdf")),
            benchmark_backends=tuple(
                str(item) for item in value.get("benchmark_backends", [])
            ),
            baseline_id=str(value["baseline_id"]),
            baseline_filename=str(value["baseline_filename"]),
            description=str(value.get("description", "")),
        )

    @classmethod
    def load(cls, path: Path) -> "ReviewedGoldCampaign":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Campaign root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "corpus_id": self.corpus_id,
            "description": self.description,
            "targets": [item.to_dict() for item in self.targets],
            "review_backend": self.review_backend,
            "benchmark_backends": list(self.benchmark_backends),
            "baseline_id": self.baseline_id,
            "baseline_filename": self.baseline_filename,
        }


@dataclass(frozen=True)
class CampaignStatus:
    campaign_id: str
    state: str
    structural_status: str
    target_count: int
    reviewed_targets: int
    active_baseline_id: Optional[str]
    targets: Tuple[Dict[str, Any], ...]
    failures: Tuple[str, ...] = ()
    pending: Tuple[str, ...] = ()
    schema_version: str = CAMPAIGN_SCHEMA_VERSION

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def ready_for_activation(self) -> bool:
        return self.state == "ready_for_activation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "state": self.state,
            "structural_status": self.structural_status,
            "target_count": self.target_count,
            "reviewed_targets": self.reviewed_targets,
            "active_baseline_id": self.active_baseline_id,
            "targets": list(self.targets),
            "failures": list(self.failures),
            "pending": list(self.pending),
        }


@dataclass(frozen=True)
class CampaignActivationResult:
    campaign_id: str
    baseline_id: str
    baseline_path: str
    benchmark_results_path: str
    leaderboard_path: str
    governance_status: str
    governance_mode: str
    reviewed_documents: int
    reviewed_pages: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "baseline_id": self.baseline_id,
            "baseline_path": self.baseline_path,
            "benchmark_results_path": self.benchmark_results_path,
            "leaderboard_path": self.leaderboard_path,
            "governance_status": self.governance_status,
            "governance_mode": self.governance_mode,
            "reviewed_documents": self.reviewed_documents,
            "reviewed_pages": self.reviewed_pages,
        }


def validate_campaign(
    campaign: ReviewedGoldCampaign,
    manifest: CorpusManifest,
    plan: ReviewPlan,
) -> None:
    validate_review_plan(plan, manifest)
    if campaign.corpus_id != manifest.corpus_id:
        raise ValueError(
            f"Campaign corpus_id {campaign.corpus_id!r} does not match "
            f"manifest {manifest.corpus_id!r}"
        )
    plan_targets = {
        (target.document_id, target.page_index): target for target in plan.targets
    }
    errors = []
    for target in campaign.targets:
        if (target.document_id, target.page_index) not in plan_targets:
            errors.append(
                f"{target.document_id} page {target.page_index} is not in the review plan"
            )
    if errors:
        raise ValueError("; ".join(sorted(errors)))


def create_campaign_batch(
    campaign: ReviewedGoldCampaign,
    *,
    manifest: CorpusManifest,
    plan: ReviewPlan,
    created_by: str,
    reviewer_a: str,
    reviewer_b: str,
    adjudicator: str = "",
    description: str = "",
) -> ReviewBatch:
    validate_campaign(campaign, manifest, plan)
    batch = ReviewBatch(
        batch_id=campaign.campaign_id,
        corpus_id=campaign.corpus_id,
        assignments=tuple(
            ReviewerAssignment(
                document_id=target.document_id,
                page_index=target.page_index,
                reviewer_a=reviewer_a,
                reviewer_b=reviewer_b,
                adjudicator=adjudicator,
            )
            for target in campaign.targets
        ),
        created_by=created_by,
        created_at=_utc_now(),
        description=description or f"Review assignments for {campaign.campaign_id}.",
    )
    validate_review_batch(batch, plan, manifest)
    return batch


def _latest_review(
    registry: ConsensusProvenanceRegistry,
    document_id: str,
    page_index: int,
):
    record = registry.document(document_id)
    if record is None:
        return None
    matches = [item for item in record.reviews if item.page_index == page_index]
    if not matches:
        return None
    return max(matches, key=lambda item: item.published_at)


def _campaign_batch_failures(
    campaign: ReviewedGoldCampaign,
    batch: ReviewBatch,
    *,
    plan: ReviewPlan,
    manifest: CorpusManifest,
) -> List[str]:
    failures: List[str] = []
    try:
        validate_review_batch(batch, plan, manifest)
    except ValueError as exc:
        return [str(exc)]
    expected = {
        (target.document_id, target.page_index) for target in campaign.targets
    }
    actual = {
        (assignment.document_id, assignment.page_index)
        for assignment in batch.assignments
    }
    if expected != actual:
        failures.append(
            "Campaign review batch must contain exactly the campaign target set"
        )
    if batch.batch_id != campaign.campaign_id:
        failures.append(
            f"Campaign review batch id {batch.batch_id!r} does not match "
            f"campaign {campaign.campaign_id!r}"
        )
    return failures


def inspect_campaign(
    campaign: ReviewedGoldCampaign,
    *,
    manifest_path: Path,
    review_plan_path: Path,
    provenance_registry_path: Path,
    baseline_registry_path: Path,
    governance_policy_path: Optional[Path] = None,
    batch: Optional[ReviewBatch] = None,
) -> CampaignStatus:
    manifest_path = Path(manifest_path).resolve()
    manifest = CorpusManifest.load(manifest_path)
    plan = ReviewPlan.load(review_plan_path)
    validate_campaign(campaign, manifest, plan)
    failures: List[str] = []
    pending: List[str] = []

    assignments: Dict[Tuple[str, int], ReviewerAssignment] = {}
    if batch is None:
        pending.append("review batch has not been assigned")
    else:
        failures.extend(
            _campaign_batch_failures(
                campaign,
                batch,
                plan=plan,
                manifest=manifest,
            )
        )
        assignments = {
            (item.document_id, item.page_index): item
            for item in batch.assignments
        }

    provenance = ConsensusProvenanceRegistry.load(provenance_registry_path)
    by_id = {item.id: item for item in manifest.documents}
    target_rows: List[Dict[str, Any]] = []
    reviewed_count = 0

    annotation_cache: Dict[str, Any] = {}
    for target in campaign.targets:
        spec = by_id[target.document_id]
        if target.document_id not in annotation_cache:
            annotation_cache[target.document_id] = load_gold_annotation(
                manifest_path,
                spec,
            )
        annotation = annotation_cache[target.document_id]
        annotated_pages = (
            {page.page_index for page in annotation.pages}
            if annotation is not None
            else set()
        )
        annotation_status = (
            annotation.status
            if annotation is not None and target.page_index in annotated_pages
            else "unannotated"
        )
        review = _latest_review(
            provenance,
            target.document_id,
            target.page_index,
        )
        has_provenance = review is not None
        reviewed = annotation_status == "reviewed" and has_provenance
        if annotation_status == "reviewed" and not has_provenance:
            failures.append(
                f"{target.document_id} page {target.page_index}: reviewed gold "
                "has no consensus provenance"
            )
        if has_provenance and annotation_status != "reviewed":
            failures.append(
                f"{target.document_id} page {target.page_index}: consensus provenance "
                "exists but canonical gold is not reviewed"
            )

        assignment = assignments.get((target.document_id, target.page_index))
        if review is not None and assignment is not None:
            expected_reviewers = {assignment.reviewer_a, assignment.reviewer_b}
            actual_reviewers = {review.reviewer_a, review.reviewer_b}
            if expected_reviewers != actual_reviewers:
                failures.append(
                    f"{target.document_id} page {target.page_index}: consensus reviewers "
                    "do not match campaign assignment"
                )
            if review.adjudicators:
                if (
                    not assignment.adjudicator
                    or set(review.adjudicators) != {assignment.adjudicator}
                ):
                    failures.append(
                        f"{target.document_id} page {target.page_index}: consensus "
                        "adjudicator does not match campaign assignment"
                    )

        if reviewed:
            reviewed_count += 1
        else:
            pending.append(
                f"{target.document_id} page {target.page_index}: "
                "independent consensus review is not yet published"
            )

        target_rows.append(
            {
                "document_id": target.document_id,
                "page_index": target.page_index,
                "annotation_status": annotation_status,
                "consensus_provenance": has_provenance,
                "reviewed": reviewed,
                "reviewer_a": review.reviewer_a if review is not None else None,
                "reviewer_b": review.reviewer_b if review is not None else None,
                "adjudicators": list(review.adjudicators) if review is not None else [],
            }
        )

    baseline_registry = ReviewedBaselineRegistry.load(baseline_registry_path)
    active_id = baseline_registry.active_baseline_id
    all_reviewed = reviewed_count == len(campaign.targets)

    if failures:
        state = "blocked"
    elif active_id == campaign.baseline_id:
        if governance_policy_path is None:
            failures.append(
                "governance policy is required to verify an active campaign baseline"
            )
            state = "blocked"
        else:
            governance = evaluate_governance(
                manifest_path,
                BenchmarkGovernancePolicy.load(governance_policy_path),
                baseline_registry_path,
                provenance_registry_path=provenance_registry_path,
            )
            if not governance.ok or governance.mode != "strict":
                failures.extend(governance.failures)
                state = "blocked"
            else:
                state = "strict"
    elif all_reviewed and batch is not None:
        state = "ready_for_activation"
        pending.append(
            f"strict baseline {campaign.baseline_id!r} is not active yet"
        )
    elif batch is None:
        state = "planned"
    elif reviewed_count:
        state = "reviewing"
    else:
        state = "assigned"

    return CampaignStatus(
        campaign_id=campaign.campaign_id,
        state=state,
        structural_status="pass" if not failures else "fail",
        target_count=len(campaign.targets),
        reviewed_targets=reviewed_count,
        active_baseline_id=active_id,
        targets=tuple(target_rows),
        failures=tuple(sorted(set(failures))),
        pending=tuple(sorted(set(pending))),
    )


def render_campaign_markdown(status: CampaignStatus) -> str:
    lines = [
        f"# Reviewed Gold Campaign — {status.campaign_id}",
        "",
        f"- State: **{status.state}**",
        f"- Structural status: **{status.structural_status}**",
        f"- Reviewed targets: {status.reviewed_targets}/{status.target_count}",
        f"- Active baseline: `{status.active_baseline_id or 'none'}`",
        "",
    ]
    if status.failures:
        lines.extend(["## Blocking failures", ""])
        lines.extend(f"- {item}" for item in status.failures)
        lines.append("")
    if status.pending:
        lines.extend(["## Pending work", ""])
        lines.extend(f"- {item}" for item in status.pending)
        lines.append("")
    lines.extend(
        [
            "## Targets",
            "",
            "| Document | Page | Gold | Provenance | Reviewed | Reviewers |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for target in status.targets:
        reviewers = " / ".join(
            item
            for item in [target.get("reviewer_a"), target.get("reviewer_b")]
            if item
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{target['document_id']}`",
                    str(target["page_index"]),
                    str(target["annotation_status"]),
                    "yes" if target["consensus_provenance"] else "no",
                    "yes" if target["reviewed"] else "no",
                    reviewers or "—",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_campaign_status(
    status: CampaignStatus,
    output_dir: Path,
) -> Tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "campaign-status.json"
    markdown_path = output_dir / "campaign-status.md"
    json_path.write_text(
        json.dumps(status.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_campaign_markdown(status), encoding="utf-8")
    return json_path, markdown_path


def generate_review_packages(
    campaign: ReviewedGoldCampaign,
    batch: ReviewBatch,
    *,
    store: GoldReviewStore,
    output_dir: Path,
) -> Dict[str, Any]:
    validate_campaign(campaign, store.manifest, store.plan)
    failures = _campaign_batch_failures(
        campaign,
        batch,
        plan=store.plan,
        manifest=store.manifest,
    )
    if failures:
        raise ValueError("; ".join(failures))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = []
    for assignment in batch.assignments:
        target = next(
            item
            for item in store.plan.targets
            if item.document_id == assignment.document_id
            and item.page_index == assignment.page_index
        )
        for role, reviewer in (
            ("reviewer_a", assignment.reviewer_a),
            ("reviewer_b", assignment.reviewer_b),
        ):
            session = store.create(
                assignment.document_id,
                assignment.page_index,
                backend=campaign.review_backend,
            )
            package_dir = (
                output_dir
                / assignment.document_id
                / f"page-{assignment.page_index:04d}"
                / f"{role}-{_safe_slug(reviewer)}"
            )
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "source-page.png").write_bytes(
                store.render_page(session.id, scale=2.0)
            )
            (package_dir / "draft-gold.json").write_text(
                json.dumps(
                    session.annotation.to_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (package_dir / "parser-bookir.json").write_text(
                session.book.to_json() + "\n",
                encoding="utf-8",
            )
            metadata = {
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "campaign_id": campaign.campaign_id,
                "batch_id": batch.batch_id,
                "document_id": assignment.document_id,
                "page_index": assignment.page_index,
                "tasks": list(target.tasks),
                "reviewer": reviewer,
                "role": role,
                "adjudicator": assignment.adjudicator or None,
                "session_id": session.id,
                "review_backend": campaign.review_backend,
                "source_sha256": session.source_sha256,
                "canonical_hash_at_open": session.canonical_hash_at_open,
                "generated_at": _utc_now(),
            }
            (package_dir / "package.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (package_dir / "README.md").write_text(
                (
                    f"# {campaign.campaign_id} — {role}\n\n"
                    f"- Reviewer: `{reviewer}`\n"
                    f"- Document: `{assignment.document_id}`\n"
                    f"- PDF page index: {assignment.page_index}\n"
                    f"- Session: `{session.id}`\n"
                    f"- Tasks: {', '.join(target.tasks)}\n\n"
                    "Review the source page independently. Do not consult the other "
                    "reviewer's annotation before promotion. Use the Gold Review "
                    "workbench session id above for edits and confirmations.\n"
                ),
                encoding="utf-8",
            )
            packages.append(metadata)

    manifest = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign.campaign_id,
        "batch_id": batch.batch_id,
        "package_count": len(packages),
        "packages": packages,
    }
    (output_dir / "review-packages.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _reviewed_document_ids(manifest_path: Path) -> List[str]:
    manifest = CorpusManifest.load(manifest_path)
    result = []
    for spec in manifest.documents:
        annotation = load_gold_annotation(manifest_path, spec)
        if annotation is not None and annotation.status == "reviewed":
            result.append(spec.id)
    return sorted(result)


def activate_strict_baseline(
    campaign: ReviewedGoldCampaign,
    batch: ReviewBatch,
    *,
    manifest_path: Path,
    review_plan_path: Path,
    provenance_registry_path: Path,
    baseline_registry_path: Path,
    leaderboard_policy_path: Path,
    governance_policy_path: Path,
    cache_dir: Path,
    output_dir: Path,
    timeout: float = 300.0,
) -> CampaignActivationResult:
    """Create and activate the first reviewed baseline after real consensus review."""

    status = inspect_campaign(
        campaign,
        manifest_path=manifest_path,
        review_plan_path=review_plan_path,
        provenance_registry_path=provenance_registry_path,
        baseline_registry_path=baseline_registry_path,
        governance_policy_path=governance_policy_path,
        batch=batch,
    )
    if status.state == "strict":
        raise ValueError(f"Campaign {campaign.campaign_id!r} is already strict")
    if not status.ok:
        raise ValueError("Campaign has blocking failures: " + "; ".join(status.failures))
    if not status.ready_for_activation:
        raise ValueError(
            "Campaign is not ready for strict activation: " + "; ".join(status.pending)
        )

    manifest_path = Path(manifest_path).resolve()
    baseline_registry_path = Path(baseline_registry_path).resolve()
    output_dir = Path(output_dir).resolve()
    baseline_path = baseline_registry_path.parent / campaign.baseline_filename
    registry_before = (
        baseline_registry_path.read_bytes()
        if baseline_registry_path.is_file()
        else None
    )
    baseline_before = baseline_path.read_bytes() if baseline_path.is_file() else None

    reviewed_documents = _reviewed_document_ids(manifest_path)
    if not reviewed_documents:
        raise ValueError("Strict activation requires canonical reviewed gold")

    store = CorpusStore(manifest_path, cache_dir)
    benchmark_dir = output_dir / "benchmark"
    report = ParserBenchmarkRunner(store, benchmark_dir).run(
        document_ids=reviewed_documents,
        backends=campaign.benchmark_backends,
        timeout=timeout,
        fetch_missing=True,
    )
    leaderboard_policy = LeaderboardPolicy.load(leaderboard_policy_path)
    if leaderboard_policy.include_draft:
        raise ValueError("Strict campaign activation requires reviewed-only leaderboard")
    leaderboard = build_leaderboard(report, policy=leaderboard_policy)
    leaderboard_json, _ = write_leaderboard(
        leaderboard,
        output_dir / "leaderboard",
    )
    snapshot = build_reviewed_baseline(manifest_path, leaderboard)

    try:
        write_reviewed_baseline(snapshot, baseline_path)
        register_reviewed_baseline(
            baseline_registry_path,
            baseline_path,
            campaign.baseline_id,
            activate=True,
        )
        governance_policy = BenchmarkGovernancePolicy.load(governance_policy_path)
        governance = evaluate_governance(
            manifest_path,
            governance_policy,
            baseline_registry_path,
            provenance_registry_path=provenance_registry_path,
            current_leaderboard=leaderboard,
        )
        if not governance.ok or governance.mode != "strict":
            details = "; ".join(governance.failures) or (
                f"unexpected governance mode {governance.mode!r}"
            )
            raise ValueError("Strict governance activation failed: " + details)
        release = build_governance_release_manifest(
            governance,
            manifest_path=manifest_path,
            policy_path=governance_policy_path,
            baseline_registry_path=baseline_registry_path,
            provenance_registry_path=provenance_registry_path,
        )
        write_governance_outputs(
            governance,
            release,
            output_dir / "governance",
        )
    except Exception:
        if registry_before is None:
            baseline_registry_path.unlink(missing_ok=True)
        else:
            _atomic_write_bytes(baseline_registry_path, registry_before)
        if baseline_before is None:
            baseline_path.unlink(missing_ok=True)
        else:
            _atomic_write_bytes(baseline_path, baseline_before)
        raise

    result = CampaignActivationResult(
        campaign_id=campaign.campaign_id,
        baseline_id=campaign.baseline_id,
        baseline_path=str(baseline_path),
        benchmark_results_path=str(benchmark_dir / "benchmark-results.json"),
        leaderboard_path=str(leaderboard_json),
        governance_status=governance.status,
        governance_mode=governance.mode,
        reviewed_documents=governance.reviewed_documents,
        reviewed_pages=governance.reviewed_pages,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "activation-result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result
