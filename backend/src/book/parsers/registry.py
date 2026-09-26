"""Registry helpers for capability-aware parser discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from book.parsers.base import BookParserAdapter


class ParserRegistry:
    """Register adapters and query them by format and declared capability."""

    def __init__(
        self,
        adapters: Optional[Iterable[BookParserAdapter]] = None,
    ) -> None:
        self._adapters: Dict[str, BookParserAdapter] = {}
        for adapter in adapters or ():
            self.register(adapter)

    def register(self, adapter: BookParserAdapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"Parser adapter already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> BookParserAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise KeyError(f"Unknown parser adapter: {name}") from exc

    def candidates(
        self,
        path: Path,
        *,
        required_features: Iterable[str] = (),
        available_only: bool = True,
    ) -> List[BookParserAdapter]:
        required = tuple(required_features)
        return [
            adapter
            for adapter in self._adapters.values()
            if adapter.supports(Path(path))
            and not adapter.capabilities.missing(required)
            and (not available_only or adapter.is_available())
        ]

    def profiles(self) -> List[dict]:
        return [
            self._adapters[name].profile()
            for name in sorted(self._adapters)
        ]
