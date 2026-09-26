"""Capability descriptors for interchangeable parser backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple


@dataclass(frozen=True)
class ParserCapabilities:
    """Describe what an adapter can preserve or reconstruct from its backend."""

    native_text: bool = False
    ocr: bool = False
    layout: bool = False
    reading_order: bool = False
    headings: bool = False
    footnotes: bool = False
    tables: bool = False
    formulas: bool = False
    images: bool = False
    bbox: bool = False
    multi_column: bool = False
    semantic_output: bool = False
    quality_modes: Tuple[str, ...] = ()

    def supports(self, *features: str) -> bool:
        for feature in features:
            if not hasattr(self, feature):
                raise ValueError(f"Unknown parser capability: {feature}")
            value = getattr(self, feature)
            if not isinstance(value, bool) or not value:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "native_text": self.native_text,
            "ocr": self.ocr,
            "layout": self.layout,
            "reading_order": self.reading_order,
            "headings": self.headings,
            "footnotes": self.footnotes,
            "tables": self.tables,
            "formulas": self.formulas,
            "images": self.images,
            "bbox": self.bbox,
            "multi_column": self.multi_column,
            "semantic_output": self.semantic_output,
            "quality_modes": list(self.quality_modes),
        }

    def missing(self, features: Iterable[str]) -> Tuple[str, ...]:
        return tuple(feature for feature in features if not self.supports(feature))
