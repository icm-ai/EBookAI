"""Parser adapters that normalize source documents into BookIR."""

from book.parsers.base import (
    BookParserAdapter,
    ParserBackendError,
    ParserBackendUnavailable,
    ParserPayloadError,
)
from book.parsers.capabilities import ParserCapabilities
from book.parsers.marker import MarkerAdapter
from book.parsers.mineru import MinerUAdapter
from book.parsers.pymupdf import PyMuPDFAdapter
from book.parsers.registry import ParserRegistry

__all__ = [
    "BookParserAdapter",
    "MarkerAdapter",
    "MinerUAdapter",
    "ParserBackendError",
    "ParserBackendUnavailable",
    "ParserCapabilities",
    "ParserPayloadError",
    "ParserRegistry",
    "PyMuPDFAdapter",
]
