"""Canonical provenance registry for consensus-reviewed gold annotations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROVENANCE_SCHEMA_VERSION = "1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, value: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class ConsensusReviewRecord:
    page_index: int
    consensus_bundle_id: str
    audit_path: str
    audit_sha256: str
    reviewer_a: str
    reviewer_b: str
    adjudicators: Tuple[str, ...]
    published_at: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ConsensusReviewRecord":
        return cls(
            page_index=int(value["page_index"]),
            consensus_bundle_id=str(value["consensus_bundle_id"]),
            audit_path=str(value["audit_path"]),
            audit_sha256=str(value["audit_sha256"]),
            reviewer_a=str(value["reviewer_a"]),
            reviewer_b=str(value["reviewer_b"]),
            adjudicators=tuple(
                str(item) for item in value.get("adjudicators", [])
            ),
            published_at=str(value["published_at"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_index": self.page_index,
            "consensus_bundle_id": self.consensus_bundle_id,
            "audit_path": self.audit_path,
            "audit_sha256": self.audit_sha256,
            "reviewer_a": self.reviewer_a,
            "reviewer_b": self.reviewer_b,
            "adjudicators": list(self.adjudicators),
            "published_at": self.published_at,
        }


@dataclass
class DocumentProvenanceRecord:
    document_id: str
    source_sha256: str
    current_gold_sha256: str
    reviews: List[ConsensusReviewRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "DocumentProvenanceRecord":
        return cls(
            document_id=str(value["document_id"]),
            source_sha256=str(value["source_sha256"]),
            current_gold_sha256=str(value["current_gold_sha256"]),
            reviews=[
                ConsensusReviewRecord.from_dict(item)
                for item in value.get("reviews", [])
            ],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_sha256": self.source_sha256,
            "current_gold_sha256": self.current_gold_sha256,
            "reviews": [item.to_dict() for item in self.reviews],
        }


@dataclass
class ConsensusProvenanceRegistry:
    records: List[DocumentProvenanceRecord] = field(default_factory=list)
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    @classmethod
    def empty(cls) -> "ConsensusProvenanceRegistry":
        return cls()

    @classmethod
    def load(cls, path: Path) -> "ConsensusProvenanceRegistry":
        path = Path(path)
        if not path.is_file():
            return cls.empty()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Consensus provenance registry root must be an object")
        if str(payload.get("schema_version", "")) != PROVENANCE_SCHEMA_VERSION:
            raise ValueError("Unsupported consensus provenance registry schema")
        return cls(
            records=[
                DocumentProvenanceRecord.from_dict(item)
                for item in payload.get("records", [])
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "records": [
                item.to_dict()
                for item in sorted(self.records, key=lambda record: record.document_id)
            ],
        }

    def document(self, document_id: str) -> Optional[DocumentProvenanceRecord]:
        for record in self.records:
            if record.document_id == document_id:
                return record
        return None

    def upsert_document(self, record: DocumentProvenanceRecord) -> None:
        self.records = [
            item for item in self.records if item.document_id != record.document_id
        ]
        self.records.append(record)

    def save(self, path: Path) -> Path:
        path = Path(path)
        _atomic_write_json(path, self.to_dict())
        return path


def registry_path_for_manifest(manifest_path: Path) -> Path:
    return Path(manifest_path).resolve().parent / "provenance" / "registry.json"


def _canonical_audit_path(
    manifest_path: Path,
    document_id: str,
    page_index: int,
    bundle_id: str,
) -> Path:
    root = Path(manifest_path).resolve().parent
    safe_document = "".join(
        character
        for character in document_id
        if character.isalnum() or character in "-_"
    )
    safe_bundle = "".join(
        character for character in bundle_id if character.isalnum() or character in "-_"
    )
    if not safe_document or not safe_bundle:
        raise ValueError("Consensus provenance identifiers are not path-safe")
    path = (
        root
        / "provenance"
        / safe_document
        / f"page-{page_index:04d}-{safe_bundle}.consensus-audit.json"
    ).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Consensus audit path escapes corpus directory") from exc
    return path


def record_consensus_publish(
    *,
    manifest_path: Path,
    document_id: str,
    source_sha256: str,
    canonical_gold_path: Path,
    audit_payload: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Persist canonical consensus audit and update the document provenance registry."""

    manifest_path = Path(manifest_path).resolve()
    corpus_root = manifest_path.parent
    page_index = int(audit_payload["page_index"])
    bundle_id = str(audit_payload["bundle_id"])
    audit_path = _canonical_audit_path(
        manifest_path,
        document_id,
        page_index,
        bundle_id,
    )
    _atomic_write_json(audit_path, audit_payload)
    audit_sha256 = sha256_file(audit_path)
    gold_sha256 = sha256_file(canonical_gold_path)

    registry_path = registry_path_for_manifest(manifest_path)
    registry = ConsensusProvenanceRegistry.load(registry_path)
    existing = registry.document(document_id)
    reviews = list(existing.reviews) if existing is not None else []
    reviews = [
        item
        for item in reviews
        if not (
            item.page_index == page_index
            and item.consensus_bundle_id == bundle_id
        )
    ]
    decisions = list(audit_payload.get("decisions", []))
    adjudicators = tuple(
        sorted(
            {
                str(item.get("adjudicator", "")).strip()
                for item in decisions
                if str(item.get("adjudicator", "")).strip()
            }
        )
    )
    relative_audit = audit_path.relative_to(corpus_root).as_posix()
    reviews.append(
        ConsensusReviewRecord(
            page_index=page_index,
            consensus_bundle_id=bundle_id,
            audit_path=relative_audit,
            audit_sha256=audit_sha256,
            reviewer_a=str(audit_payload["reviewer_a"]),
            reviewer_b=str(audit_payload["reviewer_b"]),
            adjudicators=adjudicators,
            published_at=str(audit_payload["published_at"]),
        )
    )
    reviews.sort(key=lambda item: (item.page_index, item.published_at))
    registry.upsert_document(
        DocumentProvenanceRecord(
            document_id=document_id,
            source_sha256=source_sha256,
            current_gold_sha256=gold_sha256,
            reviews=reviews,
        )
    )
    registry.save(registry_path)
    return audit_path, registry_path
