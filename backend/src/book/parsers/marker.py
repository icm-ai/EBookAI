"""Marker JSON adapter for BookIR.

Marker remains an optional dependency. The adapter uses Marker's public Python
converter surface lazily and normalizes its JSON Page/Block tree into BookIR.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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
from book.parsers.utils import polygon_to_bbox, resolve_source_id, stable_node_id

_PAGE_RE = re.compile(r"/page/(\d+)(?:/|$)", re.IGNORECASE)
_HEADING_RE = re.compile(r"<h([1-6])\b", re.IGNORECASE)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts).strip()


class MarkerAdapter(BookParserAdapter):
    """Normalize Marker JSON renderer output into BookIR."""

    name = "marker"
    supported_extensions = frozenset({".pdf", ".png", ".jpg", ".jpeg"})
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
        quality_modes=("fast", "balanced"),
    )

    _TYPE_MAP = {
        "SectionHeader": NodeType.HEADING,
        "Text": NodeType.PARAGRAPH,
        "Handwriting": NodeType.PARAGRAPH,
        "Footnote": NodeType.FOOTNOTE,
        "Table": NodeType.TABLE,
        "TableGroup": NodeType.TABLE,
        "Equation": NodeType.FORMULA,
        "TextInlineMath": NodeType.FORMULA,
        "Figure": NodeType.FIGURE,
        "FigureGroup": NodeType.FIGURE,
        "Picture": NodeType.FIGURE,
        "PictureGroup": NodeType.FIGURE,
        "Caption": NodeType.CAPTION,
        "ListGroup": NodeType.LIST,
        "ListItem": NodeType.LIST_ITEM,
        "Code": NodeType.RAW,
        "TableOfContents": NodeType.RAW,
        "PageHeader": NodeType.RAW,
        "PageFooter": NodeType.RAW,
        "Form": NodeType.RAW,
    }
    _IGNORED_TYPES = {"Line", "Span", "Page", "Document"}

    def __init__(
        self,
        *,
        mode: str = "balanced",
        disable_ocr: bool = False,
    ) -> None:
        if mode not in self.capabilities.quality_modes:
            raise ValueError(f"Unsupported Marker mode: {mode}")
        self.mode = mode
        self.disable_ocr = disable_ocr

    def is_available(self) -> bool:
        return importlib.util.find_spec("marker") is not None

    def parse(self, path: Path) -> Book:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not self.supports(path):
            raise ValueError(f"Unsupported source format: {path.suffix}")
        if not self.is_available():
            raise ParserBackendUnavailable(
                "Marker is not installed. Install marker-pdf separately to use "
                "MarkerAdapter; EBookAI intentionally does not bundle it."
            )

        try:
            converter_module = importlib.import_module("marker.converters.pdf")
            models_module = importlib.import_module("marker.models")
            config_module = importlib.import_module("marker.config.parser")
            pdf_converter = getattr(converter_module, "PdfConverter")
            create_model_dict = getattr(models_module, "create_model_dict")
            config_parser_cls = getattr(config_module, "ConfigParser")

            config: Dict[str, Any] = {
                "output_format": "json",
                "mode": self.mode,
            }
            if self.disable_ocr:
                config["disable_ocr"] = True
            config_parser = config_parser_cls(config)
            converter = pdf_converter(
                config=config_parser.generate_config_dict(),
                artifact_dict=create_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service(),
            )
            rendered = converter(str(path))
            payload = self._serialized_output(rendered)
        except (ImportError, AttributeError) as exc:
            raise ParserBackendUnavailable(
                "Installed Marker does not expose the expected converter API."
            ) from exc
        except Exception as exc:
            raise ParserBackendError(f"Marker failed to parse {path}") from exc

        return self.from_json_output(payload, path)

    def from_json_output(
        self,
        payload: Any,
        source_path: Path,
        *,
        source_id: Optional[str] = None,
    ) -> Book:
        source_path = Path(source_path)
        pages = list(self._iter_pages(payload))
        if not pages:
            raise ParserPayloadError("Marker JSON output contains no Page blocks")

        resolved_source_id = resolve_source_id(source_path, source_id)
        nodes: List[BookNode] = []
        for page_position, page in enumerate(pages):
            page_index = self._page_index(page, page_position)
            children = page.get("children") or []
            if not isinstance(children, list):
                raise ParserPayloadError("Marker Page children must be a list")
            for block_index, block in enumerate(children):
                if not isinstance(block, dict):
                    continue
                node = self._block_to_node(
                    block=block,
                    page_index=page_index,
                    logical_path=f"page:{page_index}/block:{block_index}",
                    source_id=resolved_source_id,
                )
                if node is not None:
                    nodes.append(node)

        title = next(
            (
                node.content
                for node in nodes
                if node.type == NodeType.HEADING and node.content.strip()
            ),
            source_path.stem,
        )
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        return Book(
            metadata=BookMetadata(
                title=title,
                language="und",
                identifier=f"urn:sha256:{resolved_source_id}",
                source_path=str(source_path),
                extra={
                    "page_count": len(pages),
                    "parser": self.name,
                    "parser_profile": self.profile(),
                    "backend_metadata": metadata if isinstance(metadata, dict) else {},
                },
            ),
            nodes=nodes,
        )

    def _block_to_node(
        self,
        *,
        block: Dict[str, Any],
        page_index: int,
        logical_path: str,
        source_id: str,
    ) -> Optional[BookNode]:
        backend_type = str(block.get("block_type") or "Unknown")
        if backend_type in self._IGNORED_TYPES:
            return None

        node_type = self._TYPE_MAP.get(backend_type, NodeType.RAW)
        raw_html = str(block.get("html") or "")
        content = self._html_text(raw_html)
        bbox = polygon_to_bbox(block.get("polygon"))
        node_id = stable_node_id(
            parser=self.name,
            source_id=source_id,
            page_index=page_index,
            logical_path=logical_path,
            node_type=node_type.value,
            content=content,
            bbox=bbox,
        )
        attrs: Dict[str, Any] = {
            "backend_type": backend_type,
            "backend_id": block.get("id"),
            "confidence_basis": "adapter_default",
        }
        if raw_html:
            attrs["html"] = raw_html

        if node_type == NodeType.HEADING:
            match = _HEADING_RE.search(raw_html)
            if match:
                attrs["level"] = int(match.group(1))
            else:
                hierarchy = block.get("section_hierarchy")
                levels = []
                if isinstance(hierarchy, dict):
                    for key in hierarchy:
                        try:
                            levels.append(int(key))
                        except (TypeError, ValueError):
                            continue
                attrs["level"] = min(levels) if levels else 2

        semantic_children: List[BookNode] = []
        raw_children = block.get("children")
        if isinstance(raw_children, list):
            for child_index, child in enumerate(raw_children):
                if not isinstance(child, dict):
                    continue
                child_type = str(child.get("block_type") or "Unknown")
                if child_type in {"Line", "Span"}:
                    continue
                child_node = self._block_to_node(
                    block=child,
                    page_index=page_index,
                    logical_path=f"{logical_path}/child:{child_index}",
                    source_id=source_id,
                )
                if child_node is not None:
                    semantic_children.append(child_node)

        confidence = (
            Confidence(0.90, 0.88, 0.92)
            if self.mode == "fast"
            else Confidence(0.93, 0.92, 0.94)
        )
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
            confidence=confidence,
            children=semantic_children,
            attrs=attrs,
        )

    @staticmethod
    def _serialized_output(rendered: Any) -> Any:
        if isinstance(rendered, (dict, list)):
            return rendered
        model_dump = getattr(rendered, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json")
        to_dict = getattr(rendered, "dict", None)
        if callable(to_dict):
            return to_dict()
        raise ParserPayloadError("Marker renderer returned an unsupported object")

    @classmethod
    def _iter_pages(cls, payload: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    if item.get("block_type") == "Page":
                        yield item
                    else:
                        yield from cls._iter_pages(item)
            return

        if not isinstance(payload, dict):
            return
        if payload.get("block_type") == "Page":
            yield payload
            return
        children = payload.get("children")
        if isinstance(children, list):
            for child in children:
                yield from cls._iter_pages(child)

    @staticmethod
    def _page_index(page: Dict[str, Any], fallback: int) -> int:
        for candidate in (page.get("page_id"), page.get("id")):
            if isinstance(candidate, int) and candidate >= 0:
                return candidate
            if isinstance(candidate, str):
                match = _PAGE_RE.search(candidate)
                if match:
                    return int(match.group(1))
        return fallback

    @staticmethod
    def _html_text(raw_html: str) -> str:
        if not raw_html:
            return ""
        extractor = _HTMLTextExtractor()
        extractor.feed(raw_html)
        extractor.close()
        return extractor.text()
