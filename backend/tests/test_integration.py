import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app

    return TestClient(app)


@pytest.fixture
def temp_test_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test file for conversion.")
    return test_file


def conversion_result(task_id="test-task"):
    return {
        "task_id": task_id,
        "status": "completed",
        "output_file": "test.pdf",
        "message": "Conversion completed successfully",
    }


class TestCompleteConversionWorkflow:
    @pytest.mark.integration
    @patch("api.conversion.conversion_service.convert_file", new_callable=AsyncMock)
    def test_single_file_conversion_workflow(
        self, mock_convert, client, temp_test_file
    ):
        mock_convert.return_value = conversion_result()
        with temp_test_file.open("rb") as handle:
            response = client.post(
                "/api/convert",
                files={"file": ("test.txt", handle, "text/plain")},
                data={"target_format": "pdf"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["output_file"] == "test.pdf"

    @pytest.mark.integration
    @patch("api.conversion.conversion_service.convert_file", new_callable=AsyncMock)
    def test_health_to_conversion_workflow(self, mock_convert, client, temp_test_file):
        assert client.get("/api/health").json()["status"] == "healthy"
        assert client.get("/api/health/detailed").status_code == 200

        mock_convert.return_value = conversion_result()
        with temp_test_file.open("rb") as handle:
            response = client.post(
                "/api/convert",
                files={"file": ("test.txt", handle, "text/plain")},
                data={"target_format": "pdf"},
            )
        assert response.status_code == 200


class TestBatchConversionWorkflow:
    @pytest.mark.integration
    @patch(
        "api.batch.batch_conversion_service.start_batch_conversion",
        new_callable=AsyncMock,
    )
    @patch(
        "api.batch.batch_conversion_service.create_batch_job", new_callable=AsyncMock
    )
    def test_batch_conversion_complete_workflow(
        self, mock_create, mock_start, client, tmp_path
    ):
        mock_create.return_value = {
            "batch_id": "batch-1",
            "total_files": 3,
            "status": "created",
        }
        mock_start.return_value = {"batch_id": "batch-1", "status": "processing"}

        files = []
        handles = []
        try:
            for index in range(3):
                path = tmp_path / f"test{index}.txt"
                path.write_text(f"content {index}")
                handle = path.open("rb")
                handles.append(handle)
                files.append(("files", (path.name, handle, "text/plain")))

            response = client.post(
                "/api/batch/convert",
                files=files,
                data={"target_format": "pdf"},
            )
        finally:
            for handle in handles:
                handle.close()

        assert response.status_code == 200
        assert response.json()["batch_id"] == "batch-1"
        assert response.json()["total_files"] == 3

    @pytest.mark.integration
    @patch("api.batch.batch_conversion_service.cleanup_completed_batches")
    @patch("api.batch.batch_conversion_service.get_all_batches")
    def test_batch_list_and_cleanup_workflow(self, mock_list, mock_cleanup, client):
        mock_list.return_value = {
            "batch-1": {"batch_id": "batch-1", "status": "completed"}
        }
        list_response = client.get("/api/batch/list")
        assert list_response.status_code == 200
        assert list_response.json()["count"] == 1

        cleanup_response = client.post("/api/batch/cleanup")
        assert cleanup_response.status_code == 200
        mock_cleanup.assert_called_once_with(max_age_hours=2)


class TestAIServiceWorkflow:
    @pytest.mark.integration
    @patch("api.ai.AIService")
    def test_ai_providers_discovery(self, mock_service, client):
        instance = mock_service.return_value
        instance.provider = "deepseek"
        instance.get_available_providers.return_value = ["deepseek"]

        response = client.get("/api/ai/providers")
        assert response.status_code == 200
        assert response.json() == {"providers": ["deepseek"], "default": "deepseek"}

    @pytest.mark.integration
    def test_ai_enhancement_types(self, client):
        response = client.get("/api/ai/enhancement-types")
        assert response.status_code == 200
        data = response.json()
        assert "enhancement_types" in data
        assert len(data["enhancement_types"]) > 0

    @pytest.mark.integration
    @patch("api.ai.AIService")
    def test_ai_summary_workflow(self, mock_service, client):
        from services.ai_service import AIResult

        instance = mock_service.return_value
        instance.generate_summary = AsyncMock(
            return_value=AIResult(
                content="Test summary",
                provider="deepseek",
                model="deepseek-chat",
                processing_time=0.5,
            )
        )
        response = client.post(
            "/api/ai/summary",
            json={"text": "Long text", "max_length": 100},
        )
        assert response.status_code == 200
        assert response.json()["summary"] == "Test summary"


class TestFileCleanupWorkflow:
    @pytest.mark.integration
    def test_cleanup_status_and_run_workflow(self, client):
        status_response = client.get("/api/cleanup/status")
        assert status_response.status_code == 200
        assert "disk_usage" in status_response.json()

        run_response = client.post("/api/cleanup/run")
        assert run_response.status_code == 200
        assert "statistics" in run_response.json()


class TestErrorHandlingWorkflow:
    @pytest.mark.integration
    def test_invalid_file_format_workflow(self, client, temp_test_file):
        with temp_test_file.open("rb") as handle:
            response = client.post(
                "/api/convert",
                files={"file": ("test.txt", handle, "text/plain")},
                data={"target_format": "invalid_format"},
            )
        assert response.status_code == 400

    @pytest.mark.integration
    def test_missing_file_workflow(self, client):
        response = client.post("/api/convert", data={"target_format": "pdf"})
        assert response.status_code == 422

    @pytest.mark.integration
    def test_nonexistent_batch_workflow(self, client):
        response = client.get("/api/batch/status/nonexistent-batch-id")
        assert response.status_code == 404


class TestConcurrentOperations:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, client):
        async def make_health_request():
            return client.get("/api/health")

        responses = await asyncio.gather(*(make_health_request() for _ in range(10)))
        assert all(response.status_code == 200 for response in responses)
        assert all(response.json()["status"] == "healthy" for response in responses)


class TestServiceInteractions:
    @pytest.mark.integration
    @patch("api.conversion.conversion_service.convert_file", new_callable=AsyncMock)
    def test_conversion_and_cleanup_interaction(
        self, mock_convert, client, temp_test_file
    ):
        mock_convert.return_value = conversion_result()
        with temp_test_file.open("rb") as handle:
            conversion_response = client.post(
                "/api/convert",
                files={"file": ("test.txt", handle, "text/plain")},
                data={"target_format": "pdf"},
            )
        assert conversion_response.status_code == 200
        assert client.post("/api/cleanup/run").status_code == 200

    @pytest.mark.integration
    def test_health_check_reflects_service_state(self, client):
        response = client.get("/api/health/detailed")
        assert response.status_code == 200
        components = response.json()["components"]
        assert "conversion_service" in components
        assert "batch_conversion_service" in components
        assert "ai_service" in components


class TestDataFlow:
    @pytest.mark.integration
    @patch("api.conversion.conversion_service.convert_file", new_callable=AsyncMock)
    def test_file_upload_to_download_flow(self, mock_convert, client, temp_test_file):
        mock_convert.return_value = conversion_result()
        with temp_test_file.open("rb") as handle:
            response = client.post(
                "/api/convert",
                files={"file": ("test.txt", handle, "text/plain")},
                data={"target_format": "pdf"},
            )
        assert response.status_code == 200
        assert response.json()["output_file"] == "test.pdf"
