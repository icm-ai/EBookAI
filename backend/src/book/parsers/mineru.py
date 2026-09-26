"""MinerU 4.x SDK adapter for BookIR.

The optional MinerU dependency is imported only when parse() is executed.
Normalization targets MinerU's public Structured Content contract rather than
backend-specific model output or temporary CLI artifacts.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.parsers.base import (
    BookParserAdapter,
    ParserBackendError,
    ParserBackendUnavailable,
    ParserPayloadError,
)
from book.parsers.capabilities import ParserCapabilities
from book.parsers.utils import coerce_bbox, resolve_source_id, stable_node_id


class MinerUAdapter(BookParserAdapter):
    """Normalize MinerU Structured Content into BookIR."""

    name = "mineru"
    supported_extensions = frozenset(
        {
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".tiff",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".rtf",
            ".odt",
            ".ods",
            ".odp",
            ".epub",
            ".ofd",
            ".html",
            ".htm",
            ".mhtml",
            ".mht",
            ".csv",
            ".tsv",
        }
    )
    capabilities = ParserCapabilities(
        native_text=True,
        ocr=True,
        layout=True,
        reading_order=True,
        headings=True,
        footnotes=True,
        tables=True,
        formulas=True,
        images=True,
        bbox=True,
        multi_column=True,
        semantic_output=True,
        quality_modes=("flash", "basic", "standard", "advanced"),
    )

    _TYPE_MAP = {
        "doc_title": NodeType.HEADING,
        "paragraph_title": NodeType.HEADING,
        "text": NodeType.PARAGRAPH,
        "ref_text": NodeType.PARAGRAPH,
        "page_footnote": NodeType.FOOTNOTE,
        "list": NodeType.LIST,
        "equation": NodeType.FORMULA,
        "image": NodeType.FIGURE,
        "chart": NodeType.FIGURE,
        "table": NodeType.TABLE,
        "code": NodeType.RAW,
        "algorithm": NodeType.RAW,
        "index": NodeType.RAW,
        "header": NodeType.RAW,
        "footer": NodeType.RAW,
        "page_number": NodeType.RAW,
        "aside_text": NodeType.RAW,
    }

    def __init__(
        self,
        *,
        tier: str = "standard",
        ocr_mode: str = "auto",
        image_analysis: bool = True,
    ) -> None:
        if tier not in self.capabilities.quality_modes:
            raise ValueError(f"Unsupported MinerU tier: {tier}")
        if ocr_mode not in {"auto", "txt", "ocr"}:
            raise ValueError(f"Unsupported MinerU OCR mode: {ocr_mode}")
        self.tier = tier
        self.ocr_mode = ocr_mode
        self.image_analysis = image_analysis

    def is_available(self) -> bool:
        return importlib.util.find_spec("mineru") is not None

    def parse(self, path: Path) -> Book:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not self.supports(path):
            raise ValueError(f"Unsupported source format: {path.suffix}")

        if not self.is_available():
            raise ParserBackendUnavailable(
                "MinerU is not installed. Install MinerU separately to use "
                "MinerUAdapter; EBookAI intentionally does not bundle it."
            )

        try:
            parser_module = importlib.import_module("mineru.parser")
            parse_document = getattr(parser_module, "parse")
            result = parse_document(
                path,
                tier=self.tier,
                ocr_mode=self.ocr_mode,
                image_analysis=self.image_analysis,
            )
            payload = result.structured_content()
        except (ImportError, AttributeError) as exc:
            raise ParserBackendUnavailable(
                "Installed MinerU does not expose the expected 4.x parser SDK."
            ) from exc
        except Exception as exc:
            raise ParserBackendError(f"MinerU failed to parse {path}") from exc

        return self.from_structured_content(payload, path)

    def from_structured_content(
        self,
        payload: Dict[str, Any],
        source_path: Path,
        *,
        source_id: Optional[str] = None,
    ) -> Book:
        if not isinstance(payload, dict):
            raise ParserPayloadError("MinerU Structured Content must be an object")
        pages = payload.get("pages")
        if not isinstance(pages, list):
            raise ParserPayloadError("MinerU Structured Content must contain pages")

        source_path = Path(source_path)
        resolved_source_id = resolve_source_id(source_path, source_id)
        nodes: List[BookNode] = []
        title = source_path.stem

        for page_position, page in enumerate(pages):
            if not isinstance(page, dict):
                raise ParserPayloadError("MinerU page entry must be an object")
            page_index = self._page_index(page, page_position)
            blocks = page.get("blocks", [])
            if not isinstance(blocks, list):
                raise ParserPayloadError("MinerU page blocks must be a list")

            for block_index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    continue
                node = self._block_to_node(
                    block=block,
                    page_index=page_index,
                    block_index=block_index,
                    source_id=resolved_source_id,
                )
                if node is None:
                    continue
                nodes.append(node)
                if (
                    block.get("type") == "doc_title"
                    and node.content.strip()
                    and title == source_path.stem
                ):
                    title = node.content.strip()

        backend_metadata = {
            key: value for key, value in payload.items() if key != "pages"
        }
        return Book(
            metadata=BookMetadata(
                title=title,
                language=str(payload.get("language") or "und"),
                identifier=f"urn:sha256:{resolved_source_id}",
                source_path=str(source_path),
                extra={
                    "page_count": len(pages),
                    "parser": self.name,
                    "parser_profile": self.profile(),
                    "backend_metadata": backend_metadata,
                },
            ),
            nodes=nodes,
        )

    def _block_to_node(
        self,
        *,
        block: Dict[str, Any],
        page_index: int,
        block_index: int,
        source_id: str,
    ) -> Optional[BookNode]:
        backend_type = str(block.get("type") or "unknown")
        node_type = self._TYPE_MAP.get(backend_type, NodeType.RAW)
        content = self._content(block.get("content"))
        bbox = coerce_bbox(block.get("bbox"))
        logical_path = f"page:{page_index}/block:{block_index}"
        node_id = stable_node_id(
            parser=self.name,
            source_id=source_id,
            page_index=page_index,
            logical_path=logical_path,
            node_type=node_type.value,
            content=content,
            bbox=bbox,
        )

        attrs = {
            "backend_type": backend_type,
            "confidence_basis": "adapter_default",
        }
        for key in (
            "level",
            "anchor",
            "sub_type",
            "continues_prev",
            "image_source",
        ):
            if key in block:
                attrs[key] = block[key]

        children: List[BookNode] = []
        for collection_name, child_type in (
            ("captions", NodeType.CAPTION),
            ("footnotes", NodeType.FOOTNOTE),
        ):
            raw_children = block.get(collection_name, [])
            if not isinstance(raw_children, list):
                continue
            for child_index, child in enumerate(raw_children):
                if not isinstance(child, dict):
                    continue
                child_content = self._content(child.get("content"))
                child_bbox = coerce_bbox(child.get("bbox"))
                child_path = f"{logical_path}/{collection_name}:{child_index}"
                children.append(
                    BookNode(
                        id=stable_node_id(
                            parser=self.name,
                            source_id=source_id,
                            page_index=page_index,
                            logical_path=child_path,
                            node_type=child_type.value,
                            content=child_content,
                            bbox=child_bbox,
                        ),
                        type=child_type,
                        content=child_content,
                        source=[
                            SourceRef(
                                page_index=page_index,
                                bbox=child_bbox,
                                parser=self.name,
                                source_id=source_id,
                            )
                        ],
                        confidence=Confidence(0.90, 0.90, 0.95),
                        attrs={
                            "backend_type": collection_name[:-1],
                            "confidence_basis": "adapter_default",
                        },
                    )
                )

        if node_type == NodeType.HEADING:
            level = block.get("level", 1 if backend_type == "doc_title" else 2)
            if isinstance(level, int):
                attrs["level"] = min(max(level, 1), 6)

        return BookNode(
            id=node_id,
            type=node_type,
            content=content,
            source=[
                SourceRef(
                    page_index=page_index,
                    bbox=bbox,
                    parser=self.name,
                    source_id=source_id,
                )
            ],
            confidence=Confidence(0.92, 0.92, 0.96),
            children=children,
            attrs=attrs,
        )

    @staticmethod
    def _page_index(page: Dict[str, Any], fallback: int) -> int:
        value = page.get("page_idx", fallback)
        if isinstance(value, int) and value >= 0:
            return value
        return fallback

    @staticmethod
    def _content(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
