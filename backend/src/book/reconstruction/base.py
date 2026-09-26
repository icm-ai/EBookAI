"""Base interfaces and helpers for deterministic BookIR reconstruction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from book.domain.models import Book


class ReconstructionPass(ABC):
    """A deterministic transformation from one valid BookIR document to another."""

    name: str = "reconstruction"

    @abstractmethod
    def apply(self, book: Book) -> Book:
        """Return a reconstructed copy of *book*."""
        raise NotImplementedError

    @staticmethod
    def clone(book: Book) -> Book:
        """Deep-copy BookIR through its versioned serialization boundary."""
        return Book.from_dict(book.to_dict())
