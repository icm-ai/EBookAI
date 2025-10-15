import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from services.batch_conversion_service import (
    BatchConversionService,
    BatchTask,
    BatchJob
)
from utils.exceptions import ValidationError, BatchConversionError


@pytest.fixture
def batch_service():
    """Create BatchConversionService instance"""
    return BatchConversionService()


@pytest.fixture
def mock_conversion_service():
    """Mock ConversionService"""
    with patch("services.batch_conversion_service.ConversionService") as mock:
        yield mock


@pytest.fixture
def sample_files():
    """Sample file data for batch conversion"""
    return [
        {"filename": "book1.epub", "path": "/tmp/book1.epub"},
        {"filename": "book2.epub", "path": "/tmp/book2.epub"},
        {"filename": "book3.epub", "path": "/tmp/book3.epub"}
    ]


class TestBatchServiceInitialization:
    """Test BatchConversionService initialization"""

    def test_initialization(self, batch_service):
        """Test service initializes correctly"""
        assert batch_service.active_batches == {}
        assert batch_service.max_concurrent_conversions == 3
        assert batch_service.conversion_service is not None

    def test_has_logger(self, batch_service):
        """Test service has logger"""
        assert hasattr(batch_service, "logger")


class TestCreateBatchJob:
    """Test create_batch_job method"""

    @pytest.mark.asyncio
    async def test_create_batch_job_success(self, batch_service, sample_files):
        """Test successful batch job creation"""
        result = await batch_service.create_batch_job(sample_files, "pdf")

        assert "batch_id" in result
        assert result["total_files"] == 3
        assert result["status"] == "pending"
        assert len(result["tasks"]) == 3

        batch_id = result["batch_id"]
        assert batch_id in batch_service.active_batches

    @pytest.mark.asyncio
    async def test_create_batch_job_empty_files(self, batch_service):
        """Test batch job creation with empty file list"""
        with pytest.raises(ValidationError, match="No files provided"):
            await batch_service.create_batch_job([], "pdf")

    @pytest.mark.asyncio
    async def test_create_batch_job_invalid_format(self, batch_service, sample_files):
        """Test batch job creation with invalid target format"""
        with pytest.raises(ValidationError, match="Unsupported target format"):
            await batch_service.create_batch_job(sample_files, "invalid_format")

    @pytest.mark.asyncio
    async def test_create_batch_job_task_structure(self, batch_service, sample_files):
        """Test batch job tasks have correct structure"""
        result = await batch_service.create_batch_job(sample_files, "pdf")

        for task in result["tasks"]:
            assert "task_id" in task
            assert "file_path" in task
            assert "target_format" in task
            assert task["status"] == "pending"
            assert task["target_format"] == "pdf"

    @pytest.mark.asyncio
    async def test_create_batch_job_unique_ids(self, batch_service, sample_files):
        """Test batch and task IDs are unique"""
        result1 = await batch_service.create_batch_job(sample_files, "pdf")
        result2 = await batch_service.create_batch_job(sample_files, "mobi")

        assert result1["batch_id"] != result2["batch_id"]

        task_ids = [task["task_id"] for task in result1["tasks"]] + \
                   [task["task_id"] for task in result2["tasks"]]
        assert len(task_ids) == len(set(task_ids))


class TestProcessBatchJob:
    """Test process_batch_job method"""

    @pytest.mark.asyncio
    async def test_process_batch_job_success(self, batch_service, sample_files, mock_conversion_service):
        """Test successful batch job processing"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        mock_instance = Mock()
        mock_instance.convert_file = AsyncMock(return_value="/output/book.pdf")
        mock_conversion_service.return_value = mock_instance

        await batch_service.process_batch_job(batch_id)

        batch = batch_service.active_batches[batch_id]
        assert batch.status == "completed"
        assert batch.completed_files == 3
        assert batch.failed_files == 0

    @pytest.mark.asyncio
    async def test_process_batch_job_partial_failure(self, batch_service, sample_files, mock_conversion_service):
        """Test batch job processing with partial failures"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        mock_instance = Mock()
        call_count = 0

        async def convert_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Conversion failed for book2")
            return f"/output/book{call_count}.pdf"

        mock_instance.convert_file = AsyncMock(side_effect=convert_with_failure)
        mock_conversion_service.return_value = mock_instance

        await batch_service.process_batch_job(batch_id)

        batch = batch_service.active_batches[batch_id]
        assert batch.completed_files == 2
        assert batch.failed_files == 1
        assert batch.status == "completed"

    @pytest.mark.asyncio
    async def test_process_batch_job_all_failures(self, batch_service, sample_files, mock_conversion_service):
        """Test batch job processing when all tasks fail"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        mock_instance = Mock()
        mock_instance.convert_file = AsyncMock(side_effect=Exception("All conversions failed"))
        mock_conversion_service.return_value = mock_instance

        await batch_service.process_batch_job(batch_id)

        batch = batch_service.active_batches[batch_id]
        assert batch.failed_files == 3
        assert batch.completed_files == 0
        assert batch.status == "failed"

    @pytest.mark.asyncio
    async def test_process_batch_job_nonexistent_batch(self, batch_service):
        """Test processing nonexistent batch job"""
        with pytest.raises(BatchConversionError, match="not found"):
            await batch_service.process_batch_job("nonexistent_batch_id")

    @pytest.mark.asyncio
    async def test_process_batch_job_respects_concurrency_limit(self, batch_service, mock_conversion_service):
        """Test batch processing respects concurrency limit"""
        files = [{"filename": f"book{i}.epub", "path": f"/tmp/book{i}.epub"} for i in range(10)]
        batch_result = await batch_service.create_batch_job(files, "pdf")
        batch_id = batch_result["batch_id"]

        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrency(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            return "/output/book.pdf"

        mock_instance = Mock()
        mock_instance.convert_file = AsyncMock(side_effect=track_concurrency)
        mock_conversion_service.return_value = mock_instance

        await batch_service.process_batch_job(batch_id)

        assert max_concurrent <= batch_service.max_concurrent_conversions


class TestGetBatchStatus:
    """Test get_batch_status method"""

    @pytest.mark.asyncio
    async def test_get_batch_status_success(self, batch_service, sample_files):
        """Test getting batch status"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        status = batch_service.get_batch_status(batch_id)

        assert status["batch_id"] == batch_id
        assert status["total_files"] == 3
        assert status["completed_files"] == 0
        assert status["failed_files"] == 0
        assert status["status"] == "pending"
        assert "tasks" in status

    @pytest.mark.asyncio
    async def test_get_batch_status_nonexistent(self, batch_service):
        """Test getting status of nonexistent batch"""
        with pytest.raises(BatchConversionError, match="not found"):
            batch_service.get_batch_status("nonexistent_id")

    @pytest.mark.asyncio
    async def test_get_batch_status_includes_task_details(self, batch_service, sample_files):
        """Test batch status includes task details"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        status = batch_service.get_batch_status(batch_id)

        assert len(status["tasks"]) == 3
        for task in status["tasks"]:
            assert "task_id" in task
            assert "status" in task
            assert "file_path" in task


class TestListBatches:
    """Test list_batches method"""

    @pytest.mark.asyncio
    async def test_list_batches_empty(self, batch_service):
        """Test listing batches when none exist"""
        batches = batch_service.list_batches()

        assert batches == []

    @pytest.mark.asyncio
    async def test_list_batches_multiple(self, batch_service, sample_files):
        """Test listing multiple batches"""
        await batch_service.create_batch_job(sample_files[:2], "pdf")
        await batch_service.create_batch_job(sample_files[1:], "mobi")

        batches = batch_service.list_batches()

        assert len(batches) == 2
        assert all("batch_id" in batch for batch in batches)
        assert all("total_files" in batch for batch in batches)
        assert all("status" in batch for batch in batches)

    @pytest.mark.asyncio
    async def test_list_batches_summary_format(self, batch_service, sample_files):
        """Test list batches returns summary format"""
        await batch_service.create_batch_job(sample_files, "pdf")

        batches = batch_service.list_batches()

        for batch in batches:
            assert "tasks" not in batch or isinstance(batch.get("tasks"), list)


class TestCleanupCompletedBatches:
    """Test cleanup_completed_batches method"""

    @pytest.mark.asyncio
    async def test_cleanup_completed_batches(self, batch_service, sample_files, mock_conversion_service):
        """Test cleanup of completed batches"""
        batch1 = await batch_service.create_batch_job(sample_files[:2], "pdf")
        batch2 = await batch_service.create_batch_job(sample_files[1:], "pdf")

        batch_id1 = batch1["batch_id"]
        batch_id2 = batch2["batch_id"]

        mock_instance = Mock()
        mock_instance.convert_file = AsyncMock(return_value="/output/book.pdf")
        mock_conversion_service.return_value = mock_instance

        await batch_service.process_batch_job(batch_id1)

        assert len(batch_service.active_batches) == 2

        count = batch_service.cleanup_completed_batches()

        assert count == 1
        assert batch_id1 not in batch_service.active_batches
        assert batch_id2 in batch_service.active_batches

    @pytest.mark.asyncio
    async def test_cleanup_no_completed_batches(self, batch_service, sample_files):
        """Test cleanup when no batches are completed"""
        await batch_service.create_batch_job(sample_files, "pdf")

        count = batch_service.cleanup_completed_batches()

        assert count == 0
        assert len(batch_service.active_batches) == 1

    @pytest.mark.asyncio
    async def test_cleanup_all_batches_option(self, batch_service, sample_files):
        """Test cleanup all batches regardless of status"""
        await batch_service.create_batch_job(sample_files[:2], "pdf")
        await batch_service.create_batch_job(sample_files[1:], "pdf")

        assert len(batch_service.active_batches) == 2

        count = batch_service.cleanup_completed_batches(all_batches=True)

        assert count == 2
        assert len(batch_service.active_batches) == 0


class TestBatchDataClasses:
    """Test BatchTask and BatchJob data classes"""

    def test_batch_task_creation(self):
        """Test BatchTask creation"""
        task = BatchTask(
            file_path="/tmp/book.epub",
            target_format="pdf",
            task_id="task-123"
        )

        assert task.file_path == "/tmp/book.epub"
        assert task.target_format == "pdf"
        assert task.task_id == "task-123"
        assert task.status == "pending"
        assert task.output_file == ""
        assert task.error_message == ""

    def test_batch_job_creation(self):
        """Test BatchJob creation"""
        tasks = [
            BatchTask(file_path="/tmp/book1.epub", target_format="pdf", task_id="task-1"),
            BatchTask(file_path="/tmp/book2.epub", target_format="pdf", task_id="task-2")
        ]

        job = BatchJob(
            batch_id="batch-456",
            tasks=tasks,
            total_files=2
        )

        assert job.batch_id == "batch-456"
        assert len(job.tasks) == 2
        assert job.total_files == 2
        assert job.completed_files == 0
        assert job.failed_files == 0
        assert job.status == "pending"


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_concurrent_batch_creations(self, batch_service, sample_files):
        """Test creating multiple batches concurrently"""
        tasks = [
            batch_service.create_batch_job(sample_files, "pdf"),
            batch_service.create_batch_job(sample_files, "mobi"),
            batch_service.create_batch_job(sample_files, "txt")
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert len(set(r["batch_id"] for r in results)) == 3

    @pytest.mark.asyncio
    async def test_process_batch_updates_progress(self, batch_service, sample_files, mock_conversion_service):
        """Test batch processing updates progress correctly"""
        batch_result = await batch_service.create_batch_job(sample_files, "pdf")
        batch_id = batch_result["batch_id"]

        mock_instance = Mock()
        mock_instance.convert_file = AsyncMock(return_value="/output/book.pdf")
        mock_conversion_service.return_value = mock_instance

        initial_status = batch_service.get_batch_status(batch_id)
        assert initial_status["status"] == "pending"

        await batch_service.process_batch_job(batch_id)

        final_status = batch_service.get_batch_status(batch_id)
        assert final_status["status"] == "completed"
        assert final_status["completed_files"] > 0
