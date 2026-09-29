"""Governance policy and CI gate for reviewed parser accuracy benchmarks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from book.benchmark.baseline import (
    ReviewedBaselineRegistry,
    ReviewedBaselineSnapshot,
    load_active_reviewed_baseline,
)
from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import load_gold_annotation
from book.benchmark.leaderboard import (
    ParserLeaderboard,
    build_leaderboard,
    compare_leaderboards,
    write_leaderboard,
)
from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import (
    ConsensusProvenanceRegistry,
    registry_path_for_manifest,
    sha256_file,
)
from book.benchmark.runner import ParserBenchmarkRunner

GOVERNANCE_SCHEMA_VERSION = "1"
GOVERNANCE_RELEASE_SCHEMA_VERSION = "1"


def _json_hash(value: Dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class BenchmarkGovernancePolicy:
    """Fail-closed requirements for reviewed-gold benchmark governance."""

    ci_backends: Tuple[str, ...] = ("pymupdf",)
    minimum_reviewed_documents: int = 1
    minimum_reviewed_pages: int = 1
    minimum_eligible_ci_backends: int = 1
    minimum_metrics_per_backend: int = 1
    maximum_metric_regression: float = 0.02
    maximum_coverage_drop_documents: int = 0
    maximum_coverage_drop_pages: int = 0
    require_consensus_provenance: bool = True
    require_active_baseline_after_review: bool = True
    schema_version: str = GOVERNANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != GOVERNANCE_SCHEMA_VERSION:
            raise ValueError("Unsupported benchmark governance policy schema")
        if not self.ci_backends:
            raise ValueError("Governance policy requires at least one CI backend")
        if len(self.ci_backends) != len(set(self.ci_backends)):
            raise ValueError("Governance CI backends must be unique")
        integer_fields = (
            self.minimum_reviewed_documents,
            self.minimum_reviewed_pages,
            self.minimum_eligible_ci_backends,
            self.minimum_metrics_per_backend,
            self.maximum_coverage_drop_documents,
            self.maximum_coverage_drop_pages,
        )
        if any(value < 0 for value in integer_fields):
            raise ValueError("Governance coverage values must be >= 0")
        if self.maximum_metric_regression < 0:
            raise ValueError("maximum_metric_regression must be >= 0")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BenchmarkGovernancePolicy":
        return cls(
            schema_version=str(value.get("schema_version", "")),
            ci_backends=tuple(str(item) for item in value.get("ci_backends", [])),
            minimum_reviewed_documents=int(
                value.get("minimum_reviewed_documents", 1)
            ),
            minimum_reviewed_pages=int(value.get("minimum_reviewed_pages", 1)),
            minimum_eligible_ci_backends=int(
                value.get("minimum_eligible_ci_backends", 1)
            ),
            minimum_metrics_per_backend=int(
                value.get("minimum_metrics_per_backend", 1)
            ),
            maximum_metric_regression=float(
                value.get("maximum_metric_regression", 0.02)
            ),
            maximum_coverage_drop_documents=int(
                value.get("maximum_coverage_drop_documents", 0)
            ),
            maximum_coverage_drop_pages=int(
                value.get("maximum_coverage_drop_pages", 0)
            ),
            require_consensus_provenance=bool(
                value.get("require_consensus_provenance", True)
            ),
            require_active_baseline_after_review=bool(
                value.get("require_active_baseline_after_review", True)
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "BenchmarkGovernancePolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Governance policy root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ci_backends": list(self.ci_backends),
            "minimum_reviewed_documents": self.minimum_reviewed_documents,
            "minimum_reviewed_pages": self.minimum_reviewed_pages,
            "minimum_eligible_ci_backends": self.minimum_eligible_ci_backends,
            "minimum_metrics_per_backend": self.minimum_metrics_per_backend,
            "maximum_metric_regression": self.maximum_metric_regression,
            "maximum_coverage_drop_documents": self.maximum_coverage_drop_documents,
            "maximum_coverage_drop_pages": self.maximum_coverage_drop_pages,
            "require_consensus_provenance": self.require_consensus_provenance,
            "require_active_baseline_after_review": (
                self.require_active_baseline_after_review
            ),
        }


@dataclass(frozen=True)
class BenchmarkGovernanceReport:
    corpus_id: str
    mode: str
    status: str
    reviewed_documents: int
    reviewed_pages: int
    reviewed_gold_sha256: Dict[str, str]
    provenance_documents: int
    active_baseline_id: Optional[str]
    tracked_ci_backends: Tuple[str, ...]
    failures: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    current_leaderboard: Optional[Dict[str, Any]] = None
    schema_version: str = GOVERNANCE_SCHEMA_VERSION

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "mode": self.mode,
            "status": self.status,
            "reviewed_documents": self.reviewed_documents,
            "reviewed_pages": self.reviewed_pages,
            "reviewed_gold_sha256": dict(sorted(self.reviewed_gold_sha256.items())),
            "provenance_documents": self.provenance_documents,
            "active_baseline_id": self.active_baseline_id,
            "tracked_ci_backends": list(self.tracked_ci_backends),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "current_leaderboard": self.current_leaderboard,
        }


@dataclass(frozen=True)
class GovernanceReleaseManifest:
    corpus_id: str
    governance_mode: str
    governance_status: str
    manifest_sha256: str
    policy_sha256: str
    provenance_registry_sha256: Optional[str]
    baseline_registry_sha256: Optional[str]
    active_baseline_id: Optional[str]
    active_baseline_sha256: Optional[str]
    reviewed_gold_sha256: Dict[str, str]
    governance_report_sha256: str
    created_at: str
    schema_version: str = GOVERNANCE_RELEASE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "governance_mode": self.governance_mode,
            "governance_status": self.governance_status,
            "manifest_sha256": self.manifest_sha256,
            "policy_sha256": self.policy_sha256,
            "provenance_registry_sha256": self.provenance_registry_sha256,
            "baseline_registry_sha256": self.baseline_registry_sha256,
            "active_baseline_id": self.active_baseline_id,
            "active_baseline_sha256": self.active_baseline_sha256,
            "reviewed_gold_sha256": dict(sorted(self.reviewed_gold_sha256.items())),
            "governance_report_sha256": self.governance_report_sha256,
            "created_at": self.created_at,
        }


def _reviewed_inventory(
    manifest_path: Path,
) -> Tuple[CorpusManifest, Dict[str, str], Dict[str, Tuple[int, ...]]]:
    manifest_path = Path(manifest_path).resolve()
    manifest = CorpusManifest.load(manifest_path)
    root = manifest_path.parent
    gold_sha256: Dict[str, str] = {}
    pages: Dict[str, Tuple[int, ...]] = {}
    for spec in manifest.documents:
        annotation = load_gold_annotation(manifest_path, spec)
        if annotation is None or annotation.status != "reviewed":
            continue
        if not spec.gold_annotations_path:
            raise ValueError(
                f"Reviewed gold {spec.id} is missing gold_annotations_path"
            )
        gold_path = (root / spec.gold_annotations_path).resolve()
        gold_sha256[spec.id] = sha256_file(gold_path)
        pages[spec.id] = tuple(sorted(page.page_index for page in annotation.pages))
    return manifest, gold_sha256, pages


def _validate_provenance(
    manifest_path: Path,
    manifest: CorpusManifest,
    reviewed_gold: Dict[str, str],
    reviewed_pages: Dict[str, Tuple[int, ...]],
    registry: ConsensusProvenanceRegistry,
) -> List[str]:
    failures: List[str] = []
    corpus_root = Path(manifest_path).resolve().parent
    spec_by_id = {spec.id: spec for spec in manifest.documents}
    for record in registry.records:
        if record.document_id not in spec_by_id:
            failures.append(
                f"provenance references unknown document {record.document_id}"
            )
        elif record.document_id not in reviewed_gold:
            failures.append(
                f"provenance exists for non-reviewed document {record.document_id}"
            )

    for document_id, gold_digest in reviewed_gold.items():
        spec = spec_by_id[document_id]
        record = registry.document(document_id)
        if record is None:
            failures.append(
                f"reviewed document {document_id} has no consensus provenance record"
            )
            continue
        if record.source_sha256 != spec.sha256:
            failures.append(
                f"{document_id}: provenance source SHA does not match corpus manifest"
            )
        if record.current_gold_sha256 != gold_digest:
            failures.append(
                f"{document_id}: provenance current gold SHA does not match canonical gold"
            )
        latest_by_page: Dict[int, Any] = {}
        for review in record.reviews:
            previous = latest_by_page.get(review.page_index)
            if previous is None or review.published_at > previous.published_at:
                latest_by_page[review.page_index] = review

        for page_index in reviewed_pages[document_id]:
            review = latest_by_page.get(page_index)
            if review is None:
                failures.append(
                    f"{document_id} page {page_index}: missing consensus review provenance"
                )
                continue
            audit_path = (corpus_root / review.audit_path).resolve()
            try:
                audit_path.relative_to(corpus_root)
            except ValueError:
                failures.append(
                    f"{document_id} page {page_index}: audit path escapes corpus directory"
                )
                continue
            if not audit_path.is_file():
                failures.append(
                    f"{document_id} page {page_index}: consensus audit file is missing"
                )
                continue
            if sha256_file(audit_path) != review.audit_sha256:
                failures.append(
                    f"{document_id} page {page_index}: consensus audit SHA mismatch"
                )
                continue
            try:
                audit = json.loads(audit_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                failures.append(
                    f"{document_id} page {page_index}: consensus audit is unreadable"
                )
                continue
            if not isinstance(audit, dict):
                failures.append(
                    f"{document_id} page {page_index}: consensus audit root is invalid"
                )
                continue
            checks = {
                "document_id": document_id,
                "page_index": page_index,
                "source_sha256": spec.sha256,
                "bundle_id": review.consensus_bundle_id,
                "published_at": review.published_at,
            }
            for key, expected in checks.items():
                if audit.get(key) != expected:
                    failures.append(
                        f"{document_id} page {page_index}: audit {key} mismatch"
                    )
            if audit.get("reviewer_a") == audit.get("reviewer_b"):
                failures.append(
                    f"{document_id} page {page_index}: provenance reviewers are not independent"
                )
    return failures


def evaluate_governance(
    manifest_path: Path,
    policy: BenchmarkGovernancePolicy,
    baseline_registry_path: Path,
    *,
    provenance_registry_path: Optional[Path] = None,
    current_leaderboard: Optional[ParserLeaderboard] = None,
) -> BenchmarkGovernanceReport:
    """Evaluate bootstrap/strict benchmark governance without hiding missing assets."""

    manifest_path = Path(manifest_path).resolve()
    baseline_registry_path = Path(baseline_registry_path).resolve()
    provenance_registry_path = (
        Path(provenance_registry_path).resolve()
        if provenance_registry_path is not None
        else registry_path_for_manifest(manifest_path)
    )
    failures: List[str] = []
    warnings: List[str] = []

    manifest, reviewed_gold, reviewed_pages = _reviewed_inventory(manifest_path)
    reviewed_document_count = len(reviewed_gold)
    reviewed_page_count = sum(len(items) for items in reviewed_pages.values())

    provenance = ConsensusProvenanceRegistry.load(provenance_registry_path)
    if policy.require_consensus_provenance:
        failures.extend(
            _validate_provenance(
                manifest_path,
                manifest,
                reviewed_gold,
                reviewed_pages,
                provenance,
            )
        )

    try:
        baseline_registry = ReviewedBaselineRegistry.load(baseline_registry_path)
        active_snapshot = load_active_reviewed_baseline(baseline_registry_path)
    except ValueError as exc:
        baseline_registry = ReviewedBaselineRegistry()
        active_snapshot = None
        failures.append(str(exc))

    active_id = baseline_registry.active_baseline_id
    mode = "strict" if active_snapshot is not None else "bootstrap"
    tracked_ci_backends: Tuple[str, ...] = ()

    if reviewed_document_count == 0:
        if active_snapshot is not None:
            failures.append("active baseline exists but canonical reviewed gold is empty")
        warnings.append(
            "bootstrap: no canonical reviewed gold exists yet; accuracy execution is dormant"
        )
    else:
        if reviewed_document_count < policy.minimum_reviewed_documents:
            failures.append(
                "reviewed document coverage "
                f"{reviewed_document_count} < {policy.minimum_reviewed_documents}"
            )
        if reviewed_page_count < policy.minimum_reviewed_pages:
            failures.append(
                f"reviewed page coverage {reviewed_page_count} < "
                f"{policy.minimum_reviewed_pages}"
            )
        if (
            policy.require_active_baseline_after_review
            and active_snapshot is None
        ):
            failures.append(
                "canonical reviewed gold exists but no active reviewed baseline is registered"
            )

    if active_snapshot is not None:
        if active_snapshot.corpus_id != manifest.corpus_id:
            failures.append("active baseline corpus_id does not match manifest")
        if active_snapshot.manifest_sha256 != sha256_file(manifest_path):
            failures.append("active baseline manifest SHA is stale")
        if active_snapshot.gold_sha256 != reviewed_gold:
            failures.append("active baseline reviewed-gold SHA set is stale")
        if active_snapshot.leaderboard.policy.include_draft:
            failures.append("active baseline must be reviewed-only")

        baseline_entries = {
            entry.backend: entry
            for entry in active_snapshot.leaderboard.entries
            if entry.eligible and entry.backend in set(policy.ci_backends)
        }
        tracked_ci_backends = tuple(
            backend for backend in policy.ci_backends if backend in baseline_entries
        )
        if len(tracked_ci_backends) < policy.minimum_eligible_ci_backends:
            failures.append(
                "eligible CI backend coverage "
                f"{len(tracked_ci_backends)} < {policy.minimum_eligible_ci_backends}"
            )
        for backend in tracked_ci_backends:
            entry = baseline_entries[backend]
            if entry.annotated_documents < policy.minimum_reviewed_documents:
                failures.append(
                    f"{backend}: baseline reviewed document coverage below governance floor"
                )
            if entry.annotated_pages < policy.minimum_reviewed_pages:
                failures.append(
                    f"{backend}: baseline reviewed page coverage below governance floor"
                )
            if entry.evaluated_metric_count < policy.minimum_metrics_per_backend:
                failures.append(
                    f"{backend}: baseline evaluated metric count "
                    f"{entry.evaluated_metric_count} < "
                    f"{policy.minimum_metrics_per_backend}"
                )

        if current_leaderboard is None:
            warnings.append(
                "strict baseline is active but no current leaderboard was supplied"
            )
        else:
            if current_leaderboard.corpus_id != manifest.corpus_id:
                failures.append("current leaderboard corpus_id does not match manifest")
            if current_leaderboard.policy.include_draft:
                failures.append("current governance leaderboard must be reviewed-only")
            current_by_backend = {
                entry.backend: entry for entry in current_leaderboard.entries
            }
            for backend in tracked_ci_backends:
                before = baseline_entries[backend]
                current = current_by_backend.get(backend)
                if current is None or not current.eligible:
                    failures.append(
                        f"{backend}: current reviewed-gold leaderboard is not eligible"
                    )
                    continue
                document_drop = before.annotated_documents - current.annotated_documents
                page_drop = before.annotated_pages - current.annotated_pages
                if document_drop > policy.maximum_coverage_drop_documents:
                    failures.append(
                        f"{backend}: reviewed document coverage drop {document_drop} > "
                        f"{policy.maximum_coverage_drop_documents}"
                    )
                if page_drop > policy.maximum_coverage_drop_pages:
                    failures.append(
                        f"{backend}: reviewed page coverage drop {page_drop} > "
                        f"{policy.maximum_coverage_drop_pages}"
                    )
                if current.evaluated_metric_count < policy.minimum_metrics_per_backend:
                    failures.append(
                        f"{backend}: current evaluated metric count "
                        f"{current.evaluated_metric_count} < "
                        f"{policy.minimum_metrics_per_backend}"
                    )
            failures.extend(
                compare_leaderboards(
                    current_leaderboard,
                    active_snapshot.leaderboard,
                    maximum_metric_regression=policy.maximum_metric_regression,
                )
            )

    status = "pass" if not failures else "fail"
    return BenchmarkGovernanceReport(
        corpus_id=manifest.corpus_id,
        mode=mode,
        status=status,
        reviewed_documents=reviewed_document_count,
        reviewed_pages=reviewed_page_count,
        reviewed_gold_sha256=reviewed_gold,
        provenance_documents=len(provenance.records),
        active_baseline_id=active_id,
        tracked_ci_backends=tracked_ci_backends,
        failures=tuple(sorted(set(failures))),
        warnings=tuple(sorted(set(warnings))),
        current_leaderboard=(
            current_leaderboard.to_dict()
            if current_leaderboard is not None
            else None
        ),
    )


def render_governance_markdown(report: BenchmarkGovernanceReport) -> str:
    lines = [
        "# Reviewed Accuracy Governance",
        "",
        f"- Corpus: `{report.corpus_id}`",
        f"- Mode: **{report.mode}**",
        f"- Status: **{report.status}**",
        f"- Reviewed documents: {report.reviewed_documents}",
        f"- Reviewed pages: {report.reviewed_pages}",
        f"- Provenance documents: {report.provenance_documents}",
        f"- Active baseline: `{report.active_baseline_id or 'none'}`",
        (
            "- CI backends: "
            + (
                ", ".join(f"`{item}`" for item in report.tracked_ci_backends)
                if report.tracked_ci_backends
                else "none"
            )
        ),
        "",
    ]
    if report.failures:
        lines.extend(["## Failures", ""])
        lines.extend(f"- {item}" for item in report.failures)
        lines.append("")
    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in report.warnings)
        lines.append("")
    return "\n".join(lines)


def build_governance_release_manifest(
    report: BenchmarkGovernanceReport,
    *,
    manifest_path: Path,
    policy_path: Path,
    baseline_registry_path: Path,
    provenance_registry_path: Optional[Path] = None,
) -> GovernanceReleaseManifest:
    manifest_path = Path(manifest_path).resolve()
    policy_path = Path(policy_path).resolve()
    baseline_registry_path = Path(baseline_registry_path).resolve()
    provenance_registry_path = (
        Path(provenance_registry_path).resolve()
        if provenance_registry_path is not None
        else registry_path_for_manifest(manifest_path)
    )
    baseline_registry = ReviewedBaselineRegistry.load(baseline_registry_path)
    active_sha: Optional[str] = None
    if baseline_registry.active_baseline_id is not None:
        version = baseline_registry.get(baseline_registry.active_baseline_id)
        active_path = (baseline_registry_path.parent / version.path).resolve()
        if active_path.is_file():
            active_sha = sha256_file(active_path)
    return GovernanceReleaseManifest(
        corpus_id=report.corpus_id,
        governance_mode=report.mode,
        governance_status=report.status,
        manifest_sha256=sha256_file(manifest_path),
        policy_sha256=sha256_file(policy_path),
        provenance_registry_sha256=(
            sha256_file(provenance_registry_path)
            if provenance_registry_path.is_file()
            else None
        ),
        baseline_registry_sha256=(
            sha256_file(baseline_registry_path)
            if baseline_registry_path.is_file()
            else None
        ),
        active_baseline_id=baseline_registry.active_baseline_id,
        active_baseline_sha256=active_sha,
        reviewed_gold_sha256=report.reviewed_gold_sha256,
        governance_report_sha256=_json_hash(report.to_dict()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def write_governance_outputs(
    report: BenchmarkGovernanceReport,
    release_manifest: GovernanceReleaseManifest,
    output_dir: Path,
) -> Tuple[Path, Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "governance-report.json"
    markdown_path = output_dir / "governance-report.md"
    release_path = output_dir / "governance-release.json"
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_governance_markdown(report), encoding="utf-8")
    release_path.write_text(
        json.dumps(release_manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path, markdown_path, release_path


def run_governed_accuracy_ci(
    *,
    manifest_path: Path,
    policy_path: Path,
    baseline_registry_path: Path,
    output_dir: Path,
    cache_dir: Path,
    provenance_registry_path: Optional[Path] = None,
    timeout: float = 300.0,
) -> BenchmarkGovernanceReport:
    """Run bootstrap validation or strict reviewed-gold parser regression in CI."""

    policy = BenchmarkGovernancePolicy.load(policy_path)
    static_report = evaluate_governance(
        manifest_path,
        policy,
        baseline_registry_path,
        provenance_registry_path=provenance_registry_path,
    )
    if not static_report.ok:
        release = build_governance_release_manifest(
            static_report,
            manifest_path=manifest_path,
            policy_path=policy_path,
            baseline_registry_path=baseline_registry_path,
            provenance_registry_path=provenance_registry_path,
        )
        write_governance_outputs(static_report, release, output_dir)
        return static_report

    active_snapshot = load_active_reviewed_baseline(baseline_registry_path)
    if active_snapshot is None:
        release = build_governance_release_manifest(
            static_report,
            manifest_path=manifest_path,
            policy_path=policy_path,
            baseline_registry_path=baseline_registry_path,
            provenance_registry_path=provenance_registry_path,
        )
        write_governance_outputs(static_report, release, output_dir)
        return static_report

    tracked = [
        entry.backend
        for entry in active_snapshot.leaderboard.entries
        if entry.eligible and entry.backend in set(policy.ci_backends)
    ]
    document_ids = sorted(active_snapshot.gold_sha256)
    benchmark_dir = Path(output_dir) / "benchmark"
    store = CorpusStore(manifest_path, cache_dir)
    benchmark = ParserBenchmarkRunner(store, benchmark_dir)
    result = benchmark.run(
        document_ids=document_ids,
        backends=tracked,
        timeout=timeout,
        fetch_missing=True,
    )
    current = build_leaderboard(
        result,
        policy=active_snapshot.leaderboard.policy,
    )
    write_leaderboard(current, Path(output_dir) / "leaderboard")
    final_report = evaluate_governance(
        manifest_path,
        policy,
        baseline_registry_path,
        provenance_registry_path=provenance_registry_path,
        current_leaderboard=current,
    )
    release = build_governance_release_manifest(
        final_report,
        manifest_path=manifest_path,
        policy_path=policy_path,
        baseline_registry_path=baseline_registry_path,
        provenance_registry_path=provenance_registry_path,
    )
    write_governance_outputs(final_report, release, output_dir)
    return final_report
