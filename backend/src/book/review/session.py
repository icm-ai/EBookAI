"""Persistent human-review sessions for BookIR."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from book.domain.models import Book
from book.orchestration import OrchestrationResult, ParserOrchestrator
from book.parsers import MarkerAdapter, MinerUAdapter, ParserRegistry, PyMuPDFAdapter
from book.publication import (
    PublicationReport,
    ReleaseManifest,
    ReleasePipeline,
    load_trusted_key_ids,
)
from book.quality import QualityEngine, QualityIssue, QualityReport
from book.repair import AIRepairProposal, PatchEngine


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ReviewDecision:
    """Auditable human decision for one quality issue."""

    issue_id: str
    decision: str
    issue: Dict[str, Any]
    patch_id: Optional[str] = None
    reason: str = ""
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.decision not in {"accepted", "rejected"}:
            raise ValueError("review decision must be accepted or rejected")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "decision": self.decision,
            "issue": self.issue,
            "patch_id": self.patch_id,
            "reason": self.reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewDecision":
        return cls(
            issue_id=str(value["issue_id"]),
            decision=str(value["decision"]),
            issue=dict(value.get("issue", {})),
            patch_id=(
                str(value["patch_id"]) if value.get("patch_id") is not None else None
            ),
            reason=str(value.get("reason", "")),
            created_at=str(value.get("created_at") or _utc_now()),
        )


@dataclass
class ReviewSession:
    """Persisted source + BookIR + review state."""

    id: str
    source_filename: str
    source_file: str
    book: Book
    quality_report: QualityReport
    created_at: str
    updated_at: str
    decisions: Dict[str, ReviewDecision] = field(default_factory=dict)
    ai_proposals: Dict[str, AIRepairProposal] = field(default_factory=dict)
    publication_report: Optional[PublicationReport] = None
    release_manifest: Optional[ReleaseManifest] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_filename": self.source_filename,
            "source_file": self.source_file,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "book": self.book.to_dict(),
            "quality_report": self.quality_report.to_dict(),
            "decisions": [
                self.decisions[key].to_dict() for key in sorted(self.decisions)
            ],
            "ai_proposals": [
                self.ai_proposals[key].to_dict() for key in sorted(self.ai_proposals)
            ],
            "publication_report": (
                self.publication_report.to_dict()
                if self.publication_report is not None
                else None
            ),
            "release_manifest": (
                self.release_manifest.to_dict()
                if self.release_manifest is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewSession":
        decisions = {
            item["issue_id"]: ReviewDecision.from_dict(item)
            for item in value.get("decisions", [])
        }
        ai_proposals = {
            item["id"]: AIRepairProposal.from_dict(item)
            for item in value.get("ai_proposals", [])
        }
        publication_report = value.get("publication_report")
        release_manifest = value.get("release_manifest")
        return cls(
            id=str(value["id"]),
            source_filename=str(value["source_filename"]),
            source_file=str(value["source_file"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            book=Book.from_dict(value["book"]),
            quality_report=QualityReport.from_dict(value["quality_report"]),
            decisions=decisions,
            ai_proposals=ai_proposals,
            publication_report=(
                PublicationReport.from_dict(publication_report)
                if publication_report
                else None
            ),
            release_manifest=(
                ReleaseManifest.from_dict(release_manifest)
                if release_manifest
                else None
            ),
        )

    def issue_resolutions(self) -> List[Dict[str, Any]]:
        current = {issue.id: issue for issue in self.quality_report.issues}
        patches = {patch.id: patch for patch in self.book.patches}
        records: Dict[str, Dict[str, Any]] = {}

        for issue_id, issue in current.items():
            decision = self.decisions.get(issue_id)
            patch = (
                patches.get(decision.patch_id)
                if decision is not None and decision.patch_id
                else None
            )
            if decision is None:
                state = "open"
            elif decision.decision == "rejected":
                state = "waived"
            elif patch is not None and patch.undone:
                state = "reopened"
            else:
                state = "open"
            records[issue_id] = {
                "issue_id": issue_id,
                "state": state,
                "current": True,
                "severity": issue.severity.value,
                "code": issue.code,
                "decision": decision.to_dict() if decision else None,
            }

        for issue_id, decision in self.decisions.items():
            if issue_id in records:
                continue
            patch = patches.get(decision.patch_id) if decision.patch_id else None
            state = (
                "reopened"
                if patch is not None and patch.undone
                else "resolved"
                if decision.decision == "accepted"
                else "waived"
            )
            records[issue_id] = {
                "issue_id": issue_id,
                "state": state,
                "current": False,
                "severity": str(decision.issue.get("severity", "")),
                "code": str(decision.issue.get("code", issue_id)),
                "decision": decision.to_dict(),
            }

        return [records[key] for key in sorted(records)]

    def issue_resolution_map(self) -> Dict[str, str]:
        return {item["issue_id"]: item["state"] for item in self.issue_resolutions()}

    def response_dict(self) -> Dict[str, Any]:
        payload = self.to_dict()
        payload["orchestration"] = self.book.metadata.extra.get("orchestration", {})
        engine = PatchEngine()
        payload["patch_history"] = [
            engine.describe_patch(self.book, patch.id) for patch in self.book.patches
        ]
        payload["issue_resolutions"] = self.issue_resolutions()
        return payload


def default_review_orchestrator() -> ParserOrchestrator:
    """Create the default cheap-first parser orchestrator for review uploads."""

    registry = ParserRegistry(
        [
            PyMuPDFAdapter(),
            MinerUAdapter(),
            MarkerAdapter(),
        ]
    )
    return ParserOrchestrator(registry)


class ReviewSessionStore:
    """Disk-backed review sessions with atomic JSON persistence."""

    SESSION_FILE = "session.json"

    def __init__(
        self,
        root_dir: Path,
        *,
        orchestrator: Optional[ParserOrchestrator] = None,
        quality_engine: Optional[QualityEngine] = None,
        patch_engine: Optional[PatchEngine] = None,
        release_pipeline: Optional[ReleasePipeline] = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.orchestrator = orchestrator or default_review_orchestrator()
        self.quality_engine = quality_engine or QualityEngine()
        self.patch_engine = patch_engine or PatchEngine()
        self.release_pipeline = release_pipeline or ReleasePipeline()
        self._lock = threading.RLock()

    def create(self, source_path: Path, source_filename: str) -> ReviewSession:
        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        session_id = str(uuid.uuid4())
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=False)

        suffix = source_path.suffix.lower() or ".pdf"
        stored_source = session_dir / f"source{suffix}"
        shutil.copy2(source_path, stored_source)

        try:
            result = self.orchestrator.run(stored_source)
            if result.book is None or result.quality_report is None:
                raise ValueError("Parser orchestration produced no reviewable BookIR")

            now = _utc_now()
            book = Book.from_dict(result.book.to_dict())
            book.metadata.source_path = source_filename
            session = ReviewSession(
                id=session_id,
                source_filename=source_filename,
                source_file=stored_source.name,
                book=book,
                quality_report=result.quality_report,
                created_at=now,
                updated_at=now,
            )
            self._attach_review_metadata(session)
            self._write(session)
            return session
        except Exception:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise

    def get(self, session_id: str) -> ReviewSession:
        session_file = self._session_file(session_id)
        if not session_file.is_file():
            raise FileNotFoundError(f"Review session not found: {session_id}")
        with session_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Review session payload must be an object")
        return ReviewSession.from_dict(payload)

    def source_path(self, session_id: str) -> Path:
        session = self.get(session_id)
        path = self._session_dir(session_id) / session.source_file
        resolved = path.resolve()
        resolved.relative_to(self._session_dir(session_id).resolve())
        if not resolved.is_file():
            raise FileNotFoundError(f"Review source not found: {session_id}")
        return resolved

    def accept_issue(self, session_id: str, issue_id: str) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            issue = self._find_issue(session, issue_id)
            if issue.suggested_patch is None:
                raise ValueError(f"Issue {issue_id!r} has no suggested patch")

            session.book = self.patch_engine.apply(
                session.book,
                issue.suggested_patch,
            )
            session.quality_report = self.quality_engine.analyze(session.book)
            session.decisions[issue_id] = ReviewDecision(
                issue_id=issue_id,
                decision="accepted",
                issue=issue.to_dict(),
                patch_id=issue.suggested_patch.id,
            )
            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def reject_issue(
        self,
        session_id: str,
        issue_id: str,
        *,
        reason: str = "",
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            issue = self._find_issue(session, issue_id)
            session.decisions[issue_id] = ReviewDecision(
                issue_id=issue_id,
                decision="rejected",
                issue=issue.to_dict(),
                patch_id=(issue.suggested_patch.id if issue.suggested_patch else None),
                reason=reason,
            )
            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def add_ai_proposal(
        self,
        session_id: str,
        proposal: AIRepairProposal,
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            issue = self._find_issue(session, proposal.issue_id)
            if issue.id != proposal.issue_id:
                raise ValueError(
                    "AI proposal issue does not match current quality issue"
                )
            self.patch_engine.validator.validate(session.book, proposal.patch)
            session.ai_proposals[proposal.id] = proposal
            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def accept_ai_proposal(
        self,
        session_id: str,
        proposal_id: str,
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            proposal = self._find_ai_proposal(session, proposal_id)
            if proposal.status != "pending":
                raise ValueError(f"AI proposal {proposal_id!r} is not pending")

            session.book = self.patch_engine.apply(session.book, proposal.patch)
            session.quality_report = self.quality_engine.analyze(session.book)
            session.ai_proposals[proposal_id] = proposal.with_status("accepted")
            for other_id, other in list(session.ai_proposals.items()):
                if (
                    other_id != proposal_id
                    and other.issue_id == proposal.issue_id
                    and other.status == "pending"
                ):
                    session.ai_proposals[other_id] = other.with_status("superseded")

            session.decisions[proposal.issue_id] = ReviewDecision(
                issue_id=proposal.issue_id,
                decision="accepted",
                issue=proposal.issue,
                patch_id=proposal.patch.id,
                reason=(
                    f"Accepted AI proposal {proposal.id} "
                    f"from {proposal.provider}/{proposal.model}"
                ),
            )
            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def reject_ai_proposal(
        self,
        session_id: str,
        proposal_id: str,
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            proposal = self._find_ai_proposal(session, proposal_id)
            if proposal.status != "pending":
                raise ValueError(f"AI proposal {proposal_id!r} is not pending")
            session.ai_proposals[proposal_id] = proposal.with_status("rejected")
            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def undo_patch(self, session_id: str, patch_id: str) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            session.book = self.patch_engine.undo(session.book, patch_id)
            session.quality_report = self.quality_engine.analyze(session.book)

            for proposal_id, proposal in list(session.ai_proposals.items()):
                if proposal.patch.id == patch_id and proposal.status == "accepted":
                    session.ai_proposals[proposal_id] = proposal.with_status("undone")

            session.publication_report = None
            session.release_manifest = None
            session.updated_at = _utc_now()
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def save_publication_report(
        self,
        session_id: str,
        report: PublicationReport,
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            session.publication_report = report
            session.release_manifest = None
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def build_release(
        self,
        session_id: str,
        *,
        require_epubcheck: bool = False,
        require_signature: bool = False,
    ) -> ReviewSession:
        with self._lock:
            session = self.get(session_id)
            source_path = self._session_dir(session_id) / session.source_file
            result = self.release_pipeline.build(
                source_path=source_path,
                source_filename=session.source_filename,
                book=session.book,
                quality_report=session.quality_report,
                issue_resolutions=session.issue_resolution_map(),
                output_dir=self.release_dir(session_id),
                require_epubcheck=require_epubcheck,
                require_signature=require_signature,
            )
            session.publication_report = result.publication_report
            session.release_manifest = result.manifest
            self._attach_review_metadata(session)
            self._write(session)
            return session

    def verify_release(self, session_id: str) -> Dict[str, Any]:
        session = self.get(session_id)
        if session.release_manifest is None:
            raise ValueError("No current release bundle exists for this review state")
        return self.release_pipeline.verify_bundle(
            self.release_bundle_path(session_id),
            trusted_key_ids=load_trusted_key_ids(),
        )

    def get_issue(self, session_id: str, issue_id: str) -> QualityIssue:
        return self._find_issue(self.get(session_id), issue_id)

    def epub_path(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        return self._session_dir(session_id) / "reviewed.epub"

    def release_dir(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        return self._session_dir(session_id) / "release"

    def release_bundle_path(self, session_id: str) -> Path:
        session = self.get(session_id)
        if session.release_manifest is None:
            raise FileNotFoundError(
                f"No current release bundle exists for review session: {session_id}"
            )
        path = self.release_dir(session_id) / ReleasePipeline.BUNDLE_NAME
        if not path.is_file():
            raise FileNotFoundError(
                f"Release bundle not found for review session: {session_id}"
            )
        return path

    def _find_issue(self, session: ReviewSession, issue_id: str) -> QualityIssue:
        for issue in session.quality_report.issues:
            if issue.id == issue_id:
                return issue
        raise KeyError(f"Quality issue not found: {issue_id}")

    @staticmethod
    def _find_ai_proposal(
        session: ReviewSession,
        proposal_id: str,
    ) -> AIRepairProposal:
        proposal = session.ai_proposals.get(proposal_id)
        if proposal is None:
            raise KeyError(f"AI repair proposal not found: {proposal_id}")
        return proposal

    def _write(self, session: ReviewSession) -> None:
        session_dir = self._session_dir(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        if session.release_manifest is None:
            shutil.rmtree(session_dir / "release", ignore_errors=True)
        target = session_dir / self.SESSION_FILE
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(
                session.to_dict(),
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        temporary.replace(target)

    @staticmethod
    def _attach_review_metadata(session: ReviewSession) -> None:
        session.book.metadata.extra["review"] = {
            "session_id": session.id,
            "updated_at": session.updated_at,
            "decisions": [
                session.decisions[key].to_dict() for key in sorted(session.decisions)
            ],
            "ai_proposals": [
                session.ai_proposals[key].to_dict()
                for key in sorted(session.ai_proposals)
            ],
            "issue_resolutions": session.issue_resolutions(),
            "publication_report": (
                session.publication_report.to_dict()
                if session.publication_report is not None
                else None
            ),
        }
        session.book.metadata.extra.setdefault("quality", {})[
            "report"
        ] = session.quality_report.to_dict()

    def _session_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / self.SESSION_FILE

    def _session_dir(self, session_id: str) -> Path:
        self._validate_session_id(session_id)
        return self.root_dir / session_id

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        try:
            parsed = uuid.UUID(session_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid review session id") from exc
        if str(parsed) != session_id:
            raise ValueError("Invalid review session id")
