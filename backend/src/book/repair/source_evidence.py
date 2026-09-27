"""Transient source-image evidence for vision-assisted BookIR repair."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import fitz
from book.domain.models import Book, SourceRef
from book.quality import QualityIssue


@dataclass(frozen=True)
class SourceImageEvidence:
    """A rendered source crop identified by the BookIR provenance that produced it."""

    ref_key: str
    node_id: str
    source_id: str
    page_index: int
    bbox: Tuple[float, float, float, float]
    mime_type: str
    data_base64: str

    def to_model_image(self) -> dict:
        return {
            "label": self.ref_key,
            "mime_type": self.mime_type,
            "data_base64": self.data_base64,
        }


class SourceEvidenceRenderer:
    """Render a small number of issue-target source regions as PNG crops."""

    def __init__(
        self,
        *,
        scale: float = 2.0,
        padding_points: float = 8.0,
        max_images: int = 3,
    ) -> None:
        if scale <= 0:
            raise ValueError("scale must be > 0")
        if padding_points < 0:
            raise ValueError("padding_points must be >= 0")
        if max_images < 1:
            raise ValueError("max_images must be >= 1")
        self.scale = scale
        self.padding_points = padding_points
        self.max_images = max_images

    def render_issue(
        self,
        pdf_path: Path,
        book: Book,
        issue: QualityIssue,
    ) -> List[SourceImageEvidence]:
        candidates = []
        seen = set()
        for node_id in issue.node_ids:
            node = book.find_node(node_id)
            if node is None:
                continue
            for source in node.source:
                if source.bbox is None:
                    continue
                key = self._ref_key(node_id, source)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((node_id, source, key))

        if not candidates:
            return []

        result: List[SourceImageEvidence] = []
        with fitz.open(Path(pdf_path)) as document:
            for node_id, source, key in candidates[: self.max_images]:
                if source.page_index >= len(document):
                    continue
                page = document[source.page_index]
                clip = self._clip_rect(page.rect, source.bbox)
                if clip.is_empty or clip.width <= 0 or clip.height <= 0:
                    continue
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(self.scale, self.scale),
                    clip=clip,
                    alpha=False,
                )
                result.append(
                    SourceImageEvidence(
                        ref_key=key,
                        node_id=node_id,
                        source_id=source.source_id,
                        page_index=source.page_index,
                        bbox=source.bbox,
                        mime_type="image/png",
                        data_base64=base64.b64encode(pixmap.tobytes("png")).decode(
                            "ascii"
                        ),
                    )
                )
        return result

    def _clip_rect(
        self,
        page_rect: fitz.Rect,
        bbox: Tuple[float, float, float, float],
    ) -> fitz.Rect:
        rect = fitz.Rect(*bbox)
        rect.x0 -= self.padding_points
        rect.y0 -= self.padding_points
        rect.x1 += self.padding_points
        rect.y1 += self.padding_points
        return rect & page_rect

    @staticmethod
    def _ref_key(node_id: str, source: SourceRef) -> str:
        bbox = ",".join(f"{value:.2f}" for value in source.bbox or ())
        return (
            f"node={node_id};source={source.source_id};"
            f"page={source.page_index};bbox={bbox}"
        )
