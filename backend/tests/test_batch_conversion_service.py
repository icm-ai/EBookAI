import asyncio
from unittest.mock import AsyncMock

import pytest

from services.batch_conversion_service import (
    BatchConversionService,
    BatchJob,
    BatchTask,
)
from utils.exceptions import ValidationError


@pytest.fixture
def batch_service():
    return BatchConversionService()


@pytest.fixture
def sample_files():
    return [
        {"filename": "book1.epub", "file_path": "/tmp/book1.epub"},
        {"filename": "book2.epub", "file_path": "/tmp/book2.epub"},
        {"filename": "book3.epub", "file_path": "/tmp/book3.epub"},
    ]


class TestBatchServiceInitialization:
    def test_initialization(self, batch_service):
        assert batch_service.active_batches == {}
        assert batch_service.max_concurrent_conversions == 3
        assert batch_service.conversion_service is not None
        assert hasattr(batch_service, "logger")


class TestCreateBatchJob:
    @pytest.mark.asyncio
    async def test_create_batch_job_success(self, batch_service, sample_files):
        result = await batch_service.create_batch_job(sample_files, "pdf")
        assert result["total_files"] == 3
        assert result["status"] == "created"

        status = batch_service.get_batch_status(result["batch_id"])
        assert status["status"] == "pending"
        assert len(status["tasks"]) == 3
        assert all(task["target_format"] == "pdf" for task in status["tasks"])

    @pytest.mark.asyncio
    async def test_create_batch_job_empty_files(self, batch_service):
        with pytest.raises(ValidationError, match="No files provided"):
            await batch_service.create_batch_job([], "pdf")

    @pytest.mark.asyncio
    async def test_create_batch_job_unique_ids(self, batch_service, sample_files):
        result1 = await batch_service.create_batch_job(sample_files, "pdf")
        result2 = await batch_service.create_batch_job(sample_files, "txt")
        assert result1["batch_id"] != result2["batch_id"]

        ids = []
        for batch_id in (result1["batch_id"], result2["batch_id"]):
            ids.extend(
                task["task_id"]
                for task in batch_service.get_batch_status(batch_id)["tasks"]
            )
        assert len(ids) == len(set(ids))


class TestBatchProcessing:
    @pytest.mark.asyncio
    async def test_process_batch_success(self, batch_service, sample_files):
        result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = result["batch_id"]
        batch_service.active_batches[batch_id].status = "processing"
        batch_service.conversion_service.convert_file = AsyncMock(
            return_value={"output_file": "/output/book.pdf"}
        )

        await batch_service._process_batch_tasks(batch_id)

        status = batch_service.get_batch_status(batch_id)
        assert status["status"] == "completed"
        assert status["completed_files"] == 3
        assert status["failed_files"] == 0
        assert status["progress_percent"] == 100

    @pytest.mark.asyncio
    async def test_process_batch_partial_failure(self, batch_service, sample_files):
        result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = result["batch_id"]
        batch_service.active_batches[batch_id].status = "processing"

        calls = 0

        async def convert(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("conversion failed")
            return {"output_file": f"/output/book{calls}.pdf"}

        batch_service.conversion_service.convert_file = AsyncMock(side_effect=convert)
        await batch_service._process_batch_tasks(batch_id)

        status = batch_service.get_batch_status(batch_id)
        assert status["status"] == "completed_with_errors"
        assert status["completed_files"] == 2
        assert status["failed_files"] == 1

    @pytest.mark.asyncio
    async def test_process_batch_respects_concurrency_limit(self, batch_service):
        files = [
            {"filename": f"book{i}.epub", "file_path": f"/tmp/book{i}.epub"}
            for i in range(10)
        ]
        result = await batch_service.create_batch_job(files, "pdf")
        batch_id = result["batch_id"]
        batch_service.active_batches[batch_id].status = "processing"

        concurrent = 0
        peak = 0

        async def convert(*args, **kwargs):
            nonlocal concurrent, peak
            concurrent += 1
            peak = max(peak, concurrent)
            await asyncio.sleep(0.01)
            concurrent -= 1
            return {"output_file": "/output/book.pdf"}

        batch_service.conversion_service.convert_file = AsyncMock(side_effect=convert)
        await batch_service._process_batch_tasks(batch_id)
        assert peak <= batch_service.max_concurrent_conversions


class TestBatchStatusAndCleanup:
    @pytest.mark.asyncio
    async def test_get_batch_status_success(self, batch_service, sample_files):
        result = await batch_service.create_batch_job(sample_files, "pdf")
        status = batch_service.get_batch_status(result["batch_id"])
        assert status["batch_id"] == result["batch_id"]
        assert status["total_files"] == 3
        assert status["completed_files"] == 0
        assert status["failed_files"] == 0
        assert status["progress_percent"] == 0
        assert len(status["tasks"]) == 3

    def test_get_batch_status_nonexistent(self, batch_service):
        assert batch_service.get_batch_status("missing") is None

    @pytest.mark.asyncio
    async def test_get_all_batches(self, batch_service, sample_files):
        first = await batch_service.create_batch_job(sample_files[:1], "pdf")
        second = await batch_service.create_batch_job(sample_files[1:], "txt")
        batches = batch_service.get_all_batches()
        assert set(batches) == {first["batch_id"], second["batch_id"]}

    @pytest.mark.asyncio
    async def test_cleanup_completed_batches(self, batch_service, sample_files):
        result = await batch_service.create_batch_job(sample_files[:1], "pdf")
        batch = batch_service.active_batches[result["batch_id"]]
        batch.status = "completed"
        batch.completed_at = asyncio.get_running_loop().time() - 3 * 3600

        batch_service.cleanup_completed_batches(max_age_hours=2)
        assert result["batch_id"] not in batch_service.active_batches


class TestBatchDataClasses:
    def test_batch_task_creation(self):
        task = BatchTask(
            file_path="/tmp/book.epub", target_format="pdf", task_id="task-123"
        )
        assert task.status == "pending"
        assert task.output_file == ""
        assert task.error_message == ""

    def test_batch_job_creation(self):
        tasks = [
            BatchTask(file_path="/tmp/book.epub", target_format="pdf", task_id="task-1")
        ]
        job = BatchJob(batch_id="batch-1", tasks=tasks, total_files=1)
        assert job.status == "pending"
        assert job.completed_files == 0
        assert job.failed_files == 0
