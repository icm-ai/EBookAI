"""Auditable human workbench for promoting sparse gold annotations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import (
    GOLD_SCHEMA_VERSION,
    GoldAnnotation,
    GoldElement,
    GoldPageAnnotation,
    GoldValidationError,
    evaluate_gold,
    load_gold_annotation,
    validate_gold_against_spec,
)
from book.benchmark.models import CorpusDocumentSpec, CorpusManifest
from book.benchmark.review_plan import ReviewPlan, ReviewTarget, validate_review_plan
from book.benchmark.runner import default_parser_registry
from book.domain.models import Book, NodeType
from book.parsers.base import ParserBackendUnavailable


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
class GoldReviewDecision:
    """One explicit reviewer acknowledgement in a staged annotation."""

    subject: str
    subject_id: str
    decision: str
    reviewer: str
    created_at: str = field(default_factory=_utc_now)
    note: str = ""

    def __post_init__(self) -> None:
        if self.subject not in {"element", "task"}:
            raise GoldValidationError("Review subject must be element or task")
        if self.decision != "confirmed":
            raise GoldValidationError("Gold workbench decisions must be confirmed")
        if not self.subject_id.strip():
            raise GoldValidationError("Review subject_id must not be empty")
        if not self.reviewer.strip():
            raise GoldValidationError("Review decision must record reviewer")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldReviewDecision":
        return cls(
            subject=str(value["subject"]),
            subject_id=str(value["subject_id"]),
            decision=str(value["decision"]),
            reviewer=str(value["reviewer"]),
            created_at=str(value.get("created_at") or _utc_now()),
            note=str(value.get("note", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "subject_id": self.subject_id,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "created_at": self.created_at,
            "note": self.note,
        }


@dataclass
class GoldReviewSession:
    """Persisted review state for one document/page target."""

    id: str
    document_id: str
    page_index: int
    backend: str
    source_path: str
    source_sha256: str
    canonical_hash_at_open: Optional[str]
    annotation: GoldAnnotation
    book: Book
    page_width: float
    page_height: float
    created_at: str
    updated_at: str
    decisions: Dict[str, GoldReviewDecision] = field(default_factory=dict)
    promoted_annotation: Optional[GoldAnnotation] = None
    published_at: str = ""

    def decision_key(self, subject: str, subject_id: str) -> str:
        return f"{subject}:{subject_id}"

    def to_dict(self) -> Dict[str, Any]:
        evaluation = evaluate_gold(self.book, self.annotation)
        page = next(
            item for item in self.annotation.pages if item.page_index == self.page_index
        )
        parser_nodes = []
        for position, node in enumerate(self.book.walk()):
            refs = [
                ref for ref in node.source if ref.page_index == self.page_index
            ]
            if not refs:
                continue
            parser_nodes.append(
                {
                    "position": position,
                    "id": node.id,
                    "type": node.type.value,
                    "text": node.content,
                    "bbox": (
                        list(refs[0].bbox) if refs[0].bbox is not None else None
                    ),
                    "attrs": node.attrs,
                }
            )
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_index": self.page_index,
            "backend": self.backend,
            "source_sha256": self.source_sha256,
            "canonical_hash_at_open": self.canonical_hash_at_open,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at,
            "page": {
                "width": self.page_width,
                "height": self.page_height,
                "tasks": list(page.tasks),
                "elements": [item.to_dict() for item in page.elements],
                "reading_order": list(page.reading_order),
            },
            "annotation": self.annotation.to_dict(),
            "evaluation": evaluation.to_dict(),
            "parser_nodes": parser_nodes,
            "decisions": [
                self.decisions[key].to_dict() for key in sorted(self.decisions)
            ],
            "preflight": self.preflight(),
            "promoted_annotation": (
                self.promoted_annotation.to_dict()
                if self.promoted_annotation is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GoldReviewSession":
        decisions = {
            f"{item['subject']}:{item['subject_id']}": GoldReviewDecision.from_dict(
                item
            )
            for item in value.get("decisions", [])
        }
        promoted = value.get("promoted_annotation")
        return cls(
            id=str(value["id"]),
            document_id=str(value["document_id"]),
            page_index=int(value["page_index"]),
            backend=str(value["backend"]),
            source_path=str(value["source_path"]),
            source_sha256=str(value["source_sha256"]),
            canonical_hash_at_open=(
                str(value["canonical_hash_at_open"])
                if value.get("canonical_hash_at_open") is not None
                else None
            ),
            annotation=GoldAnnotation.from_dict(value["annotation"]),
            book=Book.from_dict(value["book"]),
            page_width=float(value["page_width"]),
            page_height=float(value["page_height"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            decisions=decisions,
            promoted_annotation=(
                GoldAnnotation.from_dict(promoted) if promoted else None
            ),
            published_at=str(value.get("published_at", "")),
        )

    def persisted_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_index": self.page_index,
            "backend": self.backend,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "canonical_hash_at_open": self.canonical_hash_at_open,
            "annotation": self.annotation.to_dict(),
            "book": self.book.to_dict(),
            "page_width": self.page_width,
            "page_height": self.page_height,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "decisions": [
                self.decisions[key].to_dict() for key in sorted(self.decisions)
            ],
            "promoted_annotation": (
                self.promoted_annotation.to_dict()
                if self.promoted_annotation is not None
                else None
            ),
            "published_at": self.published_at,
        }

    def preflight(self) -> Dict[str, Any]:
        page = next(
            item for item in self.annotation.pages if item.page_index == self.page_index
        )
        missing_elements = [
            element.id
            for element in page.elements
            if self.decision_key("element", element.id) not in self.decisions
        ]
        missing_tasks = [
            task
            for task in page.tasks
            if self.decision_key("task", task) not in self.decisions
        ]
        blockers: List[str] = []
        if "reading_order" in page.tasks:
            element_ids = {element.id for element in page.elements}
            ordered_ids = set(page.reading_order)
            missing_order_ids = sorted(element_ids - ordered_ids)
            if missing_order_ids:
                blockers.append(
                    "reading_order missing element ids: "
                    + ", ".join(missing_order_ids)
                )
        if missing_elements:
            blockers.append(
                "unconfirmed elements: " + ", ".join(sorted(missing_elements))
            )
        if missing_tasks:
            blockers.append("unconfirmed tasks: " + ", ".join(sorted(missing_tasks)))
        if self.annotation.status != "draft":
            blockers.append("staged annotation must remain draft before promotion")
        return {
            "ready": not blockers,
            "blockers": blockers,
            "missing_elements": sorted(missing_elements),
            "missing_tasks": sorted(missing_tasks),
        }


class GoldReviewStore:
    """Disk-backed review workbench over a source-pinned corpus manifest."""

    SESSION_FILE = "gold-review-session.json"

    def __init__(
        self,
        manifest_path: Path,
        review_plan_path: Path,
        cache_dir: Path,
        workspace_dir: Path,
    ) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        self.review_plan_path = Path(review_plan_path).resolve()
        self.cache_dir = Path(cache_dir).resolve()
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.corpus = CorpusStore(self.manifest_path, self.cache_dir)
        self.manifest = self.corpus.manifest
        self.plan = ReviewPlan.load(self.review_plan_path)
        validate_review_plan(self.plan, self.manifest)
        self.registry = default_parser_registry()
        self._lock = threading.RLock()

    def queue(self) -> Dict[str, Any]:
        by_id = {item.id: item for item in self.manifest.documents}
        annotation_cache: Dict[str, Optional[GoldAnnotation]] = {}
        items = []
        for target in self.plan.targets:
            if target.document_id not in annotation_cache:
                annotation_cache[target.document_id] = load_gold_annotation(
                    self.manifest_path, by_id[target.document_id]
                )
            annotation = annotation_cache[target.document_id]
            annotated_pages = (
                {page.page_index for page in annotation.pages}
                if annotation is not None
                else set()
            )
            if target.page_index in annotated_pages:
                status = annotation.status if annotation is not None else "unannotated"
            else:
                status = "unannotated"
            items.append(
                {
                    **target.to_dict(),
                    "annotation_status": status,
                    "source_sha256": by_id[target.document_id].sha256,
                    "title": by_id[target.document_id].title,
                    "language": by_id[target.document_id].language,
                    "page_count": by_id[target.document_id].page_count,
                }
            )
        return {
            "corpus_id": self.manifest.corpus_id,
            "target_count": len(items),
            "items": items,
        }

    def create(
        self,
        document_id: str,
        page_index: int,
        *,
        backend: str = "pymupdf",
    ) -> GoldReviewSession:
        with self._lock:
            spec = self._spec(document_id)
            target = self._target(document_id, page_index)
            materialized = self.corpus.fetch([document_id])[0]
            source = Path(materialized.path)
            adapter = self.registry.get(backend)
            profile = adapter.profile()
            if not profile.get("available", False):
                raise ParserBackendUnavailable(
                    f"Parser backend {backend!r} is unavailable"
                )
            book = adapter.parse(source)
            canonical = load_gold_annotation(self.manifest_path, spec)
            annotation = self._stage_annotation(spec, target, canonical)
            validate_gold_against_spec(annotation, spec)

            with fitz.open(str(source)) as document:
                page = document.load_page(page_index)
                width = float(page.rect.width)
                height = float(page.rect.height)

            now = _utc_now()
            session = GoldReviewSession(
                id=str(uuid.uuid4()),
                document_id=document_id,
                page_index=page_index,
                backend=backend,
                source_path=str(source),
                source_sha256=spec.sha256,
                canonical_hash_at_open=_annotation_hash(canonical),
                annotation=annotation,
                book=book,
                page_width=width,
                page_height=height,
                created_at=now,
                updated_at=now,
            )
            self._write(session)
            return session

    def get(self, session_id: str) -> GoldReviewSession:
        path = self._session_file(session_id)
        if not path.is_file():
            raise FileNotFoundError(f"Gold review session not found: {session_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise GoldValidationError("Gold review session root must be an object")
        return GoldReviewSession.from_dict(payload)

    def render_page(
        self,
        session_id: str,
        *,
        scale: float = 1.5,
    ) -> bytes:
        if not 0.5 <= scale <= 4.0:
            raise ValueError("render scale must be between 0.5 and 4.0")
        session = self.get(session_id)
        source = Path(session.source_path)
        with fitz.open(str(source)) as document:
            page = document.load_page(session.page_index)
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                alpha=False,
            )
            return pixmap.tobytes("png")

    def set_tasks(
        self,
        session_id: str,
        tasks: List[str],
    ) -> GoldReviewSession:
        with self._lock:
            session = self.get(session_id)
            page = self._session_page(session)
            reading_order = page.reading_order if "reading_order" in tasks else ()
            updated_page = GoldPageAnnotation(
                page_index=page.page_index,
                tasks=tuple(tasks),
                elements=page.elements,
                reading_order=reading_order,
            )
            session.annotation = self._replace_page(session.annotation, updated_page)
            allowed = {f"task:{task}" for task in updated_page.tasks}
            session.decisions = {
                key: value
                for key, value in session.decisions.items()
                if not key.startswith("task:") or key in allowed
            }
            return self._touch(session)

    def upsert_element(
        self,
        session_id: str,
        value: Dict[str, Any],
    ) -> GoldReviewSession:
        with self._lock:
            session = self.get(session_id)
            page = self._session_page(session)
            element = GoldElement.from_dict(value)
            existing = {item.id: item for item in page.elements}
            existing[element.id] = element
            updated_page = GoldPageAnnotation(
                page_index=page.page_index,
                tasks=page.tasks,
                elements=tuple(existing[key] for key in sorted(existing)),
                reading_order=page.reading_order,
            )
            session.annotation = self._replace_page(session.annotation, updated_page)
            session.decisions.pop(
                session.decision_key("element", element.id),
                None,
            )
            session.promoted_annotation = None
            return self._touch(session)

    def delete_element(
        self,
        session_id: str,
        element_id: str,
    ) -> GoldReviewSession:
        with self._lock:
            session = self.get(session_id)
            page = self._session_page(session)
            if element_id not in {item.id for item in page.elements}:
                raise KeyError(f"Gold element not found: {element_id}")
            updated_page = GoldPageAnnotation(
                page_index=page.page_index,
                tasks=page.tasks,
                elements=tuple(
                    item for item in page.elements if item.id != element_id
                ),
                reading_order=tuple(
                    item for item in page.reading_order if item != element_id
                ),
            )
            session.annotation = self._replace_page(session.annotation, updated_page)
            session.decisions.pop(
                session.decision_key("element", element_id),
                None,
            )
            session.promoted_annotation = None
            return self._touch(session)

    def set_reading_order(
        self,
        session_id: str,
        reading_order: List[str],
    ) -> GoldReviewSession:
        with self._lock:
            session = self.get(session_id)
            page = self._session_page(session)
            if "reading_order" not in page.tasks:
                raise GoldValidationError(
                    "reading_order task must be enabled before setting order"
                )
            updated_page = GoldPageAnnotation(
                page_index=page.page_index,
                tasks=page.tasks,
                elements=page.elements,
                reading_order=tuple(reading_order),
            )
            session.annotation = self._replace_page(session.annotation, updated_page)
            session.decisions.pop(
                session.decision_key("task", "reading_order"),
                None,
            )
            session.promoted_annotation = None
            return self._touch(session)

    def confirm(
        self,
        session_id: str,
        *,
        subject: str,
        subject_id: str,
        reviewer: str,
        note: str = "",
    ) -> GoldReviewSession:
        with self._lock:
            session = self.get(session_id)
            page = self._session_page(session)
            if subject == "element":
                if subject_id not in {item.id for item in page.elements}:
                    raise KeyError(f"Gold element not found: {subject_id}")
            elif subject == "task":
                if subject_id not in set(page.tasks):
                    raise KeyError(f"Gold task not found on page: {subject_id}")
            decision = GoldReviewDecision(
                subject=subject,
                subject_id=subject_id,
                decision="confirmed",
                reviewer=reviewer,
                note=note,
            )
            session.decisions[session.decision_key(subject, subject_id)] = decision
            session.promoted_annotation = None
            return self._touch(session)

    def promote(
        self,
        session_id: str,
        *,
        reviewer: str,
        note: str = "",
    ) -> GoldReviewSession:
        with self._lock:
            if not reviewer.strip():
                raise GoldValidationError("Promotion requires a non-empty reviewer")
            session = self.get(session_id)
            preflight = session.preflight()
            if not preflight["ready"]:
                raise GoldValidationError(
                    "Gold promotion blocked: " + "; ".join(preflight["blockers"])
                )
            decision_reviewers = {
                item.reviewer for item in session.decisions.values()
            }
            if reviewer not in decision_reviewers:
                raise GoldValidationError(
                    "Promotion reviewer must have confirmed at least one task or element"
                )
            spec = self._spec(session.document_id)
            promoted = replace(
                session.annotation,
                status="reviewed",
                reviewed_by=reviewer.strip(),
                notes=self._promotion_notes(session.annotation.notes, note),
            )
            validate_gold_against_spec(promoted, spec)
            session.promoted_annotation = promoted
            session.updated_at = _utc_now()
            self._write(session)
            promoted_path = self._session_dir(session.id) / "promoted-gold.json"
            _atomic_write_json(promoted_path, promoted.to_dict())
            return session

    def publish(self, session_id: str) -> GoldReviewSession:
        """Explicitly publish a promoted annotation into the canonical corpus gold."""

        with self._lock:
            session = self.get(session_id)
            if session.promoted_annotation is None:
                raise GoldValidationError("Promote the annotation before publishing")
            spec = self._spec(session.document_id)
            canonical = load_gold_annotation(self.manifest_path, spec)
            if _annotation_hash(canonical) != session.canonical_hash_at_open:
                raise GoldValidationError(
                    "Canonical gold changed since this review session opened"
                )
            path = self._canonical_gold_path(spec)
            _atomic_write_json(path, session.promoted_annotation.to_dict())
            session.canonical_hash_at_open = _annotation_hash(
                session.promoted_annotation
            )
            session.annotation = session.promoted_annotation
            session.published_at = _utc_now()
            session.updated_at = session.published_at
            self._write(session)
            return session

    def promoted_path(self, session_id: str) -> Path:
        session = self.get(session_id)
        if session.promoted_annotation is None:
            raise FileNotFoundError("No promoted gold artifact exists")
        path = self._session_dir(session_id) / "promoted-gold.json"
        if not path.is_file():
            _atomic_write_json(path, session.promoted_annotation.to_dict())
        return path

    def _spec(self, document_id: str) -> CorpusDocumentSpec:
        return self.manifest.select([document_id])[0]

    def _target(self, document_id: str, page_index: int) -> ReviewTarget:
        for target in self.plan.targets:
            if target.document_id == document_id and target.page_index == page_index:
                return target
        raise KeyError(f"Review target not found: {document_id} page {page_index}")

    def _stage_annotation(
        self,
        spec: CorpusDocumentSpec,
        target: ReviewTarget,
        canonical: Optional[GoldAnnotation],
    ) -> GoldAnnotation:
        if canonical is None:
            return GoldAnnotation(
                schema_version=GOLD_SCHEMA_VERSION,
                document_id=spec.id,
                source_sha256=spec.sha256,
                status="draft",
                annotated_by="EBookAI Gold Review Workbench",
                reviewed_by="",
                notes="Created from the Milestone 16 human-review queue.",
                pages=(
                    GoldPageAnnotation(
                        page_index=target.page_index,
                        tasks=target.tasks,
                    ),
                ),
            )

        pages = {page.page_index: page for page in canonical.pages}
        if target.page_index not in pages:
            pages[target.page_index] = GoldPageAnnotation(
                page_index=target.page_index,
                tasks=target.tasks,
            )
        return GoldAnnotation(
            schema_version=canonical.schema_version,
            document_id=canonical.document_id,
            source_sha256=canonical.source_sha256,
            status="draft",
            annotated_by=canonical.annotated_by,
            reviewed_by="",
            notes=canonical.notes,
            pages=tuple(pages[key] for key in sorted(pages)),
        )

    def _canonical_gold_path(self, spec: CorpusDocumentSpec) -> Path:
        if not spec.gold_annotations_path:
            raise GoldValidationError(
                "Canonical publish requires gold_annotations_path in corpus manifest"
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

    @staticmethod
    def _session_page(session: GoldReviewSession) -> GoldPageAnnotation:
        for page in session.annotation.pages:
            if page.page_index == session.page_index:
                return page
        raise GoldValidationError("Staged annotation is missing the review page")

    @staticmethod
    def _replace_page(
        annotation: GoldAnnotation,
        updated_page: GoldPageAnnotation,
    ) -> GoldAnnotation:
        pages = {
            page.page_index: page
            for page in annotation.pages
            if page.page_index != updated_page.page_index
        }
        pages[updated_page.page_index] = updated_page
        return replace(
            annotation,
            status="draft",
            reviewed_by="",
            pages=tuple(pages[key] for key in sorted(pages)),
        )

    @staticmethod
    def _promotion_notes(existing: str, note: str) -> str:
        note = note.strip()
        if not note:
            return existing
        return (existing.rstrip() + "\n\nReview: " + note).strip()

    def _session_dir(self, session_id: str) -> Path:
        if not session_id or "/" in session_id or "\\" in session_id:
            raise ValueError("Invalid gold review session id")
        return self.workspace_dir / session_id

    def _session_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / self.SESSION_FILE

    def _write(self, session: GoldReviewSession) -> None:
        session_dir = self._session_dir(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self._session_file(session.id), session.persisted_dict())

    def _touch(self, session: GoldReviewSession) -> GoldReviewSession:
        session.promoted_annotation = None
        session.published_at = ""
        session.updated_at = _utc_now()
        self._write(session)
        return session
