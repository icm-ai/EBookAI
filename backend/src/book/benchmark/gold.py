"""Sparse, source-pinned gold annotations and deterministic accuracy metrics."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from book.benchmark.models import CorpusDocumentSpec
from book.domain.models import Book, BookNode, NodeType

GOLD_SCHEMA_VERSION = "1"
_ALLOWED_STATUSES = {"draft", "reviewed"}
_ALLOWED_TASKS = {
    "text",
    "reading_order",
    "headings",
    "lists",
    "tables",
    "figures",
    "captions",
    "footnotes",
    "formulas",
}
_TASK_NODE_TYPES = {
    "headings": (NodeType.HEADING,),
    "lists": (NodeType.LIST_ITEM,),
    "tables": (NodeType.TABLE,),
    "figures": (NodeType.FIGURE,),
    "captions": (NodeType.CAPTION,),
    "footnotes": (NodeType.FOOTNOTE,),
    "formulas": (NodeType.FORMULA,),
}
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


class GoldValidationError(ValueError):
    """Raised when a gold annotation cannot be trusted for the pinned source."""


@dataclass(frozen=True)
class GoldElement:
    """One human-auditable semantic element on an annotated page."""

    id: str
    type: NodeType
    text: str = ""
    bbox: Optional[Tuple[float, float, float, float]] = None
    level: Optional[int] = None
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise GoldValidationError("Gold element id must not be empty")
        if self.bbox is not None:
            if len(self.bbox) != 4:
                raise GoldValidationError("Gold element bbox must have four coordinates")
            left, top, right, bottom = self.bbox
            if right < left or bottom < top:
                raise GoldValidationError("Gold element bbox is inverted")
        if self.level is not None and not 1 <= self.level <= 6:
            raise GoldValidationError("Gold heading level must be in [1, 6]")
        if self.level is not None and self.type != NodeType.HEADING:
            raise GoldValidationError("Gold level is only valid for heading elements")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldElement":
        bbox = value.get("bbox")
        return cls(
            id=str(value["id"]),
            type=NodeType(str(value["type"])),
            text=str(value.get("text", "")),
            bbox=(
                tuple(float(item) for item in bbox)
                if isinstance(bbox, (list, tuple))
                else None
            ),
            level=int(value["level"]) if "level" in value else None,
            attrs=dict(value.get("attrs", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "type": self.type.value,
            "text": self.text,
        }
        if self.bbox is not None:
            result["bbox"] = list(self.bbox)
        if self.level is not None:
            result["level"] = self.level
        if self.attrs:
            result["attrs"] = self.attrs
        return result


@dataclass(frozen=True)
class GoldPageAnnotation:
    """Sparse tasks and elements for one PDF page."""

    page_index: int
    tasks: Tuple[str, ...]
    elements: Tuple[GoldElement, ...] = ()
    reading_order: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise GoldValidationError("Gold page_index must be >= 0")
        unknown = sorted(set(self.tasks) - _ALLOWED_TASKS)
        if unknown:
            raise GoldValidationError(
                "Unknown gold tasks: " + ", ".join(unknown)
            )
        if not self.tasks:
            raise GoldValidationError("Gold page must annotate at least one task")
        element_ids = [element.id for element in self.elements]
        if len(element_ids) != len(set(element_ids)):
            raise GoldValidationError(
                f"Duplicate element id on page {self.page_index}"
            )
        if self.reading_order and "reading_order" not in self.tasks:
            raise GoldValidationError(
                "reading_order ids require the reading_order task"
            )
        if len(self.reading_order) != len(set(self.reading_order)):
            raise GoldValidationError("Gold reading_order contains duplicate ids")
        unknown_order_ids = sorted(set(self.reading_order) - set(element_ids))
        if unknown_order_ids:
            raise GoldValidationError(
                "Gold reading_order references unknown ids: "
                + ", ".join(unknown_order_ids)
            )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldPageAnnotation":
        return cls(
            page_index=int(value["page_index"]),
            tasks=tuple(str(item) for item in value.get("tasks", [])),
            elements=tuple(
                GoldElement.from_dict(item) for item in value.get("elements", [])
            ),
            reading_order=tuple(
                str(item) for item in value.get("reading_order", [])
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "page_index": self.page_index,
            "tasks": list(self.tasks),
            "elements": [element.to_dict() for element in self.elements],
        }
        if self.reading_order:
            result["reading_order"] = list(self.reading_order)
        return result


@dataclass(frozen=True)
class GoldAnnotation:
    """Versioned sparse annotation bound to exact PDF bytes."""

    document_id: str
    source_sha256: str
    pages: Tuple[GoldPageAnnotation, ...]
    status: str = "draft"
    schema_version: str = GOLD_SCHEMA_VERSION
    annotated_by: str = ""
    reviewed_by: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != GOLD_SCHEMA_VERSION:
            raise GoldValidationError(
                f"Unsupported gold schema version: {self.schema_version!r}"
            )
        if self.status not in _ALLOWED_STATUSES:
            raise GoldValidationError(
                f"Unsupported gold annotation status: {self.status!r}"
            )
        if self.status == "reviewed" and not self.reviewed_by.strip():
            raise GoldValidationError(
                "Reviewed gold annotations must record reviewed_by"
            )
        page_indexes = [page.page_index for page in self.pages]
        if len(page_indexes) != len(set(page_indexes)):
            raise GoldValidationError("Gold annotation contains duplicate pages")
        element_ids = [
            element.id for page in self.pages for element in page.elements
        ]
        if len(element_ids) != len(set(element_ids)):
            raise GoldValidationError(
                "Gold element ids must be unique across the document"
            )
        if not self.pages:
            raise GoldValidationError("Gold annotation must contain at least one page")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldAnnotation":
        pages = value.get("pages")
        if not isinstance(pages, list):
            raise GoldValidationError("Gold annotation pages must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            document_id=str(value["document_id"]),
            source_sha256=str(value["source_sha256"]).lower(),
            status=str(value.get("status", "draft")),
            annotated_by=str(value.get("annotated_by", "")),
            reviewed_by=str(value.get("reviewed_by", "")),
            notes=str(value.get("notes", "")),
            pages=tuple(GoldPageAnnotation.from_dict(item) for item in pages),
        )

    @classmethod
    def load(cls, path: Path) -> "GoldAnnotation":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise GoldValidationError("Gold annotation root must be an object")
        return cls.from_dict(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "document_id": self.document_id,
            "source_sha256": self.source_sha256,
            "status": self.status,
            "annotated_by": self.annotated_by,
            "reviewed_by": self.reviewed_by,
            "notes": self.notes,
            "pages": [page.to_dict() for page in self.pages],
        }


@dataclass(frozen=True)
class GoldEvaluation:
    metrics: Dict[str, Any]
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"metrics": self.metrics, "evidence": self.evidence}


def validate_gold_against_spec(
    annotation: GoldAnnotation,
    spec: CorpusDocumentSpec,
) -> None:
    """Reject annotation/source drift before computing any accuracy metric."""

    if annotation.document_id != spec.id:
        raise GoldValidationError(
            f"Gold document_id {annotation.document_id!r} does not match "
            f"corpus id {spec.id!r}"
        )
    if annotation.source_sha256 != spec.sha256:
        raise GoldValidationError(
            f"Gold source SHA-256 for {spec.id} is "
            f"{annotation.source_sha256}, expected {spec.sha256}"
        )
    invalid_pages = sorted(
        page.page_index
        for page in annotation.pages
        if page.page_index >= spec.page_count
    )
    if invalid_pages:
        raise GoldValidationError(
            f"Gold pages outside {spec.id} page_count={spec.page_count}: "
            + ", ".join(str(item) for item in invalid_pages)
        )


def load_gold_annotation(
    manifest_path: Path,
    spec: CorpusDocumentSpec,
) -> Optional[GoldAnnotation]:
    """Load a corpus-relative annotation without allowing path traversal."""

    if not spec.gold_annotations_path:
        return None
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    path = (root / spec.gold_annotations_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GoldValidationError(
            f"Gold annotation path escapes corpus directory: {path}"
        ) from exc
    annotation = GoldAnnotation.load(path)
    validate_gold_against_spec(annotation, spec)
    return annotation


def normalize_text(value: str) -> str:
    return _WS_RE.sub(" ", value).strip().casefold()


def _tokens(value: str) -> List[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(value)]


def _counter_prf(
    predicted: Counter[str],
    expected: Counter[str],
) -> Dict[str, float | int]:
    true_positive = sum((predicted & expected).values())
    predicted_total = sum(predicted.values())
    expected_total = sum(expected.values())
    precision = (
        true_positive / predicted_total
        if predicted_total
        else (1.0 if expected_total == 0 else 0.0)
    )
    recall = (
        true_positive / expected_total
        if expected_total
        else 1.0
    )
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": true_positive,
        "predicted": predicted_total,
        "expected": expected_total,
    }


def _count_prf(true_positive: int, predicted: int, expected: int) -> Dict[str, Any]:
    precision = (
        true_positive / predicted
        if predicted
        else (1.0 if expected == 0 else 0.0)
    )
    recall = true_positive / expected if expected else 1.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_positive": true_positive,
        "predicted": predicted,
        "expected": expected,
    }


def _bbox_iou(
    left: Optional[Tuple[float, float, float, float]],
    right: Optional[Tuple[float, float, float, float]],
) -> Optional[float]:
    if left is None or right is None:
        return None
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    ix0, iy0 = max(lx0, rx0), max(ly0, ry0)
    ix1, iy1 = min(lx1, rx1), min(ly1, ry1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    left_area = max(0.0, lx1 - lx0) * max(0.0, ly1 - ly0)
    right_area = max(0.0, rx1 - rx0) * max(0.0, ry1 - ry0)
    union = left_area + right_area - intersection
    return intersection / union if union else None


def _node_bbox(node: BookNode, page_index: int) -> Optional[Tuple[float, float, float, float]]:
    for source in node.source:
        if source.page_index == page_index and source.bbox is not None:
            return source.bbox
    return None


def _text_similarity(expected: str, predicted: str) -> float:
    expected_normalized = normalize_text(expected)
    predicted_normalized = normalize_text(predicted)
    if expected_normalized == predicted_normalized and expected_normalized:
        return 1.0
    if not expected_normalized or not predicted_normalized:
        return 0.0
    expected_tokens = Counter(_tokens(expected_normalized))
    predicted_tokens = Counter(_tokens(predicted_normalized))
    token_f1 = float(_counter_prf(predicted_tokens, expected_tokens)["f1"])
    sequence_ratio = SequenceMatcher(
        None, expected_normalized, predicted_normalized, autojunk=False
    ).ratio()
    return max(token_f1, sequence_ratio)


def _node_positions(book: Book, page_index: int) -> List[Tuple[int, BookNode]]:
    result: List[Tuple[int, BookNode]] = []
    for position, node in enumerate(book.walk()):
        if any(source.page_index == page_index for source in node.source):
            result.append((position, node))
    return result


def _match_elements(
    elements: Sequence[GoldElement],
    candidates: Sequence[Tuple[int, BookNode]],
    *,
    page_index: int,
    required_types: Optional[Tuple[NodeType, ...]] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    scored: List[Tuple[float, str, str, GoldElement, int, BookNode, float, Optional[float]]] = []
    for element in elements:
        for position, node in candidates:
            if required_types is not None and node.type not in required_types:
                continue
            text_score = _text_similarity(element.text, node.content)
            bbox_score = _bbox_iou(element.bbox, _node_bbox(node, page_index))
            if element.text.strip():
                score = (
                    0.85 * text_score + 0.15 * bbox_score
                    if bbox_score is not None
                    else text_score
                )
                minimum = 0.55
            elif bbox_score is not None:
                score = bbox_score
                minimum = 0.20
            else:
                continue
            if score < minimum:
                continue
            scored.append(
                (
                    -score,
                    element.id,
                    node.id,
                    element,
                    position,
                    node,
                    text_score,
                    bbox_score,
                )
            )

    matched_gold: set[str] = set()
    matched_nodes: set[str] = set()
    matches: List[Dict[str, Any]] = []
    for (
        negative_score,
        _,
        _,
        element,
        position,
        node,
        text_score,
        bbox_score,
    ) in sorted(scored):
        if element.id in matched_gold or node.id in matched_nodes:
            continue
        matched_gold.add(element.id)
        matched_nodes.add(node.id)
        matches.append(
            {
                "gold_id": element.id,
                "gold_type": element.type.value,
                "node_id": node.id,
                "node_type": node.type.value,
                "page_index": page_index,
                "node_position": position,
                "score": round(-negative_score, 4),
                "text_similarity": round(text_score, 4),
                "bbox_iou": (
                    round(bbox_score, 4) if bbox_score is not None else None
                ),
            }
        )

    return (
        sorted(matches, key=lambda item: str(item["gold_id"])),
        sorted(element.id for element in elements if element.id not in matched_gold),
        sorted(
            node.id
            for _, node in candidates
            if node.id not in matched_nodes
            and (required_types is None or node.type in required_types)
        ),
    )


def _text_metrics(book: Book, annotation: GoldAnnotation) -> Optional[Dict[str, Any]]:
    pages = [page for page in annotation.pages if "text" in page.tasks]
    if not pages:
        return None
    expected_tokens: Counter[str] = Counter()
    predicted_tokens: Counter[str] = Counter()
    exact_pages = 0
    character_similarities: List[float] = []
    for page in pages:
        expected_text = " ".join(
            element.text for element in page.elements if element.text.strip()
        )
        predicted_text = " ".join(
            node.content
            for _, node in _node_positions(book, page.page_index)
            if node.content.strip()
        )
        expected_normalized = normalize_text(expected_text)
        predicted_normalized = normalize_text(predicted_text)
        expected_tokens.update(_tokens(expected_normalized))
        predicted_tokens.update(_tokens(predicted_normalized))
        if expected_normalized == predicted_normalized:
            exact_pages += 1
        character_similarities.append(
            SequenceMatcher(
                None, expected_normalized, predicted_normalized, autojunk=False
            ).ratio()
            if expected_normalized or predicted_normalized
            else 1.0
        )
    metrics = _counter_prf(predicted_tokens, expected_tokens)
    metrics.update(
        {
            "annotated_page_count": len(pages),
            "exact_page_rate": round(exact_pages / len(pages), 4),
            "character_similarity_mean": round(
                sum(character_similarities) / len(character_similarities), 4
            ),
        }
    )
    return metrics


def _reading_order_metrics(
    book: Book,
    annotation: GoldAnnotation,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    pages = [page for page in annotation.pages if "reading_order" in page.tasks]
    if not pages:
        return None, {}
    correct_pairs = 0
    expected_pairs = 0
    matched_elements = 0
    total_elements = 0
    page_evidence: List[Dict[str, Any]] = []
    for page in pages:
        by_id = {element.id: element for element in page.elements}
        ordered_elements = [by_id[item] for item in page.reading_order]
        candidates = _node_positions(book, page.page_index)
        matches, unmatched_gold, _ = _match_elements(
            ordered_elements,
            candidates,
            page_index=page.page_index,
        )
        position_by_gold = {
            str(match["gold_id"]): int(match["node_position"])
            for match in matches
        }
        total_elements += len(ordered_elements)
        matched_elements += len(position_by_gold)
        page_pairs = 0
        page_correct = 0
        for left_index, left_id in enumerate(page.reading_order):
            for right_id in page.reading_order[left_index + 1 :]:
                expected_pairs += 1
                page_pairs += 1
                left_position = position_by_gold.get(left_id)
                right_position = position_by_gold.get(right_id)
                if (
                    left_position is not None
                    and right_position is not None
                    and left_position < right_position
                ):
                    correct_pairs += 1
                    page_correct += 1
        page_evidence.append(
            {
                "page_index": page.page_index,
                "matches": matches,
                "unmatched_gold": unmatched_gold,
                "correct_pairs": page_correct,
                "expected_pairs": page_pairs,
            }
        )
    pair_accuracy = (
        correct_pairs / expected_pairs
        if expected_pairs
        else (1.0 if total_elements <= 1 else 0.0)
    )
    element_match_recall = (
        matched_elements / total_elements if total_elements else 1.0
    )
    return (
        {
            "pair_accuracy": round(pair_accuracy, 4),
            "correct_pairs": correct_pairs,
            "expected_pairs": expected_pairs,
            "element_match_recall": round(element_match_recall, 4),
            "matched_elements": matched_elements,
            "expected_elements": total_elements,
        },
        {"pages": page_evidence},
    )


def _structure_metrics(
    book: Book,
    annotation: GoldAnnotation,
    task: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    pages = [page for page in annotation.pages if task in page.tasks]
    if not pages:
        return None, {}
    node_types = _TASK_NODE_TYPES[task]
    expected = 0
    predicted = 0
    true_positive = 0
    heading_level_correct = 0
    heading_level_compared = 0
    page_evidence: List[Dict[str, Any]] = []
    for page in pages:
        elements = [
            element for element in page.elements if element.type in node_types
        ]
        candidates = _node_positions(book, page.page_index)
        predictions = [
            (position, node)
            for position, node in candidates
            if node.type in node_types
        ]
        matches, unmatched_gold, unmatched_predictions = _match_elements(
            elements,
            predictions,
            page_index=page.page_index,
            required_types=node_types,
        )
        expected += len(elements)
        predicted += len(predictions)
        true_positive += len(matches)
        if task == "headings":
            element_by_id = {element.id: element for element in elements}
            node_by_id = {node.id: node for _, node in predictions}
            for match in matches:
                element = element_by_id[str(match["gold_id"])]
                if element.level is None:
                    continue
                heading_level_compared += 1
                node_level = node_by_id[str(match["node_id"])].attrs.get("level")
                if node_level == element.level:
                    heading_level_correct += 1
        page_evidence.append(
            {
                "page_index": page.page_index,
                "matches": matches,
                "unmatched_gold": unmatched_gold,
                "unmatched_predictions": unmatched_predictions,
            }
        )

    metrics = _count_prf(true_positive, predicted, expected)
    if task == "headings":
        metrics["level_accuracy"] = (
            round(heading_level_correct / heading_level_compared, 4)
            if heading_level_compared
            else None
        )
        metrics["level_compared"] = heading_level_compared
    return metrics, {"pages": page_evidence}


def evaluate_gold(book: Book, annotation: GoldAnnotation) -> GoldEvaluation:
    """Compare BookIR to only the tasks/pages explicitly annotated as gold."""

    text_metrics = _text_metrics(book, annotation)
    reading_metrics, reading_evidence = _reading_order_metrics(book, annotation)
    structures: Dict[str, Any] = {}
    structure_evidence: Dict[str, Any] = {}
    for task in _TASK_NODE_TYPES:
        metrics, evidence = _structure_metrics(book, annotation, task)
        structures[task] = metrics
        if metrics is not None:
            structure_evidence[task] = evidence

    tasks = sorted({task for page in annotation.pages for task in page.tasks})
    metrics = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "annotation_status": annotation.status,
        "annotated_pages": sorted(page.page_index for page in annotation.pages),
        "tasks": tasks,
        "text": text_metrics,
        "reading_order": reading_metrics,
        "structures": structures,
    }
    evidence = {
        "document_id": annotation.document_id,
        "source_sha256": annotation.source_sha256,
        "reading_order": reading_evidence,
        "structures": structure_evidence,
    }
    return GoldEvaluation(metrics=metrics, evidence=evidence)


def _metric_at_path(metrics: Dict[str, Any], path: str) -> Optional[float]:
    current: Any = metrics
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    return float(current)


def evaluate_gold_gate(
    metrics: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, float]] = None,
    baselines: Optional[Dict[str, float]] = None,
    max_regression: Optional[Dict[str, float]] = None,
) -> Tuple[List[str], Dict[str, Optional[float]]]:
    """Evaluate reviewed-gold absolute thresholds and baseline regressions."""

    thresholds = thresholds or {}
    baselines = baselines or {}
    max_regression = max_regression or {}
    if (thresholds or baselines) and metrics.get("annotation_status") != "reviewed":
        return (
            ["gold regression gates require annotation_status=reviewed"],
            {},
        )

    failures: List[str] = []
    for threshold_name, minimum in sorted(thresholds.items()):
        metric_path = (
            threshold_name[:-4]
            if threshold_name.endswith("_min")
            else threshold_name
        )
        value = _metric_at_path(metrics, metric_path)
        if value is None or value < float(minimum):
            failures.append(
                f"{metric_path}: expected >= {minimum}, got {value}"
            )

    deltas: Dict[str, Optional[float]] = {}
    for metric_path, baseline in sorted(baselines.items()):
        value = _metric_at_path(metrics, metric_path)
        if value is None:
            deltas[metric_path] = None
            failures.append(
                f"{metric_path}: baseline requires numeric metric, got {value}"
            )
            continue
        delta = round(value - float(baseline), 4)
        deltas[metric_path] = delta
        allowed = float(max_regression.get(metric_path, 0.0))
        if delta < -allowed:
            failures.append(
                f"{metric_path}: baseline {baseline}, current {value}, "
                f"allowed drop {allowed}"
            )
    return failures, deltas
