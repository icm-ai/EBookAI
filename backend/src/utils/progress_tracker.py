import json
import time
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ProgressInfo:
    """Progress information for conversion tasks"""

    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress_percent: int
    current_step: str
    total_steps: int
    current_step_index: int
    start_time: float
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    file_name: str = ""
    source_format: str = ""
    target_format: str = ""


class ProgressTracker:
    """In-memory progress tracker for conversion tasks"""

    def __init__(self):
        self._progress_data: Dict[str, ProgressInfo] = {}

    def start_task(
        self,
        task_id: str,
        file_name: str,
        source_format: str,
        target_format: str,
        total_steps: int = 5,
    ) -> None:
        """Initialize a new conversion task"""
        progress = ProgressInfo(
            task_id=task_id,
            status="pending",
            progress_percent=0,
            current_step="Initializing conversion...",
            total_steps=total_steps,
            current_step_index=0,
            start_time=time.time(),
            file_name=file_name,
            source_format=source_format,
            target_format=target_format,
        )
        self._progress_data[task_id] = progress

    def update_progress(
        self,
        task_id: str,
        step_index: int,
        step_name: str,
        progress_percent: int = None,
    ) -> None:
        """Update progress for a specific task"""
        if task_id not in self._progress_data:
            return

        progress = self._progress_data[task_id]
        progress.current_step_index = step_index
        progress.current_step = step_name
        progress.status = "processing"

        if progress_percent is not None:
            progress.progress_percent = max(0, min(100, progress_percent))
        else:
            # Auto-calculate progress based on step index
            progress.progress_percent = min(
                95, int((step_index / progress.total_steps) * 100)
            )

    def complete_task(self, task_id: str, output_file: str = "") -> None:
        """Mark task as completed"""
        if task_id not in self._progress_data:
            return

        progress = self._progress_data[task_id]
        progress.status = "completed"
        progress.progress_percent = 100
        progress.current_step = f"Conversion completed! Output: {output_file}"
        progress.end_time = time.time()

    def fail_task(self, task_id: str, error_message: str) -> None:
        """Mark task as failed"""
        if task_id not in self._progress_data:
            return

        progress = self._progress_data[task_id]
        progress.status = "failed"
        progress.current_step = "Conversion failed"
        progress.error_message = error_message
        progress.end_time = time.time()

    def get_progress(self, task_id: str) -> Optional[Dict]:
        """Get progress information for a task"""
        if task_id not in self._progress_data:
            return None

        progress = self._progress_data[task_id]
        result = asdict(progress)

        # Add calculated fields
        if progress.start_time and not progress.end_time:
            result["elapsed_time"] = time.time() - progress.start_time
        elif progress.start_time and progress.end_time:
            result["elapsed_time"] = progress.end_time - progress.start_time
        else:
            result["elapsed_time"] = 0

        # Estimate remaining time (very basic)
        if progress.progress_percent > 0 and progress.status == "processing":
            elapsed = result["elapsed_time"]
            estimated_total = elapsed * (100 / progress.progress_percent)
            result["estimated_remaining"] = max(0, estimated_total - elapsed)
        else:
            result["estimated_remaining"] = 0

        return result

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> None:
        """Remove old completed tasks"""
        current_time = time.time()
        to_remove = []

        for task_id, progress in self._progress_data.items():
            if progress.status in ["completed", "failed"] and progress.end_time:
                age_hours = (current_time - progress.end_time) / 3600
                if age_hours > max_age_hours:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._progress_data[task_id]

    def get_all_active_tasks(self) -> Dict[str, Dict]:
        """Get all active (non-completed) tasks"""
        active_tasks = {}
        for task_id, progress in self._progress_data.items():
            if progress.status in ["pending", "processing"]:
                active_tasks[task_id] = self.get_progress(task_id)
        return active_tasks


# Global progress tracker instance
progress_tracker = ProgressTracker()
