"""Deterministic semantic reconstruction passes for BookIR v0.1."""

from __future__ import annotations

import re
import statistics
import unicodedata
import uuid
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from book.domain.models import Book, BookNode, Confidence, NodeType, SourceRef
from book.reconstruction.base import ReconstructionPass

_SENTENCE_ENDINGS = (".", "!", "?", "。", "！", "？", ";", "；", ":", "：")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_CHAPTER_RE = re.compile(
    r"^\s*(?:chapter|part)\s+[\wivxlcdm一二三四五六七八九十百零〇\d]+"
    r"|^\s*第[一二三四五六七八九十百零〇\d]+[章节篇部卷]",
    re.IGNORECASE,
)
_FOOTNOTE_RE = re.compile(
    r"^\s*(?P<marker>" r"\[\d{1,3}\]|\(\d{1,3}\)|\d{1,3}[.)、]|[*†‡]|[①-⑳]" r")\s*"
)


def _page_index(node: BookNode, *, last: bool = False) -> Optional[int]:
    if not node.source:
        return None
    ref = node.source[-1] if last else node.source[0]
    return ref.page_index


def _bbox(
    node: BookNode,
    *,
    last: bool = False,
) -> Optional[Tuple[float, float, float, float]]:
    if not node.source:
        return None
    ref = node.source[-1] if last else node.source[0]
    return ref.bbox


def _page_height(node: BookNode, *, last: bool = False) -> Optional[float]:
    key = "last_page_height" if last else "page_height"
    value = node.attrs.get(key)
    if value is None and last:
        value = node.attrs.get("page_height")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def _span_sizes(node: BookNode) -> List[float]:
    values: List[float] = []
    for span in node.attrs.get("spans", []):
        size = span.get("size")
        if isinstance(size, (int, float)) and size > 0:
            values.append(float(size))
    return values


def _font_size(node: BookNode) -> float:
    sizes = _span_sizes(node)
    return statistics.median(sizes) if sizes else 0.0


def _is_bold(node: BookNode) -> bool:
    for span in node.attrs.get("spans", []):
        font = str(span.get("font", "")).lower()
        flags = span.get("flags")
        if "bold" in font or "black" in font or "semibold" in font:
            return True
        if isinstance(flags, int) and flags & 16:
            return True
    return False


def _median_body_font(nodes: Iterable[BookNode]) -> float:
    sizes = [
        _font_size(node)
        for node in nodes
        if node.type in {NodeType.TEXT_BLOCK, NodeType.PARAGRAPH}
        and _font_size(node) > 0
    ]
    return statistics.median(sizes) if sizes else 0.0


def _normalize_repeated_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _reconstruction_meta(book: Book) -> Dict:
    return book.metadata.extra.setdefault("reconstruction", {})


class HeaderFooterRemovalPass(ReconstructionPass):
    """Remove repeated margin text while retaining an audit copy in metadata."""

    name = "header_footer_removal"

    def __init__(
        self,
        *,
        top_ratio: float = 0.12,
        bottom_ratio: float = 0.12,
        repeat_ratio: float = 0.5,
        min_pages: int = 3,
    ) -> None:
        self.top_ratio = top_ratio
        self.bottom_ratio = bottom_ratio
        self.repeat_ratio = repeat_ratio
        self.min_pages = min_pages

    def apply(self, book: Book) -> Book:
        result = self.clone(book)
        page_count = self._page_count(result)
        if page_count < self.min_pages:
            return result

        candidates: Dict[str, List[BookNode]] = defaultdict(list)
        for node in result.nodes:
            region = self._margin_region(node)
            if region is None or not node.content.strip():
                continue
            signature = f"{region}:{_normalize_repeated_text(node.content)}"
            if signature.endswith(":"):
                continue
            candidates[signature].append(node)

        suppressed_ids = set()
        for nodes in candidates.values():
            pages = {_page_index(node) for node in nodes}
            pages.discard(None)
            if len(pages) < self.min_pages:
                continue
            if len(pages) / page_count < self.repeat_ratio:
                continue
            suppressed_ids.update(node.id for node in nodes)

        if not suppressed_ids:
            return result

        suppressed = [
            node.to_dict() for node in result.nodes if node.id in suppressed_ids
        ]
        result.nodes = [node for node in result.nodes if node.id not in suppressed_ids]
        metadata = _reconstruction_meta(result)
        metadata.setdefault("suppressed_nodes", []).extend(suppressed)
        metadata.setdefault("passes", []).append(
            {
                "name": self.name,
                "suppressed_count": len(suppressed),
            }
        )
        return result

    def _margin_region(self, node: BookNode) -> Optional[str]:
        bbox = _bbox(node)
        page_height = _page_height(node)
        if bbox is None or page_height is None:
            return None
        _, y0, _, y1 = bbox
        if y1 <= page_height * self.top_ratio:
            return "header"
        if y0 >= page_height * (1.0 - self.bottom_ratio):
            return "footer"
        return None

    @staticmethod
    def _page_count(book: Book) -> int:
        value = book.metadata.extra.get("page_count")
        if isinstance(value, int) and value > 0:
            return value
        pages = [ref.page_index for node in book.walk() for ref in node.source]
        return max(pages) + 1 if pages else 0


class HeadingInferencePass(ReconstructionPass):
    """Infer heading nodes from typography and strong chapter patterns."""

    name = "heading_inference"

    def __init__(
        self,
        *,
        font_scale: float = 1.28,
        max_heading_chars: int = 120,
    ) -> None:
        self.font_scale = font_scale
        self.max_heading_chars = max_heading_chars

    def apply(self, book: Book) -> Book:
        result = self.clone(book)
        text_sizes = [
            _font_size(node)
            for node in result.nodes
            if node.type in {NodeType.TEXT_BLOCK, NodeType.PARAGRAPH}
            and _font_size(node) > 0
        ]
        body_font = statistics.median(text_sizes) if text_sizes else 0.0
        if 0 < len(text_sizes) <= 2:
            body_font = min(text_sizes)

        candidates: List[BookNode] = []
        for node in result.nodes:
            if node.type not in {NodeType.TEXT_BLOCK, NodeType.PARAGRAPH}:
                continue
            text = node.content.strip()
            if not text or len(text) > self.max_heading_chars:
                continue

            size = _font_size(node)
            pattern_match = bool(_CHAPTER_RE.search(text))
            typographic_match = body_font > 0 and size >= body_font * self.font_scale
            bold_match = body_font > 0 and _is_bold(node) and size >= body_font * 1.05
            if pattern_match or typographic_match or bold_match:
                candidates.append(node)

        if not candidates:
            return result

        ranked_sizes = sorted(
            {round(_font_size(node), 2) for node in candidates if _font_size(node) > 0},
            reverse=True,
        )

        for node in candidates:
            text = node.content.strip()
            size = round(_font_size(node), 2)
            if _CHAPTER_RE.search(text):
                level = 1
            elif size > 0 and size in ranked_sizes:
                level = min(ranked_sizes.index(size) + 1, 6)
            else:
                level = 2

            node.type = NodeType.HEADING
            node.attrs["level"] = level
            node.attrs["inferred_heading"] = True
            node.confidence = Confidence(
                extraction=node.confidence.extraction,
                structure=max(node.confidence.structure, 0.85),
                reading_order=node.confidence.reading_order,
            )

        _reconstruction_meta(result).setdefault("passes", []).append(
            {"name": self.name, "inferred_count": len(candidates)}
        )
        return result


class FootnoteAssociationPass(ReconstructionPass):
    """Identify bottom-margin footnote definitions and associate references."""

    name = "footnote_association"

    def __init__(
        self,
        *,
        bottom_start_ratio: float = 0.68,
        max_font_ratio: float = 0.92,
        max_chars: int = 500,
    ) -> None:
        self.bottom_start_ratio = bottom_start_ratio
        self.max_font_ratio = max_font_ratio
        self.max_chars = max_chars

    def apply(self, book: Book) -> Book:
        result = self.clone(book)
        body_font = _median_body_font(result.nodes)
        associated = 0

        for node in result.nodes:
            if node.type not in {NodeType.TEXT_BLOCK, NodeType.PARAGRAPH}:
                continue
            match = _FOOTNOTE_RE.match(node.content)
            if match is None or len(node.content) > self.max_chars:
                continue

            bbox = _bbox(node)
            page_height = _page_height(node)
            if bbox is None or page_height is None:
                continue
            if bbox[1] < page_height * self.bottom_start_ratio:
                continue

            size = _font_size(node)
            if body_font > 0 and size > 0 and size > body_font * self.max_font_ratio:
                continue

            marker = match.group("marker")
            page = _page_index(node)
            references = [
                candidate.id
                for candidate in result.nodes
                if candidate.id != node.id
                and _page_index(candidate) == page
                and candidate.type != NodeType.FOOTNOTE
                and marker in candidate.content
            ]

            node.type = NodeType.FOOTNOTE
            node.attrs["marker"] = marker
            node.attrs["reference_node_ids"] = references
            node.confidence = Confidence(
                extraction=node.confidence.extraction,
                structure=max(node.confidence.structure, 0.90),
                reading_order=node.confidence.reading_order,
            )
            associated += 1

        if associated:
            _reconstruction_meta(result).setdefault("passes", []).append(
                {"name": self.name, "footnote_count": associated}
            )
        return result


class ParagraphMergePass(ReconstructionPass):
    """Merge high-confidence cross-page paragraph continuations."""

    name = "paragraph_merge"

    def __init__(
        self,
        *,
        previous_bottom_ratio: float = 0.72,
        next_top_ratio: float = 0.28,
        font_tolerance: float = 0.18,
    ) -> None:
        self.previous_bottom_ratio = previous_bottom_ratio
        self.next_top_ratio = next_top_ratio
        self.font_tolerance = font_tolerance

    def apply(self, book: Book) -> Book:
        result = self.clone(book)
        output: List[BookNode] = []
        index = 0
        merge_count = 0

        while index < len(result.nodes):
            current = result.nodes[index]
            if current.type == NodeType.TEXT_BLOCK:
                current.type = NodeType.PARAGRAPH

            index += 1
            while index < len(result.nodes):
                candidate = result.nodes[index]
                if not self._should_merge(current, candidate):
                    break
                current = self._merge(current, candidate)
                merge_count += 1
                index += 1

            output.append(current)

        result.nodes = output
        if merge_count:
            _reconstruction_meta(result).setdefault("passes", []).append(
                {"name": self.name, "merge_count": merge_count}
            )
        return result

    def _should_merge(self, previous: BookNode, following: BookNode) -> bool:
        if previous.type != NodeType.PARAGRAPH:
            return False
        if following.type not in {NodeType.TEXT_BLOCK, NodeType.PARAGRAPH}:
            return False

        previous_page = _page_index(previous, last=True)
        following_page = _page_index(following)
        if previous_page is None or following_page != previous_page + 1:
            return False

        previous_bbox = _bbox(previous, last=True)
        following_bbox = _bbox(following)
        previous_height = _page_height(previous, last=True)
        following_height = _page_height(following)
        if (
            previous_bbox is None
            or following_bbox is None
            or previous_height is None
            or following_height is None
        ):
            return False

        if previous_bbox[3] < previous_height * self.previous_bottom_ratio:
            return False
        if following_bbox[1] > following_height * self.next_top_ratio:
            return False

        previous_text = previous.content.rstrip()
        following_text = following.content.lstrip()
        if not previous_text or not following_text:
            return False
        if previous_text.endswith(_SENTENCE_ENDINGS):
            return False

        previous_size = _font_size(previous)
        following_size = _font_size(following)
        if previous_size > 0 and following_size > 0:
            relative_delta = abs(previous_size - following_size) / max(
                previous_size,
                following_size,
            )
            if relative_delta > self.font_tolerance:
                return False

        return True

    def _merge(self, previous: BookNode, following: BookNode) -> BookNode:
        content = self._join_text(previous.content, following.content)
        sources = self._dedupe_sources([*previous.source, *following.source])
        merged_from = [
            *previous.attrs.get("merged_from", [previous.id]),
            *following.attrs.get("merged_from", [following.id]),
        ]
        attrs = dict(previous.attrs)
        attrs["merged_from"] = merged_from
        attrs["spans"] = [
            *previous.attrs.get("spans", []),
            *following.attrs.get("spans", []),
        ]
        if "page_height" in following.attrs:
            attrs["last_page_height"] = following.attrs["page_height"]

        material = ":".join(merged_from)
        node_id = f"node-{uuid.uuid5(uuid.NAMESPACE_URL, material)}"
        return BookNode(
            id=node_id,
            type=NodeType.PARAGRAPH,
            content=content,
            source=sources,
            confidence=Confidence(
                extraction=min(
                    previous.confidence.extraction,
                    following.confidence.extraction,
                ),
                structure=max(
                    0.80,
                    min(
                        previous.confidence.structure,
                        following.confidence.structure,
                    ),
                ),
                reading_order=min(
                    previous.confidence.reading_order,
                    following.confidence.reading_order,
                ),
            ),
            children=[*previous.children, *following.children],
            attrs=attrs,
        )

    @staticmethod
    def _join_text(previous: str, following: str) -> str:
        left = previous.rstrip()
        right = following.lstrip()
        if left.endswith("-") and right[:1].isalpha():
            return left[:-1] + right
        if _CJK_RE.search(left[-1:]) and _CJK_RE.search(right[:1]):
            return left + right
        return f"{left} {right}"

    @staticmethod
    def _dedupe_sources(sources: Sequence[SourceRef]) -> List[SourceRef]:
        output: List[SourceRef] = []
        seen = set()
        for source in sources:
            key = (
                source.page_index,
                source.bbox,
                source.parser,
                source.source_id,
            )
            if key not in seen:
                output.append(source)
                seen.add(key)
        return output
