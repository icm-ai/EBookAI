"""Publication-readiness findings for reviewed BookIR output."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class PublicationSeverity(str, Enum):
    """Severity used by publication-readiness checks."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class PublicationFinding:
    """One release-readiness finding."""

    code: str
    severity: PublicationSeverity
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "PublicationFinding":
        return cls(
            code=str(value["code"]),
            severity=PublicationSeverity(value["severity"]),
            message=str(value.get("message", "")),
            evidence=dict(value.get("evidence", {})),
        )


@dataclass
class PublicationReport:
    """Serializable release-readiness report."""

    release_ready: bool
    findings: List[PublicationFinding]
    epub_checked: bool
    engine_version: str = "0.1"

    @property
    def counts(self) -> Dict[str, int]:
        counts = {severity.value: 0 for severity in PublicationSeverity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "release_ready": self.release_ready,
            "epub_checked": self.epub_checked,
            "counts": self.counts,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "PublicationReport":
        return cls(
            engine_version=str(value.get("engine_version", "0.1")),
            release_ready=bool(value.get("release_ready", False)),
            epub_checked=bool(value.get("epub_checked", False)),
            findings=[
                PublicationFinding.from_dict(item)
                for item in value.get("findings", [])
            ],
        )
