"""Policy objects for quality-aware parser routing and escalation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from book.parsers.base import BookParserAdapter
from book.quality.models import IssueSeverity, QualityReport
from book.orchestration.models import GateDecision


@dataclass(frozen=True)
class QualityGate:
    """Decide whether a parsed/reconstructed BookIR is good enough to stop."""

    minimum_score: float = 0.97
    max_error_issues: int = 0
    max_review_ratio: float = 0.05
    blocking_issue_codes: Tuple[str, ...] = ("missing_provenance",)

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError("minimum_score must be in [0, 1]")
        if self.max_error_issues < 0:
            raise ValueError("max_error_issues must be >= 0")
        if not 0.0 <= self.max_review_ratio <= 1.0:
            raise ValueError("max_review_ratio must be in [0, 1]")

    def evaluate(self, report: QualityReport) -> GateDecision:
        reasons: List[str] = []
        counts = report.counts

        if report.score < self.minimum_score:
            reasons.append(
                f"quality_score={report.score:.4f} < {self.minimum_score:.4f}"
            )

        error_count = counts[IssueSeverity.ERROR.value]
        if error_count > self.max_error_issues:
            reasons.append(f"error_issues={error_count} > {self.max_error_issues}")

        review_burden = (counts[IssueSeverity.REVIEW.value] + error_count) / max(
            report.node_count, 1
        )
        if review_burden > self.max_review_ratio:
            reasons.append(
                "review_ratio=" f"{review_burden:.4f} > {self.max_review_ratio:.4f}"
            )

        issue_codes = {issue.code for issue in report.issues}
        blocking = sorted(issue_codes.intersection(self.blocking_issue_codes))
        if blocking:
            reasons.append(f"blocking_issues={','.join(blocking)}")

        return GateDecision(accepted=not reasons, reasons=tuple(reasons))

    def to_dict(self) -> Dict[str, object]:
        return {
            "minimum_score": self.minimum_score,
            "max_error_issues": self.max_error_issues,
            "max_review_ratio": self.max_review_ratio,
            "blocking_issue_codes": list(self.blocking_issue_codes),
        }


@dataclass(frozen=True)
class EscalationPolicy:
    """Translate quality failures into capabilities required from the next parser."""

    issue_feature_map: Dict[str, Tuple[str, ...]] = field(
        default_factory=lambda: {
            "missing_provenance": ("bbox",),
            "unclassified_text_block": ("layout", "semantic_output"),
            "empty_content": ("ocr",),
            "orphan_footnote": ("footnotes",),
            "heading_hierarchy": ("headings",),
        }
    )

    def required_features(
        self,
        report: QualityReport,
        current: Iterable[str] = (),
    ) -> Tuple[str, ...]:
        features: Set[str] = set(current)

        for issue in report.issues:
            features.update(self.issue_feature_map.get(issue.code, ()))
            if issue.code != "low_confidence":
                continue

            low_axes = issue.evidence.get("low_axes", {})
            if not isinstance(low_axes, dict):
                continue
            if "extraction" in low_axes:
                features.add("ocr")
            if "structure" in low_axes:
                features.update(("layout", "semantic_output"))
            if "reading_order" in low_axes:
                features.update(("layout", "reading_order"))

        return tuple(sorted(features))

    def to_dict(self) -> Dict[str, object]:
        return {
            "issue_feature_map": {
                code: list(features)
                for code, features in sorted(self.issue_feature_map.items())
            }
        }


@dataclass(frozen=True)
class OrchestratorPolicy:
    """Configuration for parser ordering, quality gate, and fallback depth."""

    parser_priority: Tuple[str, ...] = ("pymupdf", "mineru", "marker")
    max_attempts: int = 3
    gate: QualityGate = field(default_factory=QualityGate)
    escalation: EscalationPolicy = field(default_factory=EscalationPolicy)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if len(set(self.parser_priority)) != len(self.parser_priority):
            raise ValueError("parser_priority must not contain duplicates")

    def order(
        self,
        adapters: Sequence[BookParserAdapter],
    ) -> List[BookParserAdapter]:
        priorities = {name: index for index, name in enumerate(self.parser_priority)}
        fallback = len(priorities)
        return sorted(
            adapters,
            key=lambda adapter: (
                priorities.get(adapter.name, fallback),
                adapter.name,
            ),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "parser_priority": list(self.parser_priority),
            "max_attempts": self.max_attempts,
            "gate": self.gate.to_dict(),
            "escalation": self.escalation.to_dict(),
        }
