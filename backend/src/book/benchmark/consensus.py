"""Independent multi-reviewer consensus and adjudication for gold annotations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from book.benchmark.gold import (
    GoldAnnotation,
    GoldPageAnnotation,
    GoldValidationError,
    load_gold_annotation,
    validate_gold_against_spec,
)
from book.benchmark.models import CorpusDocumentSpec, CorpusManifest
from book.benchmark.provenance import record_consensus_publish
from book.benchmark.review_workbench import GoldReviewSession, GoldReviewStore

CONSENSUS_SCHEMA_VERSION = "1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_hash(value: Dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _annotation_hash(annotation: Optional[GoldAnnotation]) -> Optional[str]:
    return _json_hash(annotation.to_dict()) if annotation is not None else None


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
class ConsensusConflict:
    """One semantic disagreement between two independently reviewed candidates."""

    id: str
    kind: str
    subject_id: str
    candidate_a: Any
    candidate_b: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "subject_id": self.subject_id,
            "candidate_a": self.candidate_a,
            "candidate_b": self.candidate_b,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ConsensusConflict":
        return cls(
            id=str(value["id"]),
            kind=str(value["kind"]),
            subject_id=str(value.get("subject_id", "")),
            candidate_a=value.get("candidate_a"),
            candidate_b=value.get("candidate_b"),
        )


@dataclass(frozen=True)
class AdjudicationDecision:
    conflict_id: str
    choice: str
    adjudicator: str
    created_at: str = field(default_factory=_utc_now)
    note: str = ""

    def __post_init__(self) -> None:
        if self.choice not in {"a", "b"}:
            raise GoldValidationError("Adjudication choice must be 'a' or 'b'")
        if not self.adjudicator.strip():
            raise GoldValidationError("Adjudication requires an adjudicator")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "choice": self.choice,
            "adjudicator": self.adjudicator,
            "created_at": self.created_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "AdjudicationDecision":
        return cls(
            conflict_id=str(value["conflict_id"]),
            choice=str(value["choice"]),
            adjudicator=str(value["adjudicator"]),
            created_at=str(value.get("created_at") or _utc_now()),
            note=str(value.get("note", "")),
        )


@dataclass
class GoldConsensusBundle:
    """Persisted comparison between two promoted, independently reviewed sessions."""

    id: str
    document_id: str
    page_index: int
    source_sha256: str
    canonical_hash_at_open: Optional[str]
    session_a_id: str
    session_b_id: str
    reviewer_a: str
    reviewer_b: str
    candidate_a: GoldAnnotation
    candidate_b: GoldAnnotation
    conflicts: Tuple[ConsensusConflict, ...]
    created_at: str
    updated_at: str
    decisions: Dict[str, AdjudicationDecision] = field(default_factory=dict)
    consensus_annotation: Optional[GoldAnnotation] = None
    published_at: str = ""

    @property
    def unresolved_conflicts(self) -> Tuple[str, ...]:
        return tuple(
            conflict.id
            for conflict in self.conflicts
            if conflict.id not in self.decisions
        )

    @property
    def status(self) -> str:
        if self.published_at:
            return "published"
        if self.consensus_annotation is not None:
            return "consensus"
        if self.conflicts:
            return "conflicted"
        return "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": CONSENSUS_SCHEMA_VERSION,
            "id": self.id,
            "document_id": self.document_id,
            "page_index": self.page_index,
            "source_sha256": self.source_sha256,
            "canonical_hash_at_open": self.canonical_hash_at_open,
            "session_a_id": self.session_a_id,
            "session_b_id": self.session_b_id,
            "reviewer_a": self.reviewer_a,
            "reviewer_b": self.reviewer_b,
            "candidate_a": self.candidate_a.to_dict(),
            "candidate_b": self.candidate_b.to_dict(),
            "conflicts": [item.to_dict() for item in self.conflicts],
            "decisions": [
                self.decisions[key].to_dict() for key in sorted(self.decisions)
            ],
            "unresolved_conflicts": list(self.unresolved_conflicts),
            "status": self.status,
            "consensus_annotation": (
                self.consensus_annotation.to_dict()
                if self.consensus_annotation is not None
                else None
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldConsensusBundle":
        if str(value.get("schema_version", "")) != CONSENSUS_SCHEMA_VERSION:
            raise GoldValidationError("Unsupported consensus bundle schema")
        decisions = {
            str(item["conflict_id"]): AdjudicationDecision.from_dict(item)
            for item in value.get("decisions", [])
        }
        consensus = value.get("consensus_annotation")
        return cls(
            id=str(value["id"]),
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
            source_sha256=str(value["source_sha256"]),
            canonical_hash_at_open=(
                str(value["canonical_hash_at_open"])
                if value.get("canonical_hash_at_open") is not None
                else None
            ),
            session_a_id=str(value["session_a_id"]),
            session_b_id=str(value["session_b_id"]),
            reviewer_a=str(value["reviewer_a"]),
            reviewer_b=str(value["reviewer_b"]),
            candidate_a=GoldAnnotation.from_dict(value["candidate_a"]),
            candidate_b=GoldAnnotation.from_dict(value["candidate_b"]),
            conflicts=tuple(
                ConsensusConflict.from_dict(item) for item in value.get("conflicts", [])
            ),
            decisions=decisions,
            consensus_annotation=(
                GoldAnnotation.from_dict(consensus) if consensus else None
            ),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            published_at=str(value.get("published_at", "")),
        )


def _page(annotation: GoldAnnotation, page_index: int) -> GoldPageAnnotation:
    for page in annotation.pages:
        if page.page_index == page_index:
            return page
    raise GoldValidationError(f"Candidate is missing review page {page_index}")


def _other_pages(annotation: GoldAnnotation, page_index: int) -> List[Dict[str, Any]]:
    return [
        page.to_dict() for page in annotation.pages if page.page_index != page_index
    ]


def _semantic_page(page: GoldPageAnnotation) -> Dict[str, Any]:
    return {
        "tasks": sorted(page.tasks),
        "reading_order": list(page.reading_order),
        "elements": {
            element.id: element.to_dict()
            for element in sorted(page.elements, key=lambda item: item.id)
        },
    }


def compare_reviewed_pages(
    candidate_a: GoldAnnotation,
    candidate_b: GoldAnnotation,
    page_index: int,
) -> Tuple[ConsensusConflict, ...]:
    """Return deterministic semantic conflicts for one independently reviewed page."""

    left = _semantic_page(_page(candidate_a, page_index))
    right = _semantic_page(_page(candidate_b, page_index))
    conflicts: List[ConsensusConflict] = []
    if left["tasks"] != right["tasks"]:
        conflicts.append(
            ConsensusConflict(
                id="tasks",
                kind="tasks",
                subject_id="tasks",
                candidate_a=left["tasks"],
                candidate_b=right["tasks"],
            )
        )
    if left["reading_order"] != right["reading_order"]:
        conflicts.append(
            ConsensusConflict(
                id="reading_order",
                kind="reading_order",
                subject_id="reading_order",
                candidate_a=left["reading_order"],
                candidate_b=right["reading_order"],
            )
        )
    element_ids = sorted(set(left["elements"]) | set(right["elements"]))
    for element_id in element_ids:
        value_a = left["elements"].get(element_id)
        value_b = right["elements"].get(element_id)
        if value_a != value_b:
            conflicts.append(
                ConsensusConflict(
                    id=f"element:{element_id}",
                    kind="element",
                    subject_id=element_id,
                    candidate_a=value_a,
                    candidate_b=value_b,
                )
            )
    return tuple(conflicts)


class GoldConsensusStore:
    """Disk-backed two-reviewer consensus and third-party adjudication."""

    BUNDLE_FILE = "consensus-bundle.json"

    def __init__(
        self,
        manifest_path: Path,
        review_store: GoldReviewStore,
        workspace_dir: Path,
    ) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        self.manifest = CorpusManifest.load(self.manifest_path)
        self.review_store = review_store
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def create(self, session_a_id: str, session_b_id: str) -> GoldConsensusBundle:
        with self._lock:
            if session_a_id == session_b_id:
                raise GoldValidationError("Consensus requires two distinct sessions")
            session_a = self.review_store.get(session_a_id)
            session_b = self.review_store.get(session_b_id)
            self._validate_pair(session_a, session_b)
            candidate_a = session_a.promoted_annotation
            candidate_b = session_b.promoted_annotation
            assert candidate_a is not None
            assert candidate_b is not None
            conflicts = compare_reviewed_pages(
                candidate_a,
                candidate_b,
                session_a.page_index,
            )
            now = _utc_now()
            bundle = GoldConsensusBundle(
                id=str(uuid.uuid4()),
                document_id=session_a.document_id,
                page_index=session_a.page_index,
                source_sha256=session_a.source_sha256,
                canonical_hash_at_open=session_a.canonical_hash_at_open,
                session_a_id=session_a.id,
                session_b_id=session_b.id,
                reviewer_a=candidate_a.reviewed_by,
                reviewer_b=candidate_b.reviewed_by,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                conflicts=conflicts,
                created_at=now,
                updated_at=now,
            )
            if not conflicts:
                bundle.consensus_annotation = self._build_consensus(bundle)
            self._write(bundle)
            return bundle

    def get(self, bundle_id: str) -> GoldConsensusBundle:
        path = self._bundle_file(bundle_id)
        if not path.is_file():
            raise FileNotFoundError(f"Consensus bundle not found: {bundle_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise GoldValidationError("Consensus bundle root must be an object")
        return GoldConsensusBundle.from_dict(payload)

    def adjudicate(
        self,
        bundle_id: str,
        *,
        conflict_id: str,
        choice: str,
        adjudicator: str,
        note: str = "",
    ) -> GoldConsensusBundle:
        with self._lock:
            bundle = self.get(bundle_id)
            if adjudicator in {bundle.reviewer_a, bundle.reviewer_b}:
                raise GoldValidationError(
                    "Adjudicator must be independent from both reviewers"
                )
            conflict_ids = {item.id for item in bundle.conflicts}
            if conflict_id not in conflict_ids:
                raise KeyError(f"Consensus conflict not found: {conflict_id}")
            decision = AdjudicationDecision(
                conflict_id=conflict_id,
                choice=choice,
                adjudicator=adjudicator,
                note=note,
            )
            bundle.decisions[conflict_id] = decision
            bundle.consensus_annotation = None
            bundle.published_at = ""
            bundle.updated_at = _utc_now()
            if not bundle.unresolved_conflicts:
                bundle.consensus_annotation = self._build_consensus(bundle)
            self._write(bundle)
            return bundle

    def publish(self, bundle_id: str) -> GoldConsensusBundle:
        with self._lock:
            bundle = self.get(bundle_id)
            if bundle.consensus_annotation is None:
                raise GoldValidationError(
                    "Consensus publish requires all conflicts to be resolved"
                )
            spec = self._spec(bundle.document_id)
            canonical = load_gold_annotation(self.manifest_path, spec)
            if _annotation_hash(canonical) != bundle.canonical_hash_at_open:
                raise GoldValidationError(
                    "Canonical gold changed since the reviewer sessions opened"
                )
            validate_gold_against_spec(bundle.consensus_annotation, spec)
            path = self._canonical_gold_path(spec)
            try:
                _atomic_write_json(path, bundle.consensus_annotation.to_dict())
            except OSError as exc:
                raise GoldValidationError(
                    "Canonical gold is not writable in this environment"
                ) from exc
            bundle.published_at = _utc_now()
            bundle.updated_at = bundle.published_at
            self._write(bundle)
            audit_payload = self._audit_payload(bundle)
            self._write_audit(bundle, payload=audit_payload)
            try:
                record_consensus_publish(
                    manifest_path=self.manifest_path,
                    document_id=bundle.document_id,
                    source_sha256=bundle.source_sha256,
                    canonical_gold_path=path,
                    audit_payload=audit_payload,
                )
            except OSError as exc:
                raise GoldValidationError(
                    "Consensus gold was published but provenance registry update failed; "
                    "governance will fail closed until provenance is repaired"
                ) from exc
            return bundle

    def consensus_path(self, bundle_id: str) -> Path:
        bundle = self.get(bundle_id)
        if bundle.consensus_annotation is None:
            raise FileNotFoundError("Consensus annotation is not ready")
        path = self._bundle_dir(bundle_id) / "consensus-gold.json"
        if not path.is_file():
            _atomic_write_json(path, bundle.consensus_annotation.to_dict())
        return path

    def audit_path(self, bundle_id: str) -> Path:
        bundle = self.get(bundle_id)
        if bundle.consensus_annotation is None:
            raise FileNotFoundError("Consensus audit is not ready")
        self._write_audit(bundle)
        return self._bundle_dir(bundle_id) / "consensus-audit.json"

    def _validate_pair(
        self,
        session_a: GoldReviewSession,
        session_b: GoldReviewSession,
    ) -> None:
        for session in (session_a, session_b):
            if session.promoted_annotation is None:
                raise GoldValidationError(
                    f"Session {session.id} must be promoted before consensus"
                )
        if session_a.document_id != session_b.document_id:
            raise GoldValidationError("Consensus sessions must target one document")
        if session_a.page_index != session_b.page_index:
            raise GoldValidationError("Consensus sessions must target one page")
        if session_a.source_sha256 != session_b.source_sha256:
            raise GoldValidationError("Consensus sessions must use the same source SHA")
        if session_a.canonical_hash_at_open != session_b.canonical_hash_at_open:
            raise GoldValidationError(
                "Consensus sessions must start from the same canonical gold revision"
            )
        candidate_a = session_a.promoted_annotation
        candidate_b = session_b.promoted_annotation
        assert candidate_a is not None
        assert candidate_b is not None
        if candidate_a.reviewed_by == candidate_b.reviewed_by:
            raise GoldValidationError(
                "Consensus requires two distinct reviewer identities"
            )
        if _other_pages(candidate_a, session_a.page_index) != _other_pages(
            candidate_b, session_b.page_index
        ):
            raise GoldValidationError(
                "Consensus candidates disagree outside the active review page"
            )

    def _build_consensus(self, bundle: GoldConsensusBundle) -> GoldAnnotation:
        page_a = _semantic_page(_page(bundle.candidate_a, bundle.page_index))
        resolved = {
            "tasks": list(page_a["tasks"]),
            "reading_order": list(page_a["reading_order"]),
            "elements": dict(page_a["elements"]),
        }
        conflict_by_id = {item.id: item for item in bundle.conflicts}
        adjudicators = set()
        for conflict_id, decision in bundle.decisions.items():
            conflict = conflict_by_id[conflict_id]
            value = (
                conflict.candidate_a if decision.choice == "a" else conflict.candidate_b
            )
            adjudicators.add(decision.adjudicator)
            if conflict.kind == "tasks":
                resolved["tasks"] = list(value)
            elif conflict.kind == "reading_order":
                resolved["reading_order"] = list(value)
            elif conflict.kind == "element":
                if value is None:
                    resolved["elements"].pop(conflict.subject_id, None)
                else:
                    resolved["elements"][conflict.subject_id] = value
        page_payload: Dict[str, Any] = {
            "page_index": bundle.page_index,
            "tasks": resolved["tasks"],
            "elements": [
                resolved["elements"][key] for key in sorted(resolved["elements"])
            ],
        }
        if resolved["reading_order"]:
            page_payload["reading_order"] = resolved["reading_order"]
        consensus_page = GoldPageAnnotation.from_dict(page_payload)
        pages = {
            page.page_index: page
            for page in bundle.candidate_a.pages
            if page.page_index != bundle.page_index
        }
        pages[bundle.page_index] = consensus_page
        reviewers = f"{bundle.reviewer_a} + {bundle.reviewer_b}"
        if adjudicators:
            reviewers += " | adjudicated by " + ", ".join(sorted(adjudicators))
        notes = bundle.candidate_a.notes.rstrip()
        consensus_note = (
            f"Consensus review: independent reviewers {bundle.reviewer_a} and "
            f"{bundle.reviewer_b}"
        )
        if adjudicators:
            consensus_note += "; adjudicator(s): " + ", ".join(sorted(adjudicators))
        notes = (notes + "\n\n" + consensus_note).strip()
        result = GoldAnnotation(
            schema_version=bundle.candidate_a.schema_version,
            document_id=bundle.document_id,
            source_sha256=bundle.source_sha256,
            status="reviewed",
            annotated_by=bundle.candidate_a.annotated_by,
            reviewed_by=reviewers,
            notes=notes,
            pages=tuple(pages[key] for key in sorted(pages)),
        )
        validate_gold_against_spec(result, self._spec(bundle.document_id))
        return result

    def _audit_payload(self, bundle: GoldConsensusBundle) -> Dict[str, Any]:
        if bundle.consensus_annotation is None:
            raise GoldValidationError("Consensus annotation is not ready")
        return {
            "schema_version": CONSENSUS_SCHEMA_VERSION,
            "bundle_id": bundle.id,
            "document_id": bundle.document_id,
            "page_index": bundle.page_index,
            "source_sha256": bundle.source_sha256,
            "canonical_hash_at_open": bundle.canonical_hash_at_open,
            "session_a_id": bundle.session_a_id,
            "session_b_id": bundle.session_b_id,
            "reviewer_a": bundle.reviewer_a,
            "reviewer_b": bundle.reviewer_b,
            "candidate_a_hash": _annotation_hash(bundle.candidate_a),
            "candidate_b_hash": _annotation_hash(bundle.candidate_b),
            "conflicts": [item.to_dict() for item in bundle.conflicts],
            "decisions": [
                bundle.decisions[key].to_dict() for key in sorted(bundle.decisions)
            ],
            "consensus_hash": _annotation_hash(bundle.consensus_annotation),
            "published_at": bundle.published_at or None,
        }

    def _write_audit(
        self,
        bundle: GoldConsensusBundle,
        *,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if bundle.consensus_annotation is None:
            return
        resolved = payload or self._audit_payload(bundle)
        _atomic_write_json(
            self._bundle_dir(bundle.id) / "consensus-audit.json",
            resolved,
        )

    def _spec(self, document_id: str) -> CorpusDocumentSpec:
        return self.manifest.select([document_id])[0]

    def _canonical_gold_path(self, spec: CorpusDocumentSpec) -> Path:
        if not spec.gold_annotations_path:
            raise GoldValidationError(
                "Consensus publish requires gold_annotations_path in corpus manifest"
            )
        root = self.manifest_path.parent.resolve()
        path = (root / spec.gold_annotations_path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise GoldValidationError(
                f"Gold annotation path escapes corpus directory: {path}"
            ) from exc
        return path

    def _bundle_dir(self, bundle_id: str) -> Path:
        if not bundle_id or "/" in bundle_id or "\\" in bundle_id:
            raise ValueError("Invalid consensus bundle id")
        return self.workspace_dir / "consensus" / bundle_id

    def _bundle_file(self, bundle_id: str) -> Path:
        return self._bundle_dir(bundle_id) / self.BUNDLE_FILE

    def _write(self, bundle: GoldConsensusBundle) -> None:
        _atomic_write_json(self._bundle_file(bundle.id), bundle.to_dict())
        if bundle.consensus_annotation is not None:
            _atomic_write_json(
                self._bundle_dir(bundle.id) / "consensus-gold.json",
                bundle.consensus_annotation.to_dict(),
            )
            self._write_audit(bundle)
