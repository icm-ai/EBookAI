"""Human review API for source-grounded BookIR inspection and repair."""

from __future__ import annotations

import uuid
from pathlib import Path

from book.compiler import EpubCompiler
from book.review import ReviewSessionStore
from config import MAX_FILE_SIZE, OUTPUT_DIR
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/review", tags=["review"])

REVIEW_DIR = OUTPUT_DIR / "review"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
review_store = ReviewSessionStore(REVIEW_DIR)
epub_compiler = EpubCompiler()


class RejectIssueRequest(BaseModel):
    reason: str = ""


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
