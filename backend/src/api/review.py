"""Human review API for source-grounded BookIR inspection and repair."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from book.compiler import EpubCompiler
from book.publication import PublicationQAEngine
from book.repair import (
    AIRepairProposalError,
    AIRepairProposalGenerator,
    PatchUndoError,
    SourceEvidenceRenderer,
)
from book.review import ReviewSessionStore
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from services.ai_service import AIService
from starlette.concurrency import run_in_threadpool

from config import MAX_FILE_SIZE, OUTPUT_DIR, ai_config

router = APIRouter(prefix="/review", tags=["review"])

REVIEW_DIR = OUTPUT_DIR / "review"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
review_store = ReviewSessionStore(REVIEW_DIR)
epub_compiler = EpubCompiler()
ai_repair_generator = AIRepairProposalGenerator()
source_evidence_renderer = SourceEvidenceRenderer()
publication_qa_engine = PublicationQAEngine()


class RejectIssueRequest(BaseModel):
    reason: str = ""


class AIProposalRequest(BaseModel):
    provider: Optional[str] = None
    max_tokens: int = 1200
    include_source_images: bool = False


@router.get("/ai-providers")
async def get_review_ai_providers():
    return {
        "providers": ai_config.get_available_providers(),
        "default": ai_config.DEFAULT_AI_PROVIDER,
    }


@router.post("/sessions", status_code=201)
async def create_review_session(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(safe_filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Human review currently accepts PDF sources only",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    incoming = REVIEW_DIR / f".incoming-{uuid.uuid4()}.pdf"
    incoming.write_bytes(content)
    try:
        session = await run_in_threadpool(
            review_store.create,
            incoming,
            safe_filename,
        )
        return session.response_dict()
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Review session creation failed: {exc}",
        ) from exc
    finally:
        incoming.unlink(missing_ok=True)


@router.get("/sessions/{session_id}")
async def get_review_session(session_id: str):
    try:
        session = await run_in_threadpool(review_store.get, session_id)
        return session.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/source")
async def get_review_source(session_id: str):
    try:
        session = await run_in_threadpool(review_store.get, session_id)
        path = await run_in_threadpool(review_store.source_path, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{session.source_filename}"'
        },
    )


@router.post("/sessions/{session_id}/issues/{issue_id}/accept")
async def accept_review_issue(session_id: str, issue_id: str):
    try:
        session = await run_in_threadpool(
            review_store.accept_issue,
            session_id,
            issue_id,
        )
        return session.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/issues/{issue_id}/reject")
async def reject_review_issue(
    session_id: str,
    issue_id: str,
    request: RejectIssueRequest,
):
    try:
        session = await run_in_threadpool(
            review_store.reject_issue,
            session_id,
            issue_id,
            reason=request.reason,
        )
        return session.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/issues/{issue_id}/ai-proposals")
async def generate_ai_repair_proposal(
    session_id: str,
    issue_id: str,
    request: AIProposalRequest,
):
    if request.max_tokens < 128 or request.max_tokens > 4096:
        raise HTTPException(
            status_code=400,
            detail="max_tokens must be between 128 and 4096",
        )

    try:
        session = await run_in_threadpool(review_store.get, session_id)
        issue = await run_in_threadpool(
            review_store.get_issue,
            session_id,
            issue_id,
        )
        prompt = ai_repair_generator.build_prompt(session.book, issue)
        source_images = []
        if request.include_source_images:
            source_path = await run_in_threadpool(
                review_store.source_path,
                session_id,
            )
            source_images = await run_in_threadpool(
                source_evidence_renderer.render_issue,
                source_path,
                session.book,
                issue,
            )
            if not source_images:
                raise AIRepairProposalError(
                    "No renderable source bbox is available for vision grounding"
                )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIRepairProposalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        ai_service = AIService(provider=request.provider)
        result = await ai_service.complete_prompt(
            prompt,
            max_tokens=request.max_tokens,
            provider=request.provider,
            images=[item.to_model_image() for item in source_images] or None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI repair provider unavailable: {exc}",
        ) from exc

    try:
        proposal = ai_repair_generator.parse_response(
            session.book,
            issue,
            result.content,
            provider=result.provider,
            model=result.model,
            input_mode=("vision" if source_images else "text"),
            source_image_refs=tuple(item.ref_key for item in source_images),
        )
        updated = await run_in_threadpool(
            review_store.add_ai_proposal,
            session_id,
            proposal,
        )
        return updated.response_dict()
    except AIRepairProposalError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"AI proposal rejected by grounding policy: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/ai-proposals/{proposal_id}/accept")
async def accept_ai_repair_proposal(session_id: str, proposal_id: str):
    try:
        session = await run_in_threadpool(
            review_store.accept_ai_proposal,
            session_id,
            proposal_id,
        )
        return session.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/ai-proposals/{proposal_id}/reject")
async def reject_ai_repair_proposal(session_id: str, proposal_id: str):
    try:
        session = await run_in_threadpool(
            review_store.reject_ai_proposal,
            session_id,
            proposal_id,
        )
        return session.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/patches/{patch_id}/undo")
async def undo_review_patch(session_id: str, patch_id: str):
    try:
        session = await run_in_threadpool(
            review_store.undo_patch,
            session_id,
            patch_id,
        )
        return session.response_dict()
    except PatchUndoError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/publication-qa")
async def run_publication_qa(session_id: str):
    try:
        session = await run_in_threadpool(review_store.get, session_id)
        output_path = review_store.epub_path(session_id)
        await run_in_threadpool(
            epub_compiler.compile,
            session.book,
            output_path,
        )
        report = await run_in_threadpool(
            publication_qa_engine.analyze,
            session.book,
            session.quality_report,
            issue_resolutions=session.issue_resolution_map(),
            epub_path=output_path,
        )
        updated = await run_in_threadpool(
            review_store.save_publication_report,
            session_id,
            report,
        )
        return updated.response_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/export/bookir")
async def export_review_bookir(session_id: str):
    try:
        session = await run_in_threadpool(review_store.get, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = f"{Path(session.source_filename).stem}.bookir.json"
    return Response(
        content=session.book.to_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sessions/{session_id}/export/epub")
async def export_review_epub(session_id: str):
    try:
        session = await run_in_threadpool(review_store.get, session_id)
        output_path = review_store.epub_path(session_id)
        await run_in_threadpool(
            epub_compiler.compile,
            session.book,
            output_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = f"{Path(session.source_filename).stem}.epub"
    return FileResponse(
        path=output_path,
        filename=filename,
        media_type="application/epub+zip",
    )
