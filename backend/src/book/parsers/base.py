"""Base interface for BookIR parser adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import FrozenSet

from book.domain.models import Book


class BookParserAdapter(ABC):
    """Normalize a source document into BookIR without book-level rewriting."""

    name: str = "unknown"
    supported_extensions: FrozenSet[str] = frozenset()

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def parse(self, path: Path) -> Book:
        """Parse path into BookIR while retaining source provenance."""
        raise NotImplementedError
