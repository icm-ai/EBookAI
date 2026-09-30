"""Deterministic BookIR quality detectors."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Sequence

from book.domain.models import Book, BookNode, NodeType, Patch, PatchOperation
from book.quality.models import IssueSeverity, QualityIssue


def _issue_id(
    code: str,
    node_ids: Sequence[str],
    evidence: Dict[str, Any],
) -> str:
    material = json.dumps(
        {
            "code": code,
            "node_ids": list(node_ids),
            "evidence": evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return f"issue-{uuid.uuid5(uuid.NAMESPACE_URL, material)}"


def _patch_id(issue_id: str, operation: PatchOperation) -> str:
    return f"patch-{uuid.uuid5(uuid.NAMESPACE_URL, issue_id + ':' + operation.value)}"


def _page_indexes(node: BookNode) -> List[int]:
    return sorted({source.page_index for source in node.source})


class QualityDetector(ABC):
    """Base interface for deterministic quality detectors."""

    code: str = "quality"

    @abstractmethod
    def detect(self, book: Book) -> List[QualityIssue]:
        """Return quality issues without mutating BookIR."""
        raise NotImplementedError


class EmptyDocumentDetector(QualityDetector):
    """Reject parser outputs that contain no BookIR nodes."""

    code = "empty_document"

    def detect(self, book: Book) -> List[QualityIssue]:
        if next(book.walk(), None) is not None:
            return []
        evidence = {"node_count": 0}
        return [
            QualityIssue(
                id=_issue_id(self.code, [], evidence),
                code=self.code,
                severity=IssueSeverity.ERROR,
                message="Parser produced no BookIR content nodes.",
                evidence=evidence,
            )
        ]


class MissingProvenanceDetector(QualityDetector):
    code = "missing_provenance"

    _content_types = {
        NodeType.TEXT_BLOCK,
        NodeType.HEADING,
        NodeType.PARAGRAPH,
        NodeType.BLOCKQUOTE,
        NodeType.CAPTION,
        NodeType.TABLE,
        NodeType.FORMULA,
        NodeType.FOOTNOTE,
    }

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for node in book.walk():
            if (
                node.type in self._content_types
                and node.content.strip()
                and not node.source
            ):
                evidence = {"node_type": node.type.value}
                issue_id = _issue_id(self.code, [node.id], evidence)
                issues.append(
                    QualityIssue(
                        id=issue_id,
                        code=self.code,
                        severity=IssueSeverity.ERROR,
                        message="Content-bearing node has no source provenance.",
                        node_ids=(node.id,),
                        evidence=evidence,
                    )
                )
        return issues


class LowConfidenceDetector(QualityDetector):
    code = "low_confidence"

    def __init__(
        self,
        *,
        extraction: float = 0.75,
        structure: float = 0.60,
        reading_order: float = 0.65,
    ) -> None:
        self.thresholds = {
            "extraction": extraction,
            "structure": structure,
            "reading_order": reading_order,
        }

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for node in book.walk():
            values = {
                "extraction": node.confidence.extraction,
                "structure": node.confidence.structure,
                "reading_order": node.confidence.reading_order,
            }
            low_axes = {
                axis: {"value": value, "threshold": self.thresholds[axis]}
                for axis, value in values.items()
                if value < self.thresholds[axis]
            }
            if not low_axes:
                continue

            minimum = min(item["value"] for item in low_axes.values())
            severity = IssueSeverity.ERROR if minimum < 0.35 else IssueSeverity.REVIEW
            evidence = {
                "low_axes": low_axes,
                "pages": _page_indexes(node),
            }
            issue_id = _issue_id(self.code, [node.id], evidence)
            issues.append(
                QualityIssue(
                    id=issue_id,
                    code=self.code,
                    severity=severity,
                    message="Node confidence is below the configured threshold.",
                    node_ids=(node.id,),
                    confidence=1.0,
                    evidence=evidence,
                )
            )
        return issues


class UnclassifiedTextBlockDetector(QualityDetector):
    code = "unclassified_text_block"

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for node in book.walk():
            if node.type != NodeType.TEXT_BLOCK:
                continue
            evidence = {
                "pages": _page_indexes(node),
                "text_preview": node.content[:120],
            }
            issue_id = _issue_id(self.code, [node.id], evidence)
            issues.append(
                QualityIssue(
                    id=issue_id,
                    code=self.code,
                    severity=IssueSeverity.REVIEW,
                    message="Raw text block remains after semantic reconstruction.",
                    node_ids=(node.id,),
                    evidence=evidence,
                )
            )
        return issues


class EmptyContentDetector(QualityDetector):
    code = "empty_content"

    _required_content_types = {
        NodeType.TEXT_BLOCK,
        NodeType.HEADING,
        NodeType.PARAGRAPH,
        NodeType.FOOTNOTE,
        NodeType.CAPTION,
    }

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for node in book.walk():
            if (
                node.type not in self._required_content_types
                or node.content.strip()
                or node.children
            ):
                continue
            evidence = {"node_type": node.type.value, "pages": _page_indexes(node)}
            issue_id = _issue_id(self.code, [node.id], evidence)
            patch = Patch(
                id=_patch_id(issue_id, PatchOperation.DELETE_NODE),
                operation=PatchOperation.DELETE_NODE,
                target_node_id=node.id,
                reason="Remove empty semantic node.",
                confidence=0.98,
            )
            issues.append(
                QualityIssue(
                    id=issue_id,
                    code=self.code,
                    severity=IssueSeverity.REVIEW,
                    message="Semantic node has no content and no children.",
                    node_ids=(node.id,),
                    evidence=evidence,
                    suggested_patch=patch,
                )
            )
        return issues


class OrphanFootnoteDetector(QualityDetector):
    code = "orphan_footnote"

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        for node in book.walk():
            if node.type != NodeType.FOOTNOTE:
                continue
            references = node.attrs.get("reference_node_ids", [])
            if references:
                continue
            evidence = {
                "marker": node.attrs.get("marker"),
                "pages": _page_indexes(node),
            }
            issue_id = _issue_id(self.code, [node.id], evidence)
            issues.append(
                QualityIssue(
                    id=issue_id,
                    code=self.code,
                    severity=IssueSeverity.REVIEW,
                    message="Footnote definition has no associated reference node.",
                    node_ids=(node.id,),
                    evidence=evidence,
                )
            )
        return issues


class HeadingHierarchyDetector(QualityDetector):
    code = "heading_hierarchy"

    def detect(self, book: Book) -> List[QualityIssue]:
        issues: List[QualityIssue] = []
        previous_level: int | None = None

        for node in book.walk():
            if node.type != NodeType.HEADING:
                continue

            raw_level = node.attrs.get("level")
            if not isinstance(raw_level, int) or not 1 <= raw_level <= 6:
                expected = previous_level or 1
                issues.append(
                    self._issue(
                        node,
                        actual=raw_level,
                        expected=expected,
                        reason="invalid_level",
                    )
                )
                previous_level = expected
                continue

            if previous_level is not None and raw_level > previous_level + 1:
                expected = previous_level + 1
                issues.append(
                    self._issue(
                        node,
                        actual=raw_level,
                        expected=expected,
                        reason="level_jump",
                    )
                )
            previous_level = raw_level

        return issues

    def _issue(
        self,
        node: BookNode,
        *,
        actual: Any,
        expected: int,
        reason: str,
    ) -> QualityIssue:
        evidence = {
            "actual_level": actual,
            "expected_level": expected,
            "reason": reason,
            "pages": _page_indexes(node),
        }
        issue_id = _issue_id(self.code, [node.id], evidence)
        patch = Patch(
            id=_patch_id(issue_id, PatchOperation.SET_ATTRIBUTE),
            operation=PatchOperation.SET_ATTRIBUTE,
            target_node_id=node.id,
            payload={"key": "level", "value": expected},
            reason="Normalize heading hierarchy.",
            confidence=0.90,
        )
        return QualityIssue(
            id=issue_id,
            code=self.code,
            severity=IssueSeverity.REVIEW,
            message="Heading hierarchy is invalid or skips a level.",
            node_ids=(node.id,),
            evidence=evidence,
            suggested_patch=patch,
        )
