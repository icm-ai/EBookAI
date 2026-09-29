"""Occam-oriented runtime ablation pilot models, readiness, and decisions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from book.benchmark.gold import load_gold_annotation
from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import ConsensusProvenanceRegistry
from book.benchmark.review_plan import ReviewPlan, validate_review_plan

ABLATION_SCHEMA_VERSION = "1"
_ALLOWED_VARIANTS = ("A", "B", "C", "D")
_ALLOWED_STATUSES = {"success", "failed", "timeout", "skipped"}
_ALLOWED_VERDICTS = {
    "keep",
    "optional",
    "remove_candidate",
    "insufficient_evidence",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class AblationTarget:
    document_id: str
    page_index: int
    bucket: str

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("Ablation target document_id must not be empty")
        if self.page_index < 0:
            raise ValueError("Ablation target page_index must be >= 0")
        if not self.bucket.strip():
            raise ValueError("Ablation target bucket must not be empty")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationTarget":
        return cls(
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
            bucket=str(value["bucket"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page_index": self.page_index,
            "bucket": self.bucket,
        }


@dataclass(frozen=True)
class AblationVariant:
    id: str
    label: str
    added_component: str
    components: Tuple[str, ...]
    complexity_rank: int

    def __post_init__(self) -> None:
        if self.id not in _ALLOWED_VARIANTS:
            raise ValueError(f"Unsupported ablation variant: {self.id!r}")
        if not self.label.strip():
            raise ValueError("Ablation variant label must not be empty")
        if not self.added_component.strip():
            raise ValueError("Ablation variant added_component must not be empty")
        if self.complexity_rank < 1:
            raise ValueError("Ablation variant complexity_rank must be >= 1")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationVariant":
        return cls(
            id=str(value["id"]),
            label=str(value["label"]),
            added_component=str(value["added_component"]),
            components=tuple(str(item) for item in value.get("components", [])),
            complexity_rank=int(value["complexity_rank"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "added_component": self.added_component,
            "components": list(self.components),
            "complexity_rank": self.complexity_rank,
        }


@dataclass(frozen=True)
class AblationDecisionPolicy:
    minimum_reviewed_pages: int = 8
    required_buckets: Tuple[str, ...] = ()
    minimum_quality_gain_to_keep: float = 0.01
    negligible_quality_gain: float = 0.002
    maximum_latency_multiplier: float = 1.5
    maximum_failure_rate_increase: float = 0.0
    minimum_review_burden_reduction: float = 0.10
    require_human_minutes_for_final: bool = True

    def __post_init__(self) -> None:
        if self.minimum_reviewed_pages < 1:
            raise ValueError("minimum_reviewed_pages must be >= 1")
        if self.minimum_quality_gain_to_keep < 0:
            raise ValueError("minimum_quality_gain_to_keep must be >= 0")
        if self.negligible_quality_gain < 0:
            raise ValueError("negligible_quality_gain must be >= 0")
        if self.negligible_quality_gain > self.minimum_quality_gain_to_keep:
            raise ValueError(
                "negligible_quality_gain must not exceed minimum_quality_gain_to_keep"
            )
        if self.maximum_latency_multiplier < 1:
            raise ValueError("maximum_latency_multiplier must be >= 1")
        if self.maximum_failure_rate_increase < 0:
            raise ValueError("maximum_failure_rate_increase must be >= 0")
        if not 0 <= self.minimum_review_burden_reduction <= 1:
            raise ValueError("minimum_review_burden_reduction must be in [0, 1]")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationDecisionPolicy":
        return cls(
            minimum_reviewed_pages=int(value.get("minimum_reviewed_pages", 8)),
            required_buckets=tuple(
                str(item) for item in value.get("required_buckets", [])
            ),
            minimum_quality_gain_to_keep=float(
                value.get("minimum_quality_gain_to_keep", 0.01)
            ),
            negligible_quality_gain=float(value.get("negligible_quality_gain", 0.002)),
            maximum_latency_multiplier=float(
                value.get("maximum_latency_multiplier", 1.5)
            ),
            maximum_failure_rate_increase=float(
                value.get("maximum_failure_rate_increase", 0.0)
            ),
            minimum_review_burden_reduction=float(
                value.get("minimum_review_burden_reduction", 0.10)
            ),
            require_human_minutes_for_final=bool(
                value.get("require_human_minutes_for_final", True)
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minimum_reviewed_pages": self.minimum_reviewed_pages,
            "required_buckets": list(self.required_buckets),
            "minimum_quality_gain_to_keep": self.minimum_quality_gain_to_keep,
            "negligible_quality_gain": self.negligible_quality_gain,
            "maximum_latency_multiplier": self.maximum_latency_multiplier,
            "maximum_failure_rate_increase": self.maximum_failure_rate_increase,
            "minimum_review_burden_reduction": self.minimum_review_burden_reduction,
            "require_human_minutes_for_final": self.require_human_minutes_for_final,
        }


@dataclass(frozen=True)
class AblationPilotSpec:
    pilot_id: str
    corpus_id: str
    targets: Tuple[AblationTarget, ...]
    variants: Tuple[AblationVariant, ...]
    quality_metric_paths: Tuple[str, ...]
    decision_policy: AblationDecisionPolicy
    description: str = ""
    schema_version: str = ABLATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ABLATION_SCHEMA_VERSION:
            raise ValueError("Unsupported ablation pilot schema")
        if not _ID_RE.fullmatch(self.pilot_id):
            raise ValueError(f"Invalid ablation pilot id: {self.pilot_id!r}")
        if not self.corpus_id.strip():
            raise ValueError("Ablation pilot corpus_id must not be empty")
        if not self.targets:
            raise ValueError("Ablation pilot requires at least one target")
        target_keys = [(item.document_id, item.page_index) for item in self.targets]
        if len(target_keys) != len(set(target_keys)):
            raise ValueError("Ablation pilot contains duplicate document/page targets")
        if not self.variants:
            raise ValueError("Ablation pilot requires variants")
        variant_ids = [item.id for item in self.variants]
        if variant_ids != list(_ALLOWED_VARIANTS):
            raise ValueError("Ablation variants must be ordered exactly A, B, C, D")
        ranks = [item.complexity_rank for item in self.variants]
        if ranks != sorted(ranks) or len(ranks) != len(set(ranks)):
            raise ValueError("Ablation variant complexity ranks must strictly increase")
        if not self.quality_metric_paths:
            raise ValueError("Ablation pilot requires at least one quality metric")
        target_buckets = {item.bucket for item in self.targets}
        missing_buckets = set(self.decision_policy.required_buckets) - target_buckets
        if missing_buckets:
            raise ValueError(
                "Ablation pilot targets do not cover required buckets: "
                + ", ".join(sorted(missing_buckets))
            )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationPilotSpec":
        targets = value.get("targets")
        variants = value.get("variants")
        if not isinstance(targets, list):
            raise ValueError("Ablation pilot targets must be a list")
        if not isinstance(variants, list):
            raise ValueError("Ablation pilot variants must be a list")
        policy = value.get("decision_policy")
        if not isinstance(policy, dict):
            raise ValueError("Ablation pilot decision_policy must be an object")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            pilot_id=str(value["pilot_id"]),
            corpus_id=str(value["corpus_id"]),
            description=str(value.get("description", "")),
            targets=tuple(AblationTarget.from_dict(item) for item in targets),
            variants=tuple(AblationVariant.from_dict(item) for item in variants),
            quality_metric_paths=tuple(
                str(item) for item in value.get("quality_metric_paths", [])
            ),
            decision_policy=AblationDecisionPolicy.from_dict(policy),
        )

    @classmethod
    def load(cls, path: Path) -> "AblationPilotSpec":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Ablation pilot root must be an object")
        return cls.from_dict(payload)

    def variant(self, variant_id: str) -> AblationVariant:
        for item in self.variants:
            if item.id == variant_id:
                return item
        raise KeyError(f"Unknown ablation variant: {variant_id}")

    def target_keys(self) -> Set[Tuple[str, int]]:
        return {(item.document_id, item.page_index) for item in self.targets}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pilot_id": self.pilot_id,
            "corpus_id": self.corpus_id,
            "description": self.description,
            "targets": [item.to_dict() for item in self.targets],
            "variants": [item.to_dict() for item in self.variants],
            "quality_metric_paths": list(self.quality_metric_paths),
            "decision_policy": self.decision_policy.to_dict(),
        }


@dataclass(frozen=True)
class AblationReadiness:
    pilot_id: str
    state: str
    reviewed_pages: int
    target_pages: int
    reviewed_buckets: Tuple[str, ...]
    required_buckets: Tuple[str, ...]
    ready_targets: Tuple[Tuple[str, int], ...]
    pending_targets: Tuple[Tuple[str, int], ...]
    failures: Tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def ready(self) -> bool:
        return self.ok and self.state == "ready"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "state": self.state,
            "reviewed_pages": self.reviewed_pages,
            "target_pages": self.target_pages,
            "reviewed_buckets": list(self.reviewed_buckets),
            "required_buckets": list(self.required_buckets),
            "ready_targets": [
                {"document_id": document_id, "page_index": page_index}
                for document_id, page_index in self.ready_targets
            ],
            "pending_targets": [
                {"document_id": document_id, "page_index": page_index}
                for document_id, page_index in self.pending_targets
            ],
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class AblationObservation:
    variant_id: str
    document_id: str
    page_indexes: Tuple[int, ...]
    status: str
    elapsed_seconds: float
    quality_macro: Optional[float] = None
    metric_values: Dict[str, float] = field(default_factory=dict)
    review_issue_count: int = 0
    manual_review_minutes: Optional[float] = None
    ai_cost_usd: Optional[float] = None
    intervention_count: int = 0
    selected_parser: Optional[str] = None
    parser_attempts: int = 0
    valid_for_decision: bool = True
    invalid_reason: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.variant_id not in _ALLOWED_VARIANTS:
            raise ValueError(f"Unsupported observation variant: {self.variant_id!r}")
        if not self.document_id.strip():
            raise ValueError("Ablation observation document_id must not be empty")
        if not self.page_indexes:
            raise ValueError("Ablation observation requires at least one page")
        if len(self.page_indexes) != len(set(self.page_indexes)):
            raise ValueError("Ablation observation pages must be unique")
        if any(page < 0 for page in self.page_indexes):
            raise ValueError("Ablation observation page indexes must be >= 0")
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unsupported ablation status: {self.status!r}")
        if self.elapsed_seconds < 0:
            raise ValueError("Ablation elapsed_seconds must be >= 0")
        if self.quality_macro is not None and not 0 <= self.quality_macro <= 1:
            raise ValueError("Ablation quality_macro must be in [0, 1]")
        if self.review_issue_count < 0 or self.intervention_count < 0:
            raise ValueError("Ablation counts must be >= 0")
        if self.manual_review_minutes is not None and self.manual_review_minutes < 0:
            raise ValueError("manual_review_minutes must be >= 0")
        if self.ai_cost_usd is not None and self.ai_cost_usd < 0:
            raise ValueError("ai_cost_usd must be >= 0")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationObservation":
        return cls(
            variant_id=str(value["variant_id"]),
            document_id=str(value["document_id"]),
            page_indexes=tuple(int(item) for item in value.get("page_indexes", [])),
            status=str(value["status"]),
            elapsed_seconds=float(value.get("elapsed_seconds", 0.0)),
            quality_macro=(
                float(value["quality_macro"])
                if value.get("quality_macro") is not None
                else None
            ),
            metric_values={
                str(key): float(metric)
                for key, metric in dict(value.get("metric_values", {})).items()
            },
            review_issue_count=int(value.get("review_issue_count", 0)),
            manual_review_minutes=(
                float(value["manual_review_minutes"])
                if value.get("manual_review_minutes") is not None
                else None
            ),
            ai_cost_usd=(
                float(value["ai_cost_usd"])
                if value.get("ai_cost_usd") is not None
                else None
            ),
            intervention_count=int(value.get("intervention_count", 0)),
            selected_parser=(
                str(value["selected_parser"])
                if value.get("selected_parser") is not None
                else None
            ),
            parser_attempts=int(value.get("parser_attempts", 0)),
            valid_for_decision=bool(value.get("valid_for_decision", True)),
            invalid_reason=str(value.get("invalid_reason", "")),
            error=str(value.get("error", "")),
        )

    def page_keys(self) -> Set[Tuple[str, int]]:
        return {(self.document_id, page) for page in self.page_indexes}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "document_id": self.document_id,
            "page_indexes": list(self.page_indexes),
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "quality_macro": self.quality_macro,
            "metric_values": dict(sorted(self.metric_values.items())),
            "review_issue_count": self.review_issue_count,
            "manual_review_minutes": self.manual_review_minutes,
            "ai_cost_usd": self.ai_cost_usd,
            "intervention_count": self.intervention_count,
            "selected_parser": self.selected_parser,
            "parser_attempts": self.parser_attempts,
            "valid_for_decision": self.valid_for_decision,
            "invalid_reason": self.invalid_reason,
            "error": self.error,
        }


@dataclass(frozen=True)
class AblationRunArtifact:
    pilot_id: str
    corpus_id: str
    observations: Tuple[AblationObservation, ...]
    source: str = "local"
    schema_version: str = ABLATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ABLATION_SCHEMA_VERSION:
            raise ValueError("Unsupported ablation run schema")
        keys = [(item.variant_id, item.document_id) for item in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "Ablation run contains duplicate variant/document observations"
            )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AblationRunArtifact":
        observations = value.get("observations")
        if not isinstance(observations, list):
            raise ValueError("Ablation run observations must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            pilot_id=str(value["pilot_id"]),
            corpus_id=str(value["corpus_id"]),
            source=str(value.get("source", "external")),
            observations=tuple(
                AblationObservation.from_dict(item) for item in observations
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "AblationRunArtifact":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Ablation run root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pilot_id": self.pilot_id,
            "corpus_id": self.corpus_id,
            "source": self.source,
            "observations": [item.to_dict() for item in self.observations],
        }

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path


@dataclass(frozen=True)
class VariantAggregate:
    variant_id: str
    attempted_pages: int
    failed_pages: int
    invalid_pages: int
    quality_macro: float
    failure_rate: float
    elapsed_seconds_per_page: float
    review_issues_per_page: Optional[float]
    manual_review_minutes_per_page: Optional[float]
    ai_cost_usd_per_page: Optional[float]
    interventions_per_page: Optional[float]
    selected_parsers: Tuple[str, ...]
    page_keys: Tuple[Tuple[str, int], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "attempted_pages": self.attempted_pages,
            "failed_pages": self.failed_pages,
            "invalid_pages": self.invalid_pages,
            "quality_macro": self.quality_macro,
            "failure_rate": self.failure_rate,
            "elapsed_seconds_per_page": self.elapsed_seconds_per_page,
            "review_issues_per_page": self.review_issues_per_page,
            "manual_review_minutes_per_page": self.manual_review_minutes_per_page,
            "ai_cost_usd_per_page": self.ai_cost_usd_per_page,
            "interventions_per_page": self.interventions_per_page,
            "selected_parsers": list(self.selected_parsers),
            "page_keys": [
                {"document_id": document_id, "page_index": page_index}
                for document_id, page_index in self.page_keys
            ],
        }


@dataclass(frozen=True)
class AblationDecision:
    from_variant: str
    to_variant: str
    component: str
    verdict: str
    confidence: str
    quality_gain: Optional[float]
    latency_multiplier: Optional[float]
    failure_rate_delta: Optional[float]
    review_burden_reduction: Optional[float]
    manual_minutes_reduction: Optional[float]
    ai_cost_delta_per_page: Optional[float]
    reasons: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.verdict not in _ALLOWED_VERDICTS:
            raise ValueError(f"Unsupported ablation verdict: {self.verdict!r}")
        if self.confidence not in {"provisional", "decision_ready"}:
            raise ValueError(f"Unsupported ablation confidence: {self.confidence!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_variant": self.from_variant,
            "to_variant": self.to_variant,
            "component": self.component,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "quality_gain": self.quality_gain,
            "latency_multiplier": self.latency_multiplier,
            "failure_rate_delta": self.failure_rate_delta,
            "review_burden_reduction": self.review_burden_reduction,
            "manual_minutes_reduction": self.manual_minutes_reduction,
            "ai_cost_delta_per_page": self.ai_cost_delta_per_page,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AblationReport:
    pilot_id: str
    readiness: AblationReadiness
    aggregates: Tuple[VariantAggregate, ...]
    decisions: Tuple[AblationDecision, ...]
    conclusion_ready: bool
    schema_version: str = ABLATION_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pilot_id": self.pilot_id,
            "readiness": self.readiness.to_dict(),
            "aggregates": [item.to_dict() for item in self.aggregates],
            "decisions": [item.to_dict() for item in self.decisions],
            "conclusion_ready": self.conclusion_ready,
        }


def validate_pilot(
    spec: AblationPilotSpec,
    manifest: CorpusManifest,
    plan: ReviewPlan,
) -> None:
    validate_review_plan(plan, manifest)
    if spec.corpus_id != manifest.corpus_id:
        raise ValueError(
            f"Ablation corpus_id {spec.corpus_id!r} does not match "
            f"manifest {manifest.corpus_id!r}"
        )
    plan_targets = {
        (target.document_id, target.page_index): target for target in plan.targets
    }
    failures = []
    for target in spec.targets:
        if (target.document_id, target.page_index) not in plan_targets:
            failures.append(
                f"{target.document_id} page {target.page_index} is not in review plan"
            )
    if failures:
        raise ValueError("; ".join(sorted(failures)))


def inspect_ablation_readiness(
    spec: AblationPilotSpec,
    *,
    manifest_path: Path,
    review_plan_path: Path,
    provenance_registry_path: Path,
) -> AblationReadiness:
    manifest_path = Path(manifest_path).resolve()
    manifest = CorpusManifest.load(manifest_path)
    plan = ReviewPlan.load(review_plan_path)
    validate_pilot(spec, manifest, plan)
    provenance = ConsensusProvenanceRegistry.load(provenance_registry_path)
    by_id = {item.id: item for item in manifest.documents}

    failures: List[str] = []
    ready: List[Tuple[str, int]] = []
    pending: List[Tuple[str, int]] = []
    reviewed_buckets: Set[str] = set()
    annotation_cache: Dict[str, Any] = {}

    for target in spec.targets:
        corpus_spec = by_id[target.document_id]
        if target.document_id not in annotation_cache:
            annotation_cache[target.document_id] = load_gold_annotation(
                manifest_path,
                corpus_spec,
            )
        annotation = annotation_cache[target.document_id]
        page_indexes = (
            {page.page_index for page in annotation.pages}
            if annotation is not None
            else set()
        )
        canonical_reviewed = (
            annotation is not None
            and annotation.status == "reviewed"
            and target.page_index in page_indexes
        )
        record = provenance.document(target.document_id)
        has_provenance = record is not None and any(
            item.page_index == target.page_index for item in record.reviews
        )
        if canonical_reviewed != has_provenance:
            failures.append(
                f"{target.document_id} page {target.page_index}: reviewed gold and "
                "consensus provenance disagree"
            )
        if canonical_reviewed and has_provenance:
            ready.append((target.document_id, target.page_index))
            reviewed_buckets.add(target.bucket)
        else:
            pending.append((target.document_id, target.page_index))

    required_buckets = set(spec.decision_policy.required_buckets)
    enough_pages = len(ready) >= spec.decision_policy.minimum_reviewed_pages
    enough_buckets = required_buckets.issubset(reviewed_buckets)
    state = (
        "ready"
        if enough_pages and enough_buckets and not failures
        else ("blocked" if failures else "waiting_for_review")
    )
    return AblationReadiness(
        pilot_id=spec.pilot_id,
        state=state,
        reviewed_pages=len(ready),
        target_pages=len(spec.targets),
        reviewed_buckets=tuple(sorted(reviewed_buckets)),
        required_buckets=tuple(sorted(required_buckets)),
        ready_targets=tuple(sorted(ready)),
        pending_targets=tuple(sorted(pending)),
        failures=tuple(sorted(set(failures))),
    )


def _weighted_mean(values: Iterable[Tuple[float, int]]) -> Optional[float]:
    items = [(value, weight) for value, weight in values if weight > 0]
    total = sum(weight for _, weight in items)
    if total == 0:
        return None
    return sum(value * weight for value, weight in items) / total


def aggregate_variant(
    variant_id: str,
    observations: Sequence[AblationObservation],
) -> Optional[VariantAggregate]:
    selected = [item for item in observations if item.variant_id == variant_id]
    if not selected:
        return None

    page_keys: Set[Tuple[str, int]] = set()
    for item in selected:
        overlap = page_keys.intersection(item.page_keys())
        if overlap:
            raise ValueError(
                f"Variant {variant_id} observations overlap pages: {sorted(overlap)}"
            )
        page_keys.update(item.page_keys())

    attempted_pages = len(page_keys)
    failed_pages = sum(
        len(item.page_indexes)
        for item in selected
        if item.status in {"failed", "timeout"}
    )
    invalid_pages = sum(
        len(item.page_indexes)
        for item in selected
        if item.status == "skipped" or not item.valid_for_decision
    )
    quality = _weighted_mean(
        (
            item.quality_macro
            if item.status == "success" and item.quality_macro is not None
            else 0.0,
            len(item.page_indexes),
        )
        for item in selected
        if item.status != "skipped"
    )
    attempted_non_skipped = sum(
        len(item.page_indexes) for item in selected if item.status != "skipped"
    )
    elapsed = (
        sum(item.elapsed_seconds for item in selected if item.status != "skipped")
        / attempted_non_skipped
        if attempted_non_skipped
        else 0.0
    )
    successful_pages = sum(
        len(item.page_indexes) for item in selected if item.status == "success"
    )
    review_issues = (
        sum(item.review_issue_count for item in selected if item.status == "success")
        / successful_pages
        if successful_pages
        else None
    )
    interventions = (
        sum(item.intervention_count for item in selected if item.status == "success")
        / successful_pages
        if successful_pages
        else None
    )
    minutes_available = all(
        item.manual_review_minutes is not None
        for item in selected
        if item.status == "success"
    )
    minutes = (
        sum(
            float(item.manual_review_minutes or 0.0)
            for item in selected
            if item.status == "success"
        )
        / successful_pages
        if successful_pages and minutes_available
        else None
    )
    cost_available = all(
        item.ai_cost_usd is not None for item in selected if item.status == "success"
    )
    cost = (
        sum(
            float(item.ai_cost_usd or 0.0)
            for item in selected
            if item.status == "success"
        )
        / successful_pages
        if successful_pages and cost_available
        else None
    )
    return VariantAggregate(
        variant_id=variant_id,
        attempted_pages=attempted_pages,
        failed_pages=failed_pages,
        invalid_pages=invalid_pages,
        quality_macro=round(float(quality or 0.0), 6),
        failure_rate=(
            round(failed_pages / attempted_non_skipped, 6)
            if attempted_non_skipped
            else 1.0
        ),
        elapsed_seconds_per_page=round(elapsed, 6),
        review_issues_per_page=(
            round(review_issues, 6) if review_issues is not None else None
        ),
        manual_review_minutes_per_page=(
            round(minutes, 6) if minutes is not None else None
        ),
        ai_cost_usd_per_page=round(cost, 6) if cost is not None else None,
        interventions_per_page=(
            round(interventions, 6) if interventions is not None else None
        ),
        selected_parsers=tuple(
            sorted(
                {
                    item.selected_parser
                    for item in selected
                    if item.selected_parser is not None
                }
            )
        ),
        page_keys=tuple(sorted(page_keys)),
    )


def _reduction(before: Optional[float], after: Optional[float]) -> Optional[float]:
    if before is None or after is None:
        return None
    if before == 0:
        return 0.0 if after == 0 else -1.0
    return (before - after) / before


def _decision(
    spec: AblationPilotSpec,
    readiness: AblationReadiness,
    before: Optional[VariantAggregate],
    after: Optional[VariantAggregate],
    component: str,
    from_variant_id: str,
    to_variant_id: str,
) -> AblationDecision:
    policy = spec.decision_policy
    reasons: List[str] = []

    if before is None or after is None:
        return AblationDecision(
            from_variant=from_variant_id,
            to_variant=to_variant_id,
            component=component,
            verdict="insufficient_evidence",
            confidence="provisional",
            quality_gain=None,
            latency_multiplier=None,
            failure_rate_delta=None,
            review_burden_reduction=None,
            manual_minutes_reduction=None,
            ai_cost_delta_per_page=None,
            reasons=("one or both variant result sets are missing",),
        )

    expected_pages = set(readiness.ready_targets)
    before_pages = set(before.page_keys)
    after_pages = set(after.page_keys)
    if (
        not readiness.ready
        or before_pages != expected_pages
        or after_pages != expected_pages
        or before.invalid_pages > 0
        or after.invalid_pages > 0
    ):
        reasons.append(
            "paired variants do not provide a complete valid observation set "
            "for the evidence-ready pilot targets"
        )
        return AblationDecision(
            from_variant=before.variant_id,
            to_variant=after.variant_id,
            component=component,
            verdict="insufficient_evidence",
            confidence="provisional",
            quality_gain=None,
            latency_multiplier=None,
            failure_rate_delta=None,
            review_burden_reduction=None,
            manual_minutes_reduction=None,
            ai_cost_delta_per_page=None,
            reasons=tuple(reasons),
        )

    quality_gain = after.quality_macro - before.quality_macro
    latency_multiplier = (
        after.elapsed_seconds_per_page / before.elapsed_seconds_per_page
        if before.elapsed_seconds_per_page > 0
        else (1.0 if after.elapsed_seconds_per_page == 0 else float("inf"))
    )
    failure_delta = after.failure_rate - before.failure_rate
    review_reduction = _reduction(
        before.review_issues_per_page,
        after.review_issues_per_page,
    )
    minutes_reduction = _reduction(
        before.manual_review_minutes_per_page,
        after.manual_review_minutes_per_page,
    )
    before_cost = before.ai_cost_usd_per_page or 0.0
    after_cost = after.ai_cost_usd_per_page or 0.0
    cost_delta = after_cost - before_cost

    guardrails_pass = True
    if latency_multiplier > policy.maximum_latency_multiplier:
        guardrails_pass = False
        reasons.append(
            f"latency x{latency_multiplier:.3f} exceeds "
            f"x{policy.maximum_latency_multiplier:.3f}"
        )
    if failure_delta > policy.maximum_failure_rate_increase:
        guardrails_pass = False
        reasons.append(
            f"failure-rate increase {failure_delta:.4f} exceeds "
            f"{policy.maximum_failure_rate_increase:.4f}"
        )

    proxy_reduction = review_reduction or 0.0
    workload_reduction = (
        minutes_reduction if minutes_reduction is not None else proxy_reduction
    )
    meaningful_workload_reduction = (
        workload_reduction >= policy.minimum_review_burden_reduction
    )
    meaningful_quality_gain = quality_gain >= policy.minimum_quality_gain_to_keep
    negligible_quality = quality_gain <= policy.negligible_quality_gain

    if guardrails_pass and (meaningful_quality_gain or meaningful_workload_reduction):
        verdict = "keep"
        reasons.append(
            "added component clears the configured quality/workload benefit threshold"
        )
    elif negligible_quality and not meaningful_workload_reduction:
        verdict = "remove_candidate"
        reasons.append(
            "added complexity has no configured meaningful quality or workload benefit"
        )
    else:
        verdict = "optional"
        reasons.append(
            "benefit exists but does not justify making the added component mandatory"
        )

    human_complete = (
        before.manual_review_minutes_per_page is not None
        and after.manual_review_minutes_per_page is not None
    )
    confidence = (
        "decision_ready"
        if human_complete or not policy.require_human_minutes_for_final
        else "provisional"
    )
    if confidence == "provisional":
        reasons.append("manual review minutes are incomplete; verdict is provisional")

    return AblationDecision(
        from_variant=before.variant_id,
        to_variant=after.variant_id,
        component=component,
        verdict=verdict,
        confidence=confidence,
        quality_gain=round(quality_gain, 6),
        latency_multiplier=(
            round(latency_multiplier, 6) if latency_multiplier != float("inf") else None
        ),
        failure_rate_delta=round(failure_delta, 6),
        review_burden_reduction=(
            round(review_reduction, 6) if review_reduction is not None else None
        ),
        manual_minutes_reduction=(
            round(minutes_reduction, 6) if minutes_reduction is not None else None
        ),
        ai_cost_delta_per_page=round(cost_delta, 6),
        reasons=tuple(reasons),
    )


def analyze_ablation(
    spec: AblationPilotSpec,
    readiness: AblationReadiness,
    artifacts: Sequence[AblationRunArtifact],
) -> AblationReport:
    observations: List[AblationObservation] = []
    seen: Set[Tuple[str, str]] = set()
    for artifact in artifacts:
        if artifact.pilot_id != spec.pilot_id:
            raise ValueError(
                f"Run pilot_id {artifact.pilot_id!r} does not match {spec.pilot_id!r}"
            )
        if artifact.corpus_id != spec.corpus_id:
            raise ValueError("Ablation run corpus_id does not match pilot")
        for item in artifact.observations:
            key = (item.variant_id, item.document_id)
            if key in seen:
                raise ValueError(
                    "Duplicate variant/document observation across artifacts: "
                    f"{item.variant_id}/{item.document_id}"
                )
            seen.add(key)
            observations.append(item)

    aggregates = tuple(
        item
        for variant_id in _ALLOWED_VARIANTS
        for item in [aggregate_variant(variant_id, observations)]
        if item is not None
    )
    by_variant = {item.variant_id: item for item in aggregates}
    decisions = []
    for left, right in zip(spec.variants, spec.variants[1:]):
        decisions.append(
            _decision(
                spec,
                readiness,
                by_variant.get(left.id),
                by_variant.get(right.id),
                right.added_component,
                left.id,
                right.id,
            )
        )

    conclusion_ready = (
        readiness.ready
        and len(aggregates) == len(spec.variants)
        and all(
            decision.verdict != "insufficient_evidence"
            and decision.confidence == "decision_ready"
            for decision in decisions
        )
    )
    return AblationReport(
        pilot_id=spec.pilot_id,
        readiness=readiness,
        aggregates=aggregates,
        decisions=tuple(decisions),
        conclusion_ready=conclusion_ready,
    )


def render_ablation_markdown(report: AblationReport) -> str:
    lines = [
        f"# Runtime Ablation — {report.pilot_id}",
        "",
        f"- Readiness: **{report.readiness.state}**",
        (
            f"- Reviewed pilot pages: "
            f"{report.readiness.reviewed_pages}/{report.readiness.target_pages}"
        ),
        f"- Conclusion ready: **{'yes' if report.conclusion_ready else 'no'}**",
        "",
    ]
    if report.readiness.failures:
        lines.extend(["## Readiness failures", ""])
        lines.extend(f"- {item}" for item in report.readiness.failures)
        lines.append("")

    if report.aggregates:
        lines.extend(
            [
                "## Variant evidence",
                "",
                "| Variant | Quality | Failure rate | Invalid pages | Seconds/page | Issues/page | Human min/page | AI $/page |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for item in report.aggregates:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item.variant_id,
                        f"{item.quality_macro:.4f}",
                        f"{item.failure_rate:.4f}",
                        str(item.invalid_pages),
                        f"{item.elapsed_seconds_per_page:.4f}",
                        (
                            f"{item.review_issues_per_page:.4f}"
                            if item.review_issues_per_page is not None
                            else "NA"
                        ),
                        (
                            f"{item.manual_review_minutes_per_page:.4f}"
                            if item.manual_review_minutes_per_page is not None
                            else "NA"
                        ),
                        (
                            f"{item.ai_cost_usd_per_page:.4f}"
                            if item.ai_cost_usd_per_page is not None
                            else "NA"
                        ),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines.extend(["## Occam decisions", ""])
    for item in report.decisions:
        lines.extend(
            [
                (f"### {item.from_variant} → {item.to_variant}: " f"{item.component}"),
                "",
                f"- Verdict: **{item.verdict}**",
                f"- Confidence: **{item.confidence}**",
            ]
        )
        if item.quality_gain is not None:
            lines.append(f"- Quality gain: {item.quality_gain:+.4f}")
        if item.latency_multiplier is not None:
            lines.append(f"- Latency: x{item.latency_multiplier:.3f}")
        if item.review_burden_reduction is not None:
            lines.append(
                f"- Review-issue reduction: {item.review_burden_reduction:+.1%}"
            )
        if item.manual_minutes_reduction is not None:
            lines.append(
                f"- Human-minute reduction: {item.manual_minutes_reduction:+.1%}"
            )
        lines.extend(["", *[f"- {reason}" for reason in item.reasons], ""])
    if not report.conclusion_ready:
        lines.extend(
            [
                "> No architecture deletion should be treated as final until the "
                "pilot is evidence-ready and human review workload is measured.",
                "",
            ]
        )
    return "\n".join(lines)


def write_ablation_report(
    report: AblationReport,
    output_dir: Path,
) -> Tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ablation-report.json"
    markdown_path = output_dir / "ablation-report.md"
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_ablation_markdown(report), encoding="utf-8")
    return json_path, markdown_path
