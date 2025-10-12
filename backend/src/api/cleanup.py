"""
File cleanup API endpoints.
Provides manual cleanup and disk usage monitoring.
"""

from fastapi import APIRouter, HTTPException
from utils.file_cleanup import get_cleanup_manager
from utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["cleanup"])


@router.post("/cleanup/run")
async def run_cleanup():
    """
    Manually trigger file cleanup.

    Removes files older than the configured threshold from uploads and outputs directories.
    """
    try:
        cleanup_manager = get_cleanup_manager()
        stats = await cleanup_manager.cleanup_old_files()

        logger.info(f"Manual cleanup completed: {stats}")

        return {
            "status": "success",
            "message": "Cleanup completed",
            "statistics": {
                "files_removed": {
                    "uploads": stats["upload_files_removed"],
                    "outputs": stats["output_files_removed"],
                    "total": stats["upload_files_removed"]
                    + stats["output_files_removed"],
                },
                "space_freed_mb": {
                    "uploads": round(stats["upload_space_freed_mb"], 2),
                    "outputs": round(stats["output_space_freed_mb"], 2),
                    "total": round(
                        stats["upload_space_freed_mb"]
                        + stats["output_space_freed_mb"],
                        2,
                    ),
                },
                "errors": stats["errors"],
            },
        }

    except Exception as e:
        logger.error(f"Error during manual cleanup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/cleanup/status")
async def get_cleanup_status():
    """
    Get disk usage statistics for temporary directories.

    Returns information about current disk usage in uploads and outputs directories.
    """
    try:
        cleanup_manager = get_cleanup_manager()
        disk_usage = cleanup_manager.get_disk_usage()

        return {
            "status": "success",
            "disk_usage": {
                "uploads": {
                    "size_mb": round(disk_usage["upload_dir"]["size_mb"], 2),
                    "file_count": disk_usage["upload_dir"]["file_count"],
                },
                "outputs": {
                    "size_mb": round(disk_usage["output_dir"]["size_mb"], 2),
                    "file_count": disk_usage["output_dir"]["file_count"],
                },
                "total": {
                    "size_mb": round(disk_usage["total"]["size_mb"], 2),
                    "file_count": disk_usage["total"]["file_count"],
                },
            },
            "config": {
                "max_age_hours": int(cleanup_manager.max_age_seconds / 3600),
                "cleanup_interval_minutes": int(
                    cleanup_manager.cleanup_interval_seconds / 60
                ),
            },
        }

    except Exception as e:
        logger.error(f"Error getting cleanup status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get status: {str(e)}"
        )
