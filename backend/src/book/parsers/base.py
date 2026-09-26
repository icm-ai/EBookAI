"""Base interface for BookIR parser adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, FrozenSet

from book.domain.models import Book
from book.parsers.capabilities import ParserCapabilities


class ParserBackendUnavailable(RuntimeError):
    """Raised when an optional parser backend is not installed or runnable."""


class ParserBackendError(RuntimeError):
    """Raised when an installed backend fails to parse a source document."""


class ParserPayloadError(ValueError):
    """Raised when a backend payload cannot be normalized safely into BookIR."""


class BookParserAdapter(ABC):
    """Normalize a source document into BookIR without book-level rewriting."""

    name: str = "unknown"
    supported_extensions: FrozenSet[str] = frozenset()
    capabilities = ParserCapabilities()

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_extensions

    def is_available(self) -> bool:
        """Return whether the runtime required by this adapter is available."""
        return True

    def profile(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "available": self.is_available(),
            "supported_extensions": sorted(self.supported_extensions),
            "capabilities": self.capabilities.to_dict(),
        }

    @abstractmethod
    def parse(self, path: Path) -> Book:
        """Parse path into BookIR while retaining source provenance."""
        raise NotImplementedError
