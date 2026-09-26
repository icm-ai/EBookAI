"""BookIR v0.1 domain model.

BookIR is the canonical representation used between parsing, reconstruction,
quality analysis, repair, and publishing. It intentionally retains source
provenance instead of collapsing parser output into a single text string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple

BOOK_IR_VERSION = "0.1"


class NodeType(str, Enum):
    """Semantic and parser-level node types understood by BookIR v0.1."""

    TEXT_BLOCK = "text_block"
    FRONT_MATTER = "front_matter"
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    BLOCKQUOTE = "blockquote"
    FIGURE = "figure"
    CAPTION = "caption"
    TABLE = "table"
    FORMULA = "formula"
    FOOTNOTE = "footnote"
    PAGE_BREAK = "page_break"
    RAW = "raw"


@dataclass(frozen=True)
class SourceRef:
    """Trace a BookIR node back to a concrete source region."""

    page_index: int
    bbox: Optional[Tuple[float, float, float, float]]
    parser: str
    source_id: str

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index must be >= 0")
        if self.bbox is not None and len(self.bbox) != 4:
            raise ValueError("bbox must contain exactly four coordinates")
        if not self.parser:
            raise ValueError("parser must not be empty")
        if not self.source_id:
            raise ValueError("source_id must not be empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "parser": self.parser,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "SourceRef":
        bbox = value.get("bbox")
        return cls(
            page_index=int(value["page_index"]),
            bbox=tuple(float(item) for item in bbox) if bbox is not None else None,
            parser=str(value["parser"]),
            source_id=str(value["source_id"]),
        )


@dataclass(frozen=True)
class Confidence:
    """Independent confidence axes for a node."""

    extraction: float = 1.0
    structure: float = 0.0
    reading_order: float = 0.0

    def __post_init__(self) -> None:
        for name, value in (
            ("extraction", self.extraction),
            ("structure", self.structure),
            ("reading_order", self.reading_order),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} confidence must be in [0, 1]")

    def to_dict(self) -> Dict[str, float]:
        return {
            "extraction": self.extraction,
            "structure": self.structure,
            "reading_order": self.reading_order,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Confidence":
        return cls(
            extraction=float(value.get("extraction", 1.0)),
            structure=float(value.get("structure", 0.0)),
            reading_order=float(value.get("reading_order", 0.0)),
        )


class PatchOperation(str, Enum):
    """Patch operations reserved by BookIR."""

    REPLACE_CONTENT = "replace_content"
    SET_ATTRIBUTE = "set_attribute"
    INSERT_NODE = "insert_node"
    DELETE_NODE = "delete_node"
    MOVE_NODE = "move_node"
    MERGE_NODES = "merge_nodes"
    SPLIT_NODE = "split_node"


@dataclass(frozen=True)
class Patch:
    """An explicit, auditable proposed or applied change."""

    id: str
    operation: PatchOperation
    target_node_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    confidence: float = 1.0
    applied: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("patch id must not be empty")
        if not self.target_node_id:
            raise ValueError("target_node_id must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("patch confidence must be in [0, 1]")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation.value,
            "target_node_id": self.target_node_id,
            "payload": self.payload,
            "reason": self.reason,
            "confidence": self.confidence,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Patch":
        return cls(
            id=str(value["id"]),
            operation=PatchOperation(value["operation"]),
            target_node_id=str(value["target_node_id"]),
            payload=dict(value.get("payload", {})),
            reason=str(value.get("reason", "")),
            confidence=float(value.get("confidence", 1.0)),
            applied=bool(value.get("applied", False)),
        )


@dataclass
class BookNode:
    """A node in the semantic book tree."""

    id: str
    type: NodeType
    content: str = ""
    source: List[SourceRef] = field(default_factory=list)
    confidence: Confidence = field(default_factory=Confidence)
    children: List["BookNode"] = field(default_factory=list)
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("node id must not be empty")

    def walk(self) -> Iterator["BookNode"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "source": [ref.to_dict() for ref in self.source],
            "confidence": self.confidence.to_dict(),
            "children": [child.to_dict() for child in self.children],
            "attrs": self.attrs,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BookNode":
        return cls(
            id=str(value["id"]),
            type=NodeType(value["type"]),
            content=str(value.get("content", "")),
            source=[SourceRef.from_dict(item) for item in value.get("source", [])],
            confidence=Confidence.from_dict(value.get("confidence", {})),
            children=[cls.from_dict(item) for item in value.get("children", [])],
            attrs=dict(value.get("attrs", {})),
        )


@dataclass
class BookMetadata:
    """Book-level metadata independent of an output format."""

    title: str = "Untitled"
    author: str = ""
    language: str = "und"
    identifier: str = ""
    source_path: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "language": self.language,
            "identifier": self.identifier,
            "source_path": self.source_path,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BookMetadata":
        return cls(
            title=str(value.get("title", "Untitled")),
            author=str(value.get("author", "")),
            language=str(value.get("language", "und")),
            identifier=str(value.get("identifier", "")),
            source_path=str(value.get("source_path", "")),
            extra=dict(value.get("extra", {})),
        )


@dataclass
class Book:
    """Canonical BookIR document."""

    metadata: BookMetadata
    nodes: List[BookNode] = field(default_factory=list)
    patches: List[Patch] = field(default_factory=list)
    schema_version: str = BOOK_IR_VERSION

    def walk(self) -> Iterator[BookNode]:
        for node in self.nodes:
            yield from node.walk()

    def find_node(self, node_id: str) -> Optional[BookNode]:
        return next((node for node in self.walk() if node.id == node_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "patches": [patch.to_dict() for patch in self.patches],
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Book":
        schema_version = str(value.get("schema_version", ""))
        if schema_version != BOOK_IR_VERSION:
            raise ValueError(
                f"Unsupported BookIR schema version: {schema_version!r}; "
                f"expected {BOOK_IR_VERSION!r}"
            )
        return cls(
            schema_version=schema_version,
            metadata=BookMetadata.from_dict(value.get("metadata", {})),
            nodes=[BookNode.from_dict(item) for item in value.get("nodes", [])],
            patches=[Patch.from_dict(item) for item in value.get("patches", [])],
        )

    @classmethod
    def from_json(cls, value: str) -> "Book":
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("BookIR JSON root must be an object")
        return cls.from_dict(parsed)
