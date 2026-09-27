"""Auditable models for quality-aware parser orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from book.domain.models import Book
from book.quality.models import QualityReport


class AttemptStatus(str, Enum):
    """Outcome of one parser candidate evaluation."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class StopReason(str, Enum):
    """Why orchestration stopped."""

    QUALITY_ACCEPTED = "quality_accepted"
    EXHAUSTED = "candidates_exhausted"
    NO_CANDIDATES = "no_candidates"
    MAX_ATTEMPTS = "max_attempts"


@dataclass(frozen=True)
class GateDecision:
    """Result of evaluating one QualityReport against a quality gate."""

    accepted: bool
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ParserAttempt:
    """Compact audit record for one parser candidate."""

    parser_name: str
    status: AttemptStatus
    required_features: Tuple[str, ...] = ()
    quality_score: Optional[float] = None
    issue_counts: Dict[str, int] = field(default_factory=dict)
    issue_codes: Tuple[str, ...] = ()
    reason: str = ""
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parser_name": self.parser_name,
            "status": self.status.value,
            "required_features": list(self.required_features),
            "quality_score": self.quality_score,
            "issue_counts": dict(self.issue_counts),
            "issue_codes": list(self.issue_codes),
            "reason": self.reason,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


@dataclass
class OrchestrationResult:
    """Final parser orchestration outcome."""

    book: Optional[Book]
    quality_report: Optional[QualityReport]
    accepted: bool
    selected_parser: Optional[str]
    stop_reason: StopReason
    attempts: List[ParserAttempt]
    required_features: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "selected_parser": self.selected_parser,
            "stop_reason": self.stop_reason.value,
            "required_features": list(self.required_features),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "quality_report": (
                self.quality_report.to_dict() if self.quality_report else None
            ),
        }
