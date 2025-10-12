from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from utils.progress_tracker import progress_tracker
from utils.logging_config import get_logger

router = APIRouter(prefix="/progress", tags=["progress"])
logger = get_logger("progress_api")


@router.get("/task/{task_id}")
async def get_task_progress(task_id: str) -> Dict:
    """Get progress information for a specific task"""
    try:
        progress_data = progress_tracker.get_progress(task_id)

        if progress_data is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return {"task_id": task_id, "progress": progress_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progress for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve task progress")


@router.get("/active")
async def get_active_tasks() -> Dict:
    """Get all active (non-completed) tasks"""
    try:
        active_tasks = progress_tracker.get_all_active_tasks()

        return {"active_tasks": active_tasks, "count": len(active_tasks)}

    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active tasks")


@router.delete("/task/{task_id}")
async def cancel_task(task_id: str) -> Dict:
    """Cancel/remove a task (simplified implementation for MVP)"""
    try:
        progress_data = progress_tracker.get_progress(task_id)

        if progress_data is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # For now, we just mark it as failed
        # In a full implementation, this would actually stop the conversion process
        progress_tracker.fail_task(task_id, "Task cancelled by user")

        return {"task_id": task_id, "status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel task")
