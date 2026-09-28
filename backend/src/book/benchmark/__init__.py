"""Rights-cleared real-world parser benchmark utilities."""

from book.benchmark.corpus import CorpusDownloadError, CorpusIntegrityError, CorpusStore
from book.benchmark.gold import (
    GoldAnnotation,
    GoldElement,
    GoldEvaluation,
    GoldPageAnnotation,
    GoldValidationError,
    evaluate_gold,
    evaluate_gold_gate,
    load_gold_annotation,
    validate_gold_against_spec,
)
from book.benchmark.models import (
    BackendRunResult,
    BenchmarkReport,
    CorpusDocumentSpec,
    CorpusManifest,
    CorpusMaterialization,
)
from book.benchmark.report import render_markdown, write_markdown
from book.benchmark.runner import ParserBenchmarkRunner, default_parser_registry

__all__ = [
    "BackendRunResult",
    "BenchmarkReport",
    "CorpusDocumentSpec",
    "CorpusDownloadError",
    "CorpusIntegrityError",
    "CorpusManifest",
    "CorpusMaterialization",
    "CorpusStore",
    "GoldAnnotation",
    "GoldElement",
    "GoldEvaluation",
    "GoldPageAnnotation",
    "GoldValidationError",
    "ParserBenchmarkRunner",
    "default_parser_registry",
    "evaluate_gold",
    "evaluate_gold_gate",
    "load_gold_annotation",
    "render_markdown",
    "validate_gold_against_spec",
    "write_markdown",
]
