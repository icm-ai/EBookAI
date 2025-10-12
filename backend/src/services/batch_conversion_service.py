import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict

from utils.logging_config import get_logger
from utils.progress_tracker import progress_tracker
from utils.exceptions import ValidationError, BatchConversionError
from services.conversion_service import ConversionService


@dataclass
class BatchTask:
    """Single task in a batch conversion job"""

    file_path: str
    target_format: str
    task_id: str
    status: str = "pending"  # pending, processing, completed, failed
    output_file: str = ""
    error_message: str = ""


@dataclass
class BatchJob:
    """Batch conversion job containing multiple tasks"""

    batch_id: str
    tasks: List[BatchTask]
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    status: str = "pending"  # pending, processing, completed, failed
    created_at: float = 0
    completed_at: float = 0


class BatchConversionService:
    """Service for handling batch file conversions"""

    def __init__(self):
        self.logger = get_logger("batch_conversion")
        self.conversion_service = ConversionService()
        self.active_batches: Dict[str, BatchJob] = {}
        self.max_concurrent_conversions = 3  # Limit concurrent conversions

    async def create_batch_job(
        self, files: List[Dict[str, Any]], target_format: str
    ) -> Dict[str, Any]:
        """Create a new batch conversion job"""
        try:
            if not files or len(files) == 0:
                raise ValidationError(
                    message="No files provided for batch conversion",
                    field="files",
                    value=files,
                )

            if len(files) > 50:  # Limit batch size
                raise ValidationError(
                    message="Batch size too large. Maximum 50 files allowed.",
                    field="files",
                    value=len(files),
                )

            batch_id = str(uuid.uuid4())
            tasks = []

            # Create individual tasks for each file
            for file_info in files:
                task_id = str(uuid.uuid4())
                task = BatchTask(
                    file_path=file_info["file_path"],
                    target_format=target_format,
                    task_id=task_id,
                )
                tasks.append(task)

            # Create batch job
            batch_job = BatchJob(
                batch_id=batch_id,
                tasks=tasks,
                total_files=len(tasks),
                created_at=asyncio.get_event_loop().time(),
            )

            self.active_batches[batch_id] = batch_job

            self.logger.info(
                f"Created batch job {batch_id} with {len(tasks)} files",
                extra={"batch_id": batch_id, "total_files": len(tasks)},
            )

            return {
                "batch_id": batch_id,
                "total_files": len(tasks),
                "status": "created",
                "message": f"Batch job created with {len(tasks)} files",
            }

        except Exception as e:
            self.logger.error(f"Failed to create batch job: {e}")
            if isinstance(e, ValidationError):
                raise
            raise BatchConversionError(
                message="Failed to create batch conversion job", original_error=e
            )

    async def start_batch_conversion(self, batch_id: str) -> Dict[str, Any]:
        """Start processing a batch conversion job"""
        try:
            if batch_id not in self.active_batches:
                raise ValidationError(
                    message=f"Batch job {batch_id} not found",
                    field="batch_id",
                    value=batch_id,
                )

            batch_job = self.active_batches[batch_id]
            if batch_job.status != "pending":
                raise ValidationError(
                    message=f"Batch job {batch_id} is not in pending status",
                    field="status",
                    value=batch_job.status,
                )

            batch_job.status = "processing"

            # Start batch progress tracking
            progress_tracker.start_task(
                task_id=batch_id,
                file_name=f"Batch conversion ({batch_job.total_files} files)",
                source_format="batch",
                target_format=batch_job.tasks[0].target_format,
                total_steps=batch_job.total_files,
            )

            # Start processing tasks asynchronously
            asyncio.create_task(self._process_batch_tasks(batch_id))

            self.logger.info(f"Started batch conversion {batch_id}")

            return {
                "batch_id": batch_id,
                "status": "processing",
                "message": "Batch conversion started",
            }

        except Exception as e:
            self.logger.error(f"Failed to start batch conversion {batch_id}: {e}")
            if isinstance(e, ValidationError):
                raise
            raise BatchConversionError(
                message="Failed to start batch conversion", original_error=e
            )

    async def _process_batch_tasks(self, batch_id: str):
        """Process all tasks in a batch job with concurrency control"""
        try:
            batch_job = self.active_batches[batch_id]
            semaphore = asyncio.Semaphore(self.max_concurrent_conversions)

            async def process_single_task(task: BatchTask):
                async with semaphore:
                    return await self._process_single_task(batch_id, task)

            # Process all tasks concurrently (with limit)
            results = await asyncio.gather(
                *[process_single_task(task) for task in batch_job.tasks],
                return_exceptions=True,
            )

            # Update batch status
            batch_job.completed_at = asyncio.get_event_loop().time()
            if batch_job.failed_files == 0:
                batch_job.status = "completed"
                progress_tracker.complete_task(
                    batch_id,
                    f"All {batch_job.total_files} files converted successfully",
                )
            else:
                batch_job.status = "completed_with_errors"
                progress_tracker.complete_task(
                    batch_id,
                    f"{batch_job.completed_files}/{batch_job.total_files} files converted ({batch_job.failed_files} failed)",
                )

            self.logger.info(
                f"Batch conversion {batch_id} finished: {batch_job.completed_files} completed, {batch_job.failed_files} failed"
            )

        except Exception as e:
            batch_job = self.active_batches.get(batch_id)
            if batch_job:
                batch_job.status = "failed"
                progress_tracker.fail_task(
                    batch_id, f"Batch processing failed: {str(e)}"
                )

            self.logger.error(f"Batch processing failed for {batch_id}: {e}")

    async def _process_single_task(
        self, batch_id: str, task: BatchTask
    ) -> Dict[str, Any]:
        """Process a single task within a batch"""
        try:
            batch_job = self.active_batches[batch_id]
            task.status = "processing"

            self.logger.info(f"Processing task {task.task_id} in batch {batch_id}")

            # Perform the actual conversion
            result = await self.conversion_service.convert_file(
                task.file_path, task.target_format, task.task_id
            )

            # Update task status
            task.status = "completed"
            task.output_file = result["output_file"]
            batch_job.completed_files += 1

            # Update batch progress
            progress_percent = int(
                (batch_job.completed_files + batch_job.failed_files)
                / batch_job.total_files
                * 100
            )
            progress_tracker.update_progress(
                batch_id,
                batch_job.completed_files + batch_job.failed_files,
                f"Processed {batch_job.completed_files + batch_job.failed_files}/{batch_job.total_files} files",
                progress_percent,
            )

            return result

        except Exception as e:
            # Update task status on failure
            task.status = "failed"
            task.error_message = str(e)
            batch_job.failed_files += 1

            # Update batch progress
            progress_percent = int(
                (batch_job.completed_files + batch_job.failed_files)
                / batch_job.total_files
                * 100
            )
            progress_tracker.update_progress(
                batch_id,
                batch_job.completed_files + batch_job.failed_files,
                f"Processed {batch_job.completed_files + batch_job.failed_files}/{batch_job.total_files} files ({batch_job.failed_files} failed)",
                progress_percent,
            )

            self.logger.error(f"Task {task.task_id} failed in batch {batch_id}: {e}")
            return {"error": str(e)}

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get the status of a batch conversion job"""
        if batch_id not in self.active_batches:
            return None

        batch_job = self.active_batches[batch_id]
        result = asdict(batch_job)

        # Add progress information
        if batch_job.total_files > 0:
            result["progress_percent"] = int(
                (batch_job.completed_files + batch_job.failed_files)
                / batch_job.total_files
                * 100
            )
        else:
            result["progress_percent"] = 0

        return result

    def get_all_batches(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all batch jobs"""
        return {
            batch_id: self.get_batch_status(batch_id)
            for batch_id in self.active_batches.keys()
        }

    def cleanup_completed_batches(self, max_age_hours: int = 24):
        """Remove old completed batch jobs"""
        current_time = asyncio.get_event_loop().time()
        to_remove = []

        for batch_id, batch_job in self.active_batches.items():
            if (
                batch_job.status in ["completed", "completed_with_errors", "failed"]
                and batch_job.completed_at
            ):
                age_hours = (current_time - batch_job.completed_at) / 3600
                if age_hours > max_age_hours:
                    to_remove.append(batch_id)

        for batch_id in to_remove:
            del self.active_batches[batch_id]
            self.logger.info(f"Cleaned up old batch job {batch_id}")


# Global batch conversion service instance
batch_conversion_service = BatchConversionService()
