"""Validated, auditable patch application for BookIR."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from book.domain.models import (
    Book,
    BookNode,
    Confidence,
    NodeType,
    Patch,
    PatchOperation,
    SourceRef,
)


class PatchValidationError(ValueError):
    """Raised when a patch cannot be safely applied to the current BookIR."""


@dataclass
class _NodeLocation:
    container: List[BookNode]
    index: int
    parent_id: Optional[str]

    @property
    def node(self) -> BookNode:
        return self.container[self.index]


class PatchValidator:
    """Validate operation-specific patch contracts before mutation."""

    def validate(self, book: Book, patch: Patch) -> None:
        if any(item.id == patch.id and item.applied for item in book.patches):
            raise PatchValidationError(f"Patch {patch.id!r} was already applied")

        location = _find_location(book.nodes, patch.target_node_id)
        if location is None:
            raise PatchValidationError(
                f"Target node {patch.target_node_id!r} does not exist"
            )

        operation = patch.operation
        if operation == PatchOperation.REPLACE_CONTENT:
            if not isinstance(patch.payload.get("content"), str):
                raise PatchValidationError("replace_content requires string content")
        elif operation == PatchOperation.SET_ATTRIBUTE:
            key = patch.payload.get("key")
            if not isinstance(key, str) or not key:
                raise PatchValidationError("set_attribute requires a non-empty key")
            if "value" not in patch.payload:
                raise PatchValidationError("set_attribute requires a value")
        elif operation == PatchOperation.INSERT_NODE:
            self._validate_insert(book, patch)
        elif operation == PatchOperation.DELETE_NODE:
            return
        elif operation == PatchOperation.MOVE_NODE:
            self._validate_move(book, patch)
        elif operation == PatchOperation.MERGE_NODES:
            self._validate_merge(book, patch)
        elif operation == PatchOperation.SPLIT_NODE:
            self._validate_split(patch)
        else:
            raise PatchValidationError(f"Unsupported patch operation: {operation}")

    def _validate_insert(self, book: Book, patch: Patch) -> None:
        raw_node = patch.payload.get("node")
        if not isinstance(raw_node, dict):
            raise PatchValidationError("insert_node requires a serialized node")
        try:
            node = BookNode.from_dict(raw_node)
        except (KeyError, TypeError, ValueError) as exc:
            raise PatchValidationError(f"Invalid inserted node: {exc}") from exc

        existing_ids = {item.id for item in book.walk()}
        inserted_ids = {item.id for item in node.walk()}
        if len(inserted_ids) != sum(1 for _ in node.walk()):
            raise PatchValidationError("Inserted subtree contains duplicate node ids")
        duplicates = existing_ids & inserted_ids
        if duplicates:
            raise PatchValidationError(
                f"Inserted node ids already exist: {sorted(duplicates)}"
            )

        position = patch.payload.get("position", "after")
        if position not in {"before", "after", "child"}:
            raise PatchValidationError(
                "insert_node position must be before, after, or child"
            )

    def _validate_move(self, book: Book, patch: Patch) -> None:
        parent_id = patch.payload.get("parent_id")
        index = patch.payload.get("index", 0)
        if not isinstance(index, int) or index < 0:
            raise PatchValidationError("move_node index must be a non-negative int")
        if parent_id is None:
            return
        if not isinstance(parent_id, str) or book.find_node(parent_id) is None:
            raise PatchValidationError("move_node parent_id does not exist")
        if parent_id == patch.target_node_id:
            raise PatchValidationError("A node cannot be moved into itself")
        target = book.find_node(patch.target_node_id)
        if target and any(node.id == parent_id for node in target.walk()):
            raise PatchValidationError("A node cannot be moved into its descendant")

    def _validate_merge(self, book: Book, patch: Patch) -> None:
        node_ids = patch.payload.get("node_ids")
        if (
            not isinstance(node_ids, list)
            or len(node_ids) < 2
            or any(not isinstance(item, str) for item in node_ids)
        ):
            raise PatchValidationError("merge_nodes requires at least two node_ids")
        if node_ids[0] != patch.target_node_id:
            raise PatchValidationError("merge_nodes target must be the first node_id")
        if len(set(node_ids)) != len(node_ids):
            raise PatchValidationError("merge_nodes node_ids must be unique")

        locations = [_find_location(book.nodes, node_id) for node_id in node_ids]
        if any(location is None for location in locations):
            raise PatchValidationError("merge_nodes contains a missing node")

        typed_locations = [location for location in locations if location is not None]
        container = typed_locations[0].container
        indexes = [location.index for location in typed_locations]
        if any(location.container is not container for location in typed_locations):
            raise PatchValidationError("merge_nodes nodes must be siblings")
        if indexes != list(range(indexes[0], indexes[0] + len(indexes))):
            raise PatchValidationError("merge_nodes nodes must be contiguous siblings")

        content = patch.payload.get("content")
        if content is not None and not isinstance(content, str):
            raise PatchValidationError("merge_nodes content must be a string")

    @staticmethod
    def _validate_split(patch: Patch) -> None:
        parts = patch.payload.get("parts")
        if not isinstance(parts, list) or len(parts) < 2:
            raise PatchValidationError("split_node requires at least two parts")
        for part in parts:
            if isinstance(part, str):
                if not part:
                    raise PatchValidationError("split_node parts must not be empty")
                continue
            if not isinstance(part, dict) or not isinstance(
                part.get("content"), str
            ):
                raise PatchValidationError(
                    "split_node parts must be strings or content dictionaries"
                )


class PatchEngine:
    """Apply validated patches to a cloned BookIR and record before-state."""

    def __init__(self, validator: Optional[PatchValidator] = None) -> None:
        self.validator = validator or PatchValidator()

    def apply(self, book: Book, patch: Patch) -> Book:
        self.validator.validate(book, patch)
        result = Book.from_dict(book.to_dict())
        audit: Dict[str, Any]

        if patch.operation == PatchOperation.REPLACE_CONTENT:
            audit = self._replace_content(result, patch)
        elif patch.operation == PatchOperation.SET_ATTRIBUTE:
            audit = self._set_attribute(result, patch)
        elif patch.operation == PatchOperation.INSERT_NODE:
            audit = self._insert_node(result, patch)
        elif patch.operation == PatchOperation.DELETE_NODE:
            audit = self._delete_node(result, patch)
        elif patch.operation == PatchOperation.MOVE_NODE:
            audit = self._move_node(result, patch)
        elif patch.operation == PatchOperation.MERGE_NODES:
            audit = self._merge_nodes(result, patch)
        elif patch.operation == PatchOperation.SPLIT_NODE:
            audit = self._split_node(result, patch)
        else:
            raise PatchValidationError(
                f"Unsupported patch operation: {patch.operation}"
            )

        self._record_applied_patch(result, patch, audit)
        return result

    def apply_many(self, book: Book, patches: Sequence[Patch]) -> Book:
        """Apply patches sequentially; the input book remains untouched on error."""
        result = Book.from_dict(book.to_dict())
        for patch in patches:
            result = self.apply(result, patch)
        return result

    @staticmethod
    def _replace_content(book: Book, patch: Patch) -> Dict[str, Any]:
        node = _require_node(book, patch.target_node_id)
        before = node.content
        node.content = patch.payload["content"]
        return {"before_content": before}

    @staticmethod
    def _set_attribute(book: Book, patch: Patch) -> Dict[str, Any]:
        node = _require_node(book, patch.target_node_id)
        key = patch.payload["key"]
        existed = key in node.attrs
        before = node.attrs.get(key)
        node.attrs[key] = patch.payload["value"]
        return {
            "attribute": key,
            "before_value": before,
            "attribute_existed": existed,
        }

    @staticmethod
    def _insert_node(book: Book, patch: Patch) -> Dict[str, Any]:
        anchor_location = _require_location(book, patch.target_node_id)
        inserted = BookNode.from_dict(patch.payload["node"])
        position = patch.payload.get("position", "after")

        if position == "child":
            anchor = anchor_location.node
            index = patch.payload.get("index", len(anchor.children))
            if not isinstance(index, int) or index < 0:
                raise PatchValidationError(
                    "insert_node child index must be a non-negative int"
                )
            index = min(index, len(anchor.children))
            anchor.children.insert(index, inserted)
            parent_id = anchor.id
        else:
            offset = 0 if position == "before" else 1
            index = anchor_location.index + offset
            anchor_location.container.insert(index, inserted)
            parent_id = anchor_location.parent_id

        return {
            "inserted_node_id": inserted.id,
            "parent_id": parent_id,
            "index": index,
        }

    @staticmethod
    def _delete_node(book: Book, patch: Patch) -> Dict[str, Any]:
        location = _require_location(book, patch.target_node_id)
        removed = location.container.pop(location.index)
        return {
            "before_node": removed.to_dict(),
            "parent_id": location.parent_id,
            "index": location.index,
        }

    @staticmethod
    def _move_node(book: Book, patch: Patch) -> Dict[str, Any]:
        source = _require_location(book, patch.target_node_id)
        node = source.container.pop(source.index)
        old_parent_id = source.parent_id
        old_index = source.index

        parent_id = patch.payload.get("parent_id")
        if parent_id is None:
            destination = book.nodes
        else:
            destination = _require_node(book, parent_id).children

        index = min(patch.payload.get("index", 0), len(destination))
        destination.insert(index, node)
        return {
            "before_parent_id": old_parent_id,
            "before_index": old_index,
            "after_parent_id": parent_id,
            "after_index": index,
        }

    @staticmethod
    def _merge_nodes(book: Book, patch: Patch) -> Dict[str, Any]:
        node_ids = patch.payload["node_ids"]
        locations = [_require_location(book, node_id) for node_id in node_ids]
        container = locations[0].container
        start = locations[0].index
        nodes = [location.node for location in locations]
        target = nodes[0]

        before_nodes = [node.to_dict() for node in nodes]
        target.content = patch.payload.get(
            "content",
            " ".join(node.content.strip() for node in nodes if node.content.strip()),
        )
        target.source = _dedupe_sources(
            source for node in nodes for source in node.source
        )
        target.children = [
            child for node in nodes for child in node.children
        ]
        target.attrs["merged_from"] = [
            node_id
            for node in nodes
            for node_id in node.attrs.get("merged_from", [node.id])
        ]
        target.confidence = Confidence(
            extraction=min(node.confidence.extraction for node in nodes),
            structure=min(node.confidence.structure for node in nodes),
            reading_order=min(node.confidence.reading_order for node in nodes),
        )

        container[start : start + len(nodes)] = [target]
        return {"before_nodes": before_nodes, "merged_node_id": target.id}

    @staticmethod
    def _split_node(book: Book, patch: Patch) -> Dict[str, Any]:
        location = _require_location(book, patch.target_node_id)
        original = location.node
        created: List[BookNode] = []

        for index, raw_part in enumerate(patch.payload["parts"]):
            if isinstance(raw_part, str):
                content = raw_part
                node_type = original.type
                attrs = dict(original.attrs)
            else:
                content = raw_part["content"]
                raw_type = raw_part.get("type", original.type.value)
                node_type = NodeType(raw_type)
                attrs = {**original.attrs, **raw_part.get("attrs", {})}

            node_id = (
                original.id
                if index == 0
                else f"node-{uuid.uuid5(uuid.NAMESPACE_URL, original.id + ':' + str(index) + ':' + content)}"
            )
            attrs["split_from"] = original.id
            created.append(
                BookNode(
                    id=node_id,
                    type=node_type,
                    content=content,
                    source=list(original.source),
                    confidence=original.confidence,
                    children=list(original.children) if index == 0 else [],
                    attrs=attrs,
                )
            )

        location.container[location.index : location.index + 1] = created
        return {
            "before_node": original.to_dict(),
            "created_node_ids": [node.id for node in created],
        }

    @staticmethod
    def _record_applied_patch(
        book: Book,
        patch: Patch,
        audit: Dict[str, Any],
    ) -> None:
        payload = dict(patch.payload)
        payload["_audit"] = audit
        applied = Patch(
            id=patch.id,
            operation=patch.operation,
            target_node_id=patch.target_node_id,
            payload=payload,
            reason=patch.reason,
            confidence=patch.confidence,
            applied=True,
        )

        for index, existing in enumerate(book.patches):
            if existing.id == patch.id:
                book.patches[index] = applied
                break
        else:
            book.patches.append(applied)


def _find_location(
    nodes: List[BookNode],
    node_id: str,
    parent_id: Optional[str] = None,
) -> Optional[_NodeLocation]:
    for index, node in enumerate(nodes):
        if node.id == node_id:
            return _NodeLocation(nodes, index, parent_id)
        child = _find_location(node.children, node_id, node.id)
        if child is not None:
            return child
    return None


def _require_location(book: Book, node_id: str) -> _NodeLocation:
    location = _find_location(book.nodes, node_id)
    if location is None:
        raise PatchValidationError(f"Node {node_id!r} does not exist")
    return location


def _require_node(book: Book, node_id: str) -> BookNode:
    node = book.find_node(node_id)
    if node is None:
        raise PatchValidationError(f"Node {node_id!r} does not exist")
    return node


def _dedupe_sources(sources) -> List[SourceRef]:
    result: List[SourceRef] = []
    seen = set()
    for source in sources:
        key = (
            source.page_index,
            source.bbox,
            source.parser,
            source.source_id,
        )
        if key not in seen:
            seen.add(key)
            result.append(source)
    return result
