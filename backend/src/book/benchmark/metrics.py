"""Parser-level metrics for real-world documents without mandatory gold labels."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, Optional, Set

from book.benchmark.models import CorpusDocumentSpec
from book.domain.models import Book, NodeType
from book.quality import QualityEngine

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STRUCTURAL_CAPABILITIES = {
    "headings": NodeType.HEADING,
    "footnotes": NodeType.FOOTNOTE,
    "tables": NodeType.TABLE,
    "formulas": NodeType.FORMULA,
    "images": NodeType.FIGURE,
}
_NON_SEMANTIC_TYPES = {NodeType.TEXT_BLOCK, NodeType.RAW, NodeType.PAGE_BREAK}


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else round(numerator / denominator, 4)


def normalized_text(book: Book) -> str:
    return " ".join(
        " ".join(node.content.split())
        for node in book.walk()
        if node.content and node.content.strip()
    ).strip()


def token_set(book: Book) -> Set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(normalized_text(book))}


def token_jaccard(left: Iterable[str], right: Iterable[str]) -> Optional[float]:
    left_set, right_set = set(left), set(right)
    union = left_set | right_set
    if not union:
        return None
    return round(len(left_set & right_set) / len(union), 4)


def parser_level_metrics(
    book: Book,
    spec: CorpusDocumentSpec,
    *,
    quality_engine: Optional[QualityEngine] = None,
) -> Dict[str, Any]:
    """Compute comparable parser proxies without claiming ground-truth accuracy."""

    nodes = list(book.walk())
    content_nodes = [node for node in nodes if node.content.strip()]
    sources = [source for node in content_nodes for source in node.source]
    counts = Counter(node.type.value for node in nodes)
    text = normalized_text(book)
    tokens = _TOKEN_RE.findall(text)
    pages_with_content = sorted(
        {source.page_index for node in content_nodes for source in node.source}
    )

    ordered_pages = [node.source[0].page_index for node in content_nodes if node.source]
    if len(ordered_pages) <= 1:
        reading_order_proxy = 1.0
    else:
        nondecreasing = sum(
            left <= right for left, right in zip(ordered_pages, ordered_pages[1:])
        )
        reading_order_proxy = round(nondecreasing / (len(ordered_pages) - 1), 4)

    structural_expected = [
        capability
        for capability in spec.expected_capabilities
        if capability in _STRUCTURAL_CAPABILITIES
    ]
    structure_hits = {
        capability: counts[_STRUCTURAL_CAPABILITIES[capability].value]
        for capability in structural_expected
    }
    expected_structure_recovery = (
        round(
            sum(count > 0 for count in structure_hits.values()) / len(structure_hits),
            4,
        )
        if structure_hits
        else None
    )

    semantic_nodes = [node for node in nodes if node.type not in _NON_SEMANTIC_TYPES]
    engine = quality_engine or QualityEngine()
    quality = engine.analyze(book)

    confidences = [node.confidence for node in nodes]
    return {
        "node_count": len(nodes),
        "node_type_counts": dict(sorted(counts.items())),
        "text_char_count": len(text),
        "text_token_count": len(tokens),
        "normalized_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "pages_with_content": pages_with_content,
        "expected_page_count": spec.page_count,
        "page_coverage": round(min(len(pages_with_content) / spec.page_count, 1.0), 4),
        "provenance_coverage": _ratio(
            sum(bool(node.source) for node in content_nodes), len(content_nodes)
        ),
        "bbox_coverage": _ratio(
            sum(source.bbox is not None for source in sources), len(sources)
        ),
        "reading_order_proxy": reading_order_proxy,
        "semantic_node_fraction": _ratio(len(semantic_nodes), len(nodes)),
        "structure_hits": structure_hits,
        "expected_structure_recovery": expected_structure_recovery,
        "mean_confidence": {
            "extraction": (
                round(mean(item.extraction for item in confidences), 4)
                if confidences
                else None
            ),
            "structure": (
                round(mean(item.structure for item in confidences), 4)
                if confidences
                else None
            ),
            "reading_order": (
                round(mean(item.reading_order for item in confidences), 4)
                if confidences
                else None
            ),
        },
        "quality_score": quality.score,
        "quality_counts": quality.counts,
        "quality_issue_codes": sorted({issue.code for issue in quality.issues}),
    }
