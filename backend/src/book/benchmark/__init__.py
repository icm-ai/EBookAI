"""Rights-cleared real-world parser benchmark utilities."""

from book.benchmark.corpus import CorpusDownloadError, CorpusIntegrityError, CorpusStore
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
    "ParserBenchmarkRunner",
    "default_parser_registry",
    "render_markdown",
    "write_markdown",
]
