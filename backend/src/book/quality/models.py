"""Quality issue and report models for BookIR."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from book.domain.models import Patch


class IssueSeverity(str, Enum):
    """Review priority for a detected quality issue."""

    INFO = "info"
    REVIEW = "review"
    ERROR = "error"


@dataclass(frozen=True)
class QualityIssue:
    """A deterministic, evidence-backed quality finding."""

    id: str
    code: str
    severity: IssueSeverity
    message: str
    node_ids: Tuple[str, ...] = ()
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_patch: Optional[Patch] = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("quality issue id must not be empty")
        if not self.code:
            raise ValueError("quality issue code must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("quality issue confidence must be in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "node_ids": list(self.node_ids),
            "confidence": self.confidence,
            "evidence": self.evidence,
            "suggested_patch": (
                self.suggested_patch.to_dict() if self.suggested_patch else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "QualityIssue":
        patch = value.get("suggested_patch")
        return cls(
            id=str(value["id"]),
            code=str(value["code"]),
            severity=IssueSeverity(value["severity"]),
            message=str(value.get("message", "")),
            node_ids=tuple(str(item) for item in value.get("node_ids", [])),
            confidence=float(value.get("confidence", 1.0)),
            evidence=dict(value.get("evidence", {})),
            suggested_patch=Patch.from_dict(patch) if patch else None,
        )


@dataclass
class QualityReport:
    """Book-level collection of quality findings and a heuristic score."""

    issues: List[QualityIssue]
    score: float
    node_count: int
    engine_version: str = "0.1"

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("quality score must be in [0, 1]")
        if self.node_count < 0:
            raise ValueError("node_count must be >= 0")

    @property
    def counts(self) -> Dict[str, int]:
        result = {severity.value: 0 for severity in IssueSeverity}
        for issue in self.issues:
            result[issue.severity.value] += 1
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "score": self.score,
            "node_count": self.node_count,
            "counts": self.counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "QualityReport":
        return cls(
            engine_version=str(value.get("engine_version", "0.1")),
            score=float(value["score"]),
            node_count=int(value["node_count"]),
            issues=[
                QualityIssue.from_dict(item) for item in value.get("issues", [])
            ],
        )

    @classmethod
    def from_json(cls, value: str) -> "QualityReport":
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("quality report JSON root must be an object")
        return cls.from_dict(parsed)
