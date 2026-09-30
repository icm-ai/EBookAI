"""API for the source-pinned gold annotation review workbench."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from book.benchmark.consensus import GoldConsensusStore
from book.benchmark.gold import GoldValidationError
from book.benchmark.review_workbench import GoldReviewStore
from book.parsers.base import ParserBackendUnavailable
from config import OUTPUT_DIR

router = APIRouter(prefix="/gold-review", tags=["gold-review"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GOLD_MANIFEST = PROJECT_ROOT / "benchmark" / "corpus" / "manifest.json"
GOLD_REVIEW_PLAN = PROJECT_ROOT / "benchmark" / "corpus" / "review-plan.json"
GOLD_CACHE = OUTPUT_DIR / "gold-review-cache"
GOLD_WORKSPACE = OUTPUT_DIR / "gold-review-workspace"


@lru_cache(maxsize=1)
def _store() -> GoldReviewStore:
    return GoldReviewStore(
        GOLD_MANIFEST,
        GOLD_REVIEW_PLAN,
        GOLD_CACHE,
        GOLD_WORKSPACE,
    )


@lru_cache(maxsize=1)
def _consensus_store() -> GoldConsensusStore:
    return GoldConsensusStore(
        GOLD_MANIFEST,
        _store(),
        GOLD_WORKSPACE,
    )


class CreateGoldReviewSessionRequest(BaseModel):
    document_id: str
    page_index: int
    backend: str = "pymupdf"


class GoldTasksRequest(BaseModel):
    tasks: List[str]


class GoldElementRequest(BaseModel):
    id: str
    type: str
    text: str = ""
    bbox: List[float] | None = None
    level: int | None = None
    attrs: Dict[str, Any] = Field(default_factory=dict)


class GoldReadingOrderRequest(BaseModel):
    reading_order: List[str]


class GoldConfirmRequest(BaseModel):
    subject: str
    subject_id: str
    reviewer: str
    note: str = ""


class GoldPromoteRequest(BaseModel):
    reviewer: str
    note: str = ""


class CreateConsensusRequest(BaseModel):
    session_a_id: str
    session_b_id: str


class AdjudicateConsensusRequest(BaseModel):
    conflict_id: str
    choice: str
    adjudicator: str
    note: str = ""


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ParserBackendUnavailable):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, GoldValidationError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Gold review failed: {exc}")


@router.get("/queue")
async def get_gold_review_queue():
    try:
        return await run_in_threadpool(_store().queue)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions", status_code=201)
async def create_gold_review_session(request: CreateGoldReviewSessionRequest):
    try:
        session = await run_in_threadpool(
            _store().create,
            request.document_id,
            request.page_index,
            backend=request.backend,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}")
async def get_gold_review_session(session_id: str):
    try:
        session = await run_in_threadpool(_store().get, session_id)
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/page.png")
async def get_gold_review_page(
    session_id: str,
    scale: float = Query(default=1.5, ge=0.5, le=4.0),
):
    try:
        image = await run_in_threadpool(
            _store().render_page,
            session_id,
            scale=scale,
        )
        return Response(content=image, media_type="image/png")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/sessions/{session_id}/tasks")
async def set_gold_review_tasks(session_id: str, request: GoldTasksRequest):
    try:
        session = await run_in_threadpool(
            _store().set_tasks,
            session_id,
            request.tasks,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/sessions/{session_id}/elements/{element_id}")
async def upsert_gold_review_element(
    session_id: str,
    element_id: str,
    request: GoldElementRequest,
):
    if element_id != request.id:
        raise HTTPException(
            status_code=400,
            detail="element id in path and payload must match",
        )
    try:
        session = await run_in_threadpool(
            _store().upsert_element,
            session_id,
            request.dict(exclude_none=True),
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/sessions/{session_id}/elements/{element_id}")
async def delete_gold_review_element(session_id: str, element_id: str):
    try:
        session = await run_in_threadpool(
            _store().delete_element,
            session_id,
            element_id,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/sessions/{session_id}/reading-order")
async def set_gold_review_reading_order(
    session_id: str,
    request: GoldReadingOrderRequest,
):
    try:
        session = await run_in_threadpool(
            _store().set_reading_order,
            session_id,
            request.reading_order,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/confirm")
async def confirm_gold_review_item(
    session_id: str,
    request: GoldConfirmRequest,
):
    try:
        session = await run_in_threadpool(
            _store().confirm,
            session_id,
            subject=request.subject,
            subject_id=request.subject_id,
            reviewer=request.reviewer,
            note=request.note,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/promote")
async def promote_gold_review(
    session_id: str,
    request: GoldPromoteRequest,
):
    try:
        session = await run_in_threadpool(
            _store().promote,
            session_id,
            reviewer=request.reviewer,
            note=request.note,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/sessions/{session_id}/publish")
async def publish_gold_review(session_id: str):
    try:
        session = await run_in_threadpool(
            _store().publish,
            session_id,
        )
        return session.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/export/promoted")
async def export_promoted_gold(session_id: str):
    try:
        session = await run_in_threadpool(_store().get, session_id)
        path = await run_in_threadpool(
            _store().promoted_path,
            session_id,
        )
        return FileResponse(
            path=path,
            filename=f"{session.document_id}.gold.reviewed.json",
            media_type="application/json",
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/export/audit")
async def export_gold_review_audit(session_id: str):
    try:
        session = await run_in_threadpool(_store().get, session_id)
        path = await run_in_threadpool(
            _store().audit_path,
            session_id,
        )
        return FileResponse(
            path=path,
            filename=f"{session.document_id}.gold.review-audit.json",
            media_type="application/json",
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/consensus", status_code=201)
async def create_gold_consensus(request: CreateConsensusRequest):
    try:
        bundle = await run_in_threadpool(
            _consensus_store().create,
            request.session_a_id,
            request.session_b_id,
        )
        return bundle.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/consensus/{bundle_id}")
async def get_gold_consensus(bundle_id: str):
    try:
        bundle = await run_in_threadpool(_consensus_store().get, bundle_id)
        return bundle.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/consensus/{bundle_id}/adjudicate")
async def adjudicate_gold_consensus(
    bundle_id: str,
    request: AdjudicateConsensusRequest,
):
    try:
        bundle = await run_in_threadpool(
            _consensus_store().adjudicate,
            bundle_id,
            conflict_id=request.conflict_id,
            choice=request.choice,
            adjudicator=request.adjudicator,
            note=request.note,
        )
        return bundle.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/consensus/{bundle_id}/publish")
async def publish_gold_consensus(bundle_id: str):
    try:
        bundle = await run_in_threadpool(
            _consensus_store().publish,
            bundle_id,
        )
        return bundle.to_dict()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/consensus/{bundle_id}/export/gold")
async def export_gold_consensus(bundle_id: str):
    try:
        bundle = await run_in_threadpool(_consensus_store().get, bundle_id)
        path = await run_in_threadpool(
            _consensus_store().consensus_path,
            bundle_id,
        )
        return FileResponse(
            path=path,
            filename=f"{bundle.document_id}.gold.consensus.json",
            media_type="application/json",
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/consensus/{bundle_id}/export/audit")
async def export_gold_consensus_audit(bundle_id: str):
    try:
        bundle = await run_in_threadpool(_consensus_store().get, bundle_id)
        path = await run_in_threadpool(
            _consensus_store().audit_path,
            bundle_id,
        )
        return FileResponse(
            path=path,
            filename=f"{bundle.document_id}.gold.consensus-audit.json",
            media_type="application/json",
        )
    except Exception as exc:
        raise _http_error(exc) from exc
