"""BookIR quality detectors, scoring, and reports."""

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
from book.quality.engine import QualityEngine
from book.quality.models import IssueSeverity, QualityIssue, QualityReport

__all__ = [
    "EmptyContentDetector",
    "EmptyDocumentDetector",
    "HeadingHierarchyDetector",
    "IssueSeverity",
    "LowConfidenceDetector",
    "MissingProvenanceDetector",
    "OrphanFootnoteDetector",
    "QualityDetector",
    "QualityEngine",
    "QualityIssue",
    "QualityReport",
    "UnclassifiedTextBlockDetector",
]
