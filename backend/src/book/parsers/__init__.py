"""Parser adapters that normalize source documents into BookIR."""

from book.parsers.base import BookParserAdapter
from book.parsers.pymupdf import PyMuPDFAdapter

__all__ = ["BookParserAdapter", "PyMuPDFAdapter"]
