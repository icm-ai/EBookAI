"""Golden-corpus specifications and regression result models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GoldenExpectation:
    minimum_node_types: Dict[str, int] = field(default_factory=dict)
    text_fragments: List[str] = field(default_factory=list)
    ordered_fragments: List[str] = field(default_factory=list)
    required_issue_codes: List[str] = field(default_factory=list)
    forbidden_issue_codes: List[str] = field(default_factory=list)
    minimum_footnote_references: int = 0
    publication_ready: Optional[bool] = None
    render_xhtml_digest: str = ""
    render_flow_digest: str = ""
    render_stylesheet_digest: str = ""
    render_section_count: Optional[int] = None

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldenExpectation":
        return cls(
            minimum_node_types={
                str(key): int(count)
                for key, count in value.get("minimum_node_types", {}).items()
            },
            text_fragments=[str(item) for item in value.get("text_fragments", [])],
            ordered_fragments=[
                str(item) for item in value.get("ordered_fragments", [])
            ],
            required_issue_codes=[
                str(item) for item in value.get("required_issue_codes", [])
            ],
            forbidden_issue_codes=[
                str(item) for item in value.get("forbidden_issue_codes", [])
            ],
            minimum_footnote_references=int(
                value.get("minimum_footnote_references", 0)
            ),
            publication_ready=(
                bool(value["publication_ready"])
                if "publication_ready" in value
                else None
            ),
            render_xhtml_digest=str(value.get("render_xhtml_digest", "")),
            render_flow_digest=str(value.get("render_flow_digest", "")),
            render_stylesheet_digest=str(value.get("render_stylesheet_digest", "")),
            render_section_count=(
                int(value["render_section_count"])
                if "render_section_count" in value
                else None
            ),
        )


@dataclass(frozen=True)
class GoldenThresholds:
    semantic_score_min: Optional[float] = None
    text_recall_min: Optional[float] = None
    reading_order_min: Optional[float] = None
    provenance_coverage_min: Optional[float] = None
    bbox_coverage_min: Optional[float] = None
    epub_text_recall_min: Optional[float] = None

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldenThresholds":
        def optional(name: str) -> Optional[float]:
            return float(value[name]) if name in value else None

        return cls(
            semantic_score_min=optional("semantic_score_min"),
            text_recall_min=optional("text_recall_min"),
            reading_order_min=optional("reading_order_min"),
            provenance_coverage_min=optional("provenance_coverage_min"),
            bbox_coverage_min=optional("bbox_coverage_min"),
            epub_text_recall_min=optional("epub_text_recall_min"),
        )


@dataclass(frozen=True)
class GoldenCaseSpec:
    id: str
    category: str
    fixture_kind: str
    expectation: GoldenExpectation
    thresholds: GoldenThresholds
    known_gaps: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldenCaseSpec":
        return cls(
            id=str(value["id"]),
            category=str(value["category"]),
            fixture_kind=str(value["fixture_kind"]),
            expectation=GoldenExpectation.from_dict(value.get("expectation", {})),
            thresholds=GoldenThresholds.from_dict(value.get("thresholds", {})),
            known_gaps=[str(item) for item in value.get("known_gaps", [])],
        )

    @classmethod
    def load(cls, path: Path) -> "GoldenCaseSpec":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Golden case must be a JSON object: {path}")
        return cls.from_dict(payload)


@dataclass(frozen=True)
class RenderEvidence:
    xhtml_digest: str
    flow_digest: str
    stylesheet_digest: str
    section_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "xhtml_digest": self.xhtml_digest,
            "flow_digest": self.flow_digest,
            "stylesheet_digest": self.stylesheet_digest,
            "section_count": self.section_count,
        }


@dataclass
class GoldenCaseResult:
    case_id: str
    category: str
    passed: bool
    metrics: Dict[str, Any]
    failures: List[str]
    known_gaps: List[str]
    render_evidence: RenderEvidence
    output_files: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "passed": self.passed,
            "metrics": self.metrics,
            "failures": list(self.failures),
            "known_gaps": list(self.known_gaps),
            "render_evidence": self.render_evidence.to_dict(),
            "output_files": dict(self.output_files),
        }


@dataclass
class GoldenSuiteReport:
    cases: List[GoldenCaseResult]

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)

    def to_dict(self) -> Dict[str, Any]:
        def average(metric: str) -> Optional[float]:
            values = [
                float(case.metrics[metric])
                for case in self.cases
                if case.metrics.get(metric) is not None
            ]
            return round(sum(values) / len(values), 4) if values else None

        known_gaps = sorted({gap for case in self.cases for gap in case.known_gaps})
        return {
            "passed": self.passed,
            "summary": {
                "case_count": len(self.cases),
                "passed": sum(1 for case in self.cases if case.passed),
                "failed": sum(1 for case in self.cases if not case.passed),
                "categories": sorted({case.category for case in self.cases}),
                "semantic_score_mean": average("semantic_score"),
                "text_recall_mean": average("text_recall"),
                "reading_order_mean": average("reading_order"),
                "provenance_coverage_mean": average("provenance_coverage"),
                "bbox_coverage_mean": average("bbox_coverage"),
                "epub_text_recall_mean": average("epub_text_recall"),
                "publication_ready_cases": sum(
                    1
                    for case in self.cases
                    if case.metrics.get("publication_ready") is True
                ),
                "known_gaps": known_gaps,
            },
            "cases": [case.to_dict() for case in self.cases],
        }
