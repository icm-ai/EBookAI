"""PyMuPDF to BookIR adapter.

This adapter extracts source blocks and provenance only. Semantic operations
such as paragraph merging, heading inference, and header/footer removal belong
to reconstruction passes, not the parser.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import fitz

from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.parsers.base import BookParserAdapter


class PyMuPDFAdapter(BookParserAdapter):
    """Extract native PDF text blocks into BookIR."""

    name = "pymupdf"
    supported_extensions = frozenset({".pdf"})

    def parse(self, path: Path) -> Book:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not self.supports(path):
            raise ValueError(f"Unsupported source format: {path.suffix}")

        source_id = self._sha256(path)
        nodes: List[BookNode] = []

        with fitz.open(str(path)) as document:
            metadata = self._metadata(document, path, source_id)

            for page_index, page in enumerate(document):
                blocks = page.get_text("dict", sort=True).get("blocks", [])
                for block_index, block in enumerate(blocks):
                    if block.get("type") != 0:
                        continue

                    content, spans = self._block_content(block)
                    if not content:
                        continue

                    bbox = self._bbox(block)
                    node_id = self._node_id(
                        source_id=source_id,
                        page_index=page_index,
                        block_index=block_index,
                        bbox=bbox,
                        content=content,
                    )
                    nodes.append(
                        BookNode(
                            id=node_id,
                            type=NodeType.TEXT_BLOCK,
                            content=content,
                            source=[
                                SourceRef(
                                    page_index=page_index,
                                    bbox=bbox,
                                    parser=self.name,
                                    source_id=source_id,
                                )
                            ],
                            confidence=Confidence(
                                extraction=1.0,
                                structure=0.25,
                                reading_order=0.80,
                            ),
                            attrs={
                                "spans": spans,
                                "page_width": float(page.rect.width),
                                "page_height": float(page.rect.height),
                            },
                        )
                    )

        return Book(metadata=metadata, nodes=nodes)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _metadata(
        self, document: fitz.Document, path: Path, source_id: str
    ) -> BookMetadata:
        raw = document.metadata or {}
        language = raw.get("language") or "und"
        return BookMetadata(
            title=(raw.get("title") or path.stem).strip(),
            author=(raw.get("author") or "").strip(),
            language=language.strip() or "und",
            identifier=f"urn:sha256:{source_id}",
            source_path=str(path),
            extra={
                "page_count": len(document),
                "parser": self.name,
                "pdf_metadata": {
                    key: value for key, value in raw.items() if value not in (None, "")
                },
            },
        )

    @staticmethod
    def _block_content(block: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        lines: List[str] = []
        serialized_spans: List[Dict[str, Any]] = []

        for line in block.get("lines", []):
            line_parts: List[str] = []
            for span in line.get("spans", []):
                text = str(span.get("text", ""))
                if not text:
                    continue
                line_parts.append(text)
                bbox = span.get("bbox")
                serialized_spans.append(
                    {
                        "text": text,
                        "bbox": [float(item) for item in bbox] if bbox else None,
                        "font": str(span.get("font", "")),
                        "size": float(span.get("size", 0.0)),
                        "flags": int(span.get("flags", 0)),
                    }
                )
            line_text = "".join(line_parts).strip()
            if line_text:
                lines.append(line_text)

        return "\n".join(lines).strip(), serialized_spans

    @staticmethod
    def _bbox(block: Dict[str, Any]) -> Tuple[float, float, float, float]:
        bbox = block.get("bbox") or (0.0, 0.0, 0.0, 0.0)
        return tuple(float(item) for item in bbox)

    @staticmethod
    def _node_id(
        *,
        source_id: str,
        page_index: int,
        block_index: int,
        bbox: Tuple[float, float, float, float],
        content: str,
    ) -> str:
        material = (
            f"{source_id}:{page_index}:{block_index}:"
            f"{','.join(f'{item:.3f}' for item in bbox)}:{content}"
        )
        return f"node-{uuid.uuid5(uuid.NAMESPACE_URL, material)}"
