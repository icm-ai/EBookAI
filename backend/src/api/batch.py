import os
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from services.batch_conversion_service import batch_conversion_service
from utils.logging_config import get_logger
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS

router = APIRouter(prefix="/batch", tags=["batch-conversion"])
logger = get_logger("batch_api")


class BatchConversionRequest(BaseModel):
    """Request model for batch conversion"""

    target_format: str
    file_paths: List[str]


@router.post("/convert")
async def create_batch_conversion(
    target_format: str = Form(...), files: List[UploadFile] = File(...)
) -> dict:
    """Create and start a batch conversion job"""
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 50:
            raise HTTPException(
                status_code=400,
                detail="Too many files. Maximum 50 files allowed per batch.",
            )

        # Validate target format
        if f".{target_format.lower()}" not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported target format: {target_format}"
            )

        uploaded_files = []

        # Save uploaded files and validate
        for file in files:
            if not file.filename:
                continue

            # Check file extension
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file_ext} (file: {file.filename})",
                )

            # Check file size (50MB limit)
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {file.filename} (max 50MB)",
                )

            # Save file
            file_path = UPLOAD_DIR / file.filename
            with open(file_path, "wb") as f:
                f.write(content)

            uploaded_files.append(
                {
                    "file_path": str(file_path),
                    "filename": file.filename,
                    "size": len(content),
                }
            )

        # Create batch job
        batch_result = await batch_conversion_service.create_batch_job(
            uploaded_files, target_format
        )

        # Start the batch conversion
        start_result = await batch_conversion_service.start_batch_conversion(
            batch_result["batch_id"]
        )

        return {
            "batch_id": batch_result["batch_id"],
            "total_files": batch_result["total_files"],
            "status": start_result["status"],
            "message": f"Batch conversion started with {batch_result['total_files']} files",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create batch conversion: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to create batch conversion job"
        )


@router.get("/status/{batch_id}")
async def get_batch_status(batch_id: str) -> dict:
    """Get the status of a batch conversion job"""
    try:
        status = batch_conversion_service.get_batch_status(batch_id)

        if status is None:
            raise HTTPException(
                status_code=404, detail=f"Batch job {batch_id} not found"
            )

        return {"batch_id": batch_id, "status": status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status for {batch_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve batch status")


@router.get("/list")
async def list_batch_jobs() -> dict:
    """List all batch conversion jobs"""
    try:
        batches = batch_conversion_service.get_all_batches()

        return {"batches": batches, "count": len(batches)}

    except Exception as e:
        logger.error(f"Failed to list batch jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve batch jobs")


@router.post("/cleanup")
async def cleanup_completed_batches() -> dict:
    """Clean up old completed batch jobs"""
    try:
        batch_conversion_service.cleanup_completed_batches(max_age_hours=2)

        return {"message": "Cleanup completed successfully"}

    except Exception as e:
        logger.error(f"Failed to cleanup batch jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup batch jobs")
