import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from services.conversion_service import ConversionService

from config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, OUTPUT_DIR, UPLOAD_DIR

router = APIRouter()
conversion_service = ConversionService()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "conversion",
        "allowed_formats": list(ALLOWED_EXTENSIONS),
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
    }


@router.get("/files")
async def list_files(file_type: str = Query("output", regex="^(input|output)$")):
    """List uploaded or converted files"""
    target_dir = UPLOAD_DIR if file_type == "input" else OUTPUT_DIR

    files = []
    for file_path in target_dir.glob("*"):
        if file_path.is_file():
            stat = file_path.stat()
            files.append(
                {
                    "filename": file_path.name,
                    "size_bytes": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    return {
        "file_type": file_type,
        "directory": str(target_dir),
        "files": sorted(files, key=lambda x: x["modified"], reverse=True),
        "total_files": len(files),
    }


@router.post("/convert")
async def convert_file(file: UploadFile = File(...), target_format: str = "pdf"):
    """Convert uploaded file to target format"""

    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Security: Sanitize filename
    safe_filename = Path(file.filename).name
    if not safe_filename or safe_filename.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Validate file extension
    file_ext = Path(safe_filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        formats = ", ".join(ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed formats: {formats}",
        )

    # Validate target format
    if f".{target_format.lower()}" not in ALLOWED_EXTENSIONS:
        formats = ", ".join(ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target format. Allowed formats: {formats}",
        )

    # Validate file size
    file_size = 0
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Save uploaded file with safe path
    input_path = UPLOAD_DIR / f"{task_id}_{safe_filename}"

    try:
        with open(input_path, "wb") as buffer:
            buffer.write(content)

        # Perform conversion
        result = await conversion_service.convert_file(
            file_path=str(input_path), target_format=target_format, task_id=task_id
        )

        return result

    except FileNotFoundError as e:
        # Clean up uploaded file
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=404, detail=str(e))

    except ValueError as e:
        # Clean up uploaded file
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Clean up uploaded file
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download converted file"""
    # Security: Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    if (
        not safe_filename
        or safe_filename.startswith(".")
        or "/" in filename
        or "\\" in filename
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = OUTPUT_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Security: Ensure file is within OUTPUT_DIR
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine appropriate media type based on file extension
    file_ext = Path(safe_filename).suffix.lower()
    media_type = "application/octet-stream"
    if file_ext == ".pdf":
        media_type = "application/pdf"
    elif file_ext == ".epub":
        media_type = "application/epub+zip"

    return FileResponse(path=file_path, filename=safe_filename, media_type=media_type)


@router.get("/status/{task_id}")
async def get_conversion_status(task_id: str):
    """Get conversion status"""
    # Validate task_id format
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Check if any output files exist for this task
    output_files = list(OUTPUT_DIR.glob(f"*{task_id}*"))

    if output_files:
        return {
            "task_id": task_id,
            "status": "completed",
            "output_files": [f.name for f in output_files],
            "message": "Conversion completed successfully",
        }
    else:
        # Check if input file still exists (processing or failed)
        input_files = list(UPLOAD_DIR.glob(f"{task_id}_*"))
        if input_files:
            return {
                "task_id": task_id,
                "status": "failed",
                "message": "Conversion failed or file not found",
            }
        else:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "Task not found",
            }


@router.delete("/cleanup/{task_id}")
async def cleanup_task_files(task_id: str):
    """Clean up files associated with a task"""
    # Validate task_id format
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    cleaned_files = []

    # Clean up input files
    input_files = list(UPLOAD_DIR.glob(f"{task_id}_*"))
    for file_path in input_files:
        try:
            file_path.unlink()
            cleaned_files.append(f"input/{file_path.name}")
        except Exception:
            pass

    # Clean up output files
    output_files = list(OUTPUT_DIR.glob(f"*{task_id}*"))
    for file_path in output_files:
        try:
            file_path.unlink()
            cleaned_files.append(f"output/{file_path.name}")
        except Exception:
            pass

    return {
        "task_id": task_id,
        "cleaned_files": cleaned_files,
        "message": f"Cleaned up {len(cleaned_files)} files",
    }
