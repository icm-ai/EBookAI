"""Quality analysis and confidence recalculation for BookIR."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from book.domain.models import Book, Confidence
from book.quality.detectors import (
    EmptyContentDetector,
    EmptyDocumentDetector,
    HeadingHierarchyDetector,
    LowConfidenceDetector,
    MissingProvenanceDetector,
    OrphanFootnoteDetector,
    QualityDetector,
    UnclassifiedTextBlockDetector,
)
from book.quality.models import IssueSeverity, QualityIssue, QualityReport

_SEVERITY_PENALTY = {
    IssueSeverity.INFO: 0.02,
    IssueSeverity.REVIEW: 0.08,
    IssueSeverity.ERROR: 0.18,
}

_CONFIDENCE_CAPS = {
    "missing_provenance": {"extraction": 0.25},
    "unclassified_text_block": {"structure": 0.45},
    "empty_content": {"extraction": 0.50, "structure": 0.40},
    "orphan_footnote": {"structure": 0.55},
    "heading_hierarchy": {"structure": 0.65},
}


class QualityEngine:
    """Run deterministic detectors and produce a review-oriented report."""

    def __init__(
        self,
        detectors: Optional[Iterable[QualityDetector]] = None,
    ) -> None:
        self.detectors = list(
            detectors
            if detectors is not None
            else (
                EmptyDocumentDetector(),
                MissingProvenanceDetector(),
                LowConfidenceDetector(),
                UnclassifiedTextBlockDetector(),
                EmptyContentDetector(),
                OrphanFootnoteDetector(),
                HeadingHierarchyDetector(),
            )
        )

    def analyze(self, book: Book) -> QualityReport:
        issues: List[QualityIssue] = []
        for detector in self.detectors:
            issues.extend(detector.detect(book))

        issues.sort(key=self._sort_key)
        node_count = sum(1 for _ in book.walk())
        penalty = sum(_SEVERITY_PENALTY[issue.severity] for issue in issues)
        score = max(0.0, 1.0 - penalty / max(node_count, 1))
        return QualityReport(
            issues=issues,
            score=round(score, 4),
            node_count=node_count,
        )

    def recalculate_confidence(
        self,
        book: Book,
        report: Optional[QualityReport] = None,
    ) -> Tuple[Book, QualityReport]:
        """Return a BookIR copy with confidence capped by explicit issue rules."""

        report = report or self.analyze(book)
        result = Book.from_dict(book.to_dict())
        caps_by_node: Dict[str, Dict[str, float]] = {}

        for issue in report.issues:
            caps = _CONFIDENCE_CAPS.get(issue.code)
            if not caps:
                continue
            for node_id in issue.node_ids:
                node_caps = caps_by_node.setdefault(node_id, {})
                for axis, cap in caps.items():
                    node_caps[axis] = min(node_caps.get(axis, 1.0), cap)

        for node_id, caps in caps_by_node.items():
            node = result.find_node(node_id)
            if node is None:
                continue
            node.confidence = Confidence(
                extraction=min(
                    node.confidence.extraction,
                    caps.get("extraction", 1.0),
                ),
                structure=min(
                    node.confidence.structure,
                    caps.get("structure", 1.0),
                ),
                reading_order=min(
                    node.confidence.reading_order,
                    caps.get("reading_order", 1.0),
                ),
            )

        result.metadata.extra.setdefault("quality", {})["report"] = report.to_dict()
        result.metadata.extra["quality"]["confidence_recalculated"] = True
        return result, report

    @staticmethod
    def _sort_key(issue: QualityIssue) -> tuple:
        severity_order = {
            IssueSeverity.ERROR: 0,
            IssueSeverity.REVIEW: 1,
            IssueSeverity.INFO: 2,
        }
        return (
            severity_order[issue.severity],
            issue.code,
            issue.node_ids,
            issue.id,
        )
