"""Golden-corpus and end-to-end regression utilities."""

from book.regression.harness import GoldenCorpusHarness
from book.regression.models import (
    GoldenCaseResult,
    GoldenCaseSpec,
    GoldenExpectation,
    GoldenSuiteReport,
    GoldenThresholds,
    RenderEvidence,
)
from book.regression.render_evidence import EpubRenderEvidenceCollector

__all__ = [
    "EpubRenderEvidenceCollector",
    "GoldenCaseResult",
    "GoldenCaseSpec",
    "GoldenCorpusHarness",
    "GoldenExpectation",
    "GoldenSuiteReport",
    "GoldenThresholds",
    "RenderEvidence",
]
