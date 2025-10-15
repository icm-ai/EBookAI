import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock


@pytest.fixture
def client():
    """Create test client"""
    from main import app
    return TestClient(app)


@pytest.fixture
def temp_test_file(tmp_path):
    """Create a temporary test file"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test file for conversion.")
    return str(test_file)


class TestCompleteConversionWorkflow:
    """Test complete end-to-end conversion workflows"""

    @pytest.mark.integration
    def test_single_file_conversion_workflow(self, client, temp_test_file):
        """Test complete single file conversion workflow"""
        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            with open(temp_test_file, "rb") as f:
                response = client.post(
                    "/api/convert",
                    files={"file": ("test.txt", f, "text/plain")},
                    data={"target_format": "pdf"}
                )

            assert response.status_code == 200
            data = response.json()
            assert "output_file" in data
            assert data["target_format"] == "pdf"

    @pytest.mark.integration
    def test_health_to_conversion_workflow(self, client, temp_test_file):
        """Test workflow from health check to conversion"""
        health_response = client.get("/api/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"

        detailed_health = client.get("/api/health/detailed")
        assert detailed_health.status_code == 200

        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            with open(temp_test_file, "rb") as f:
                conversion_response = client.post(
                    "/api/convert",
                    files={"file": ("test.txt", f, "text/plain")},
                    data={"target_format": "pdf"}
                )

            assert conversion_response.status_code == 200


class TestBatchConversionWorkflow:
    """Test batch conversion workflows"""

    @pytest.mark.integration
    def test_batch_conversion_complete_workflow(self, client, tmp_path):
        """Test complete batch conversion workflow"""
        test_files = []
        for i in range(3):
            test_file = tmp_path / f"test{i}.txt"
            test_file.write_text(f"Test content {i}")
            test_files.append(test_file)

        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            files = [
                ("files", (f"test{i}.txt", open(str(f), "rb"), "text/plain"))
                for i, f in enumerate(test_files)
            ]

            response = client.post(
                "/api/batch/convert",
                files=files,
                data={"target_format": "pdf"}
            )

            for f in test_files:
                open(str(f)).close()

            assert response.status_code == 200
            data = response.json()
            assert "batch_id" in data
            assert data["total_files"] == 3

            batch_id = data["batch_id"]

            status_response = client.get(f"/api/batch/status/{batch_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["batch_id"] == batch_id

    @pytest.mark.integration
    def test_batch_list_and_cleanup_workflow(self, client, tmp_path):
        """Test batch listing and cleanup workflow"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            with open(str(test_file), "rb") as f:
                response = client.post(
                    "/api/batch/convert",
                    files=[("files", ("test.txt", f, "text/plain"))],
                    data={"target_format": "pdf"}
                )

            assert response.status_code == 200

            list_response = client.get("/api/batch/list")
            assert list_response.status_code == 200
            batches = list_response.json()
            assert len(batches) > 0

            cleanup_response = client.post("/api/batch/cleanup")
            assert cleanup_response.status_code == 200


class TestAIServiceWorkflow:
    """Test AI service workflows"""

    @pytest.mark.integration
    def test_ai_providers_discovery(self, client):
        """Test AI providers discovery workflow"""
        response = client.get("/api/ai/providers")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.integration
    def test_ai_enhancement_types(self, client):
        """Test AI enhancement types discovery"""
        response = client.get("/api/ai/enhancement-types")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.integration
    def test_ai_summary_workflow(self, client):
        """Test AI summary generation workflow"""
        with patch("services.ai_service.AIService.generate_summary") as mock_summary:
            from services.ai_service import AIResult
            mock_summary.return_value = AIResult(
                content="Test summary",
                provider="deepseek",
                model="deepseek-chat",
                processing_time=0.5
            )

            response = client.post(
                "/api/ai/summary",
                json={
                    "text": "This is a long text that needs to be summarized.",
                    "max_length": 100
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "summary" in data or "content" in data


class TestFileCleanupWorkflow:
    """Test file cleanup workflows"""

    @pytest.mark.integration
    def test_cleanup_status_and_run_workflow(self, client):
        """Test file cleanup status check and run workflow"""
        status_response = client.get("/api/cleanup/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert "disk_usage" in status_data or "uploads" in status_data

        run_response = client.post("/api/cleanup/run")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert "files_removed" in run_data or "success" in run_data


class TestErrorHandlingWorkflow:
    """Test error handling in workflows"""

    @pytest.mark.integration
    def test_invalid_file_format_workflow(self, client, temp_test_file):
        """Test workflow with invalid file format"""
        with open(temp_test_file, "rb") as f:
            response = client.post(
                "/api/convert",
                files={"file": ("test.txt", f, "text/plain")},
                data={"target_format": "invalid_format"}
            )

        assert response.status_code in [400, 422]

    @pytest.mark.integration
    def test_missing_file_workflow(self, client):
        """Test workflow with missing file"""
        response = client.post(
            "/api/convert",
            data={"target_format": "pdf"}
        )

        assert response.status_code in [400, 422]

    @pytest.mark.integration
    def test_nonexistent_batch_workflow(self, client):
        """Test workflow with nonexistent batch ID"""
        response = client.get("/api/batch/status/nonexistent-batch-id")

        assert response.status_code in [404, 400]


class TestConcurrentOperations:
    """Test concurrent operations"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, client):
        """Test concurrent health check requests"""
        async def make_health_request():
            return client.get("/api/health")

        tasks = [make_health_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)
        assert all(r.json()["status"] == "healthy" for r in responses)

    @pytest.mark.integration
    def test_concurrent_batch_creations(self, client, tmp_path):
        """Test concurrent batch job creations"""
        test_files = []
        for i in range(3):
            test_file = tmp_path / f"concurrent_test{i}.txt"
            test_file.write_text(f"Concurrent test content {i}")
            test_files.append(test_file)

        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            responses = []
            for test_file in test_files:
                with open(str(test_file), "rb") as f:
                    response = client.post(
                        "/api/batch/convert",
                        files=[("files", (test_file.name, f, "text/plain"))],
                        data={"target_format": "pdf"}
                    )
                    responses.append(response)

            assert all(r.status_code == 200 for r in responses)
            batch_ids = [r.json()["batch_id"] for r in responses]
            assert len(set(batch_ids)) == len(batch_ids)


class TestServiceInteractions:
    """Test interactions between different services"""

    @pytest.mark.integration
    def test_conversion_and_cleanup_interaction(self, client, temp_test_file):
        """Test interaction between conversion and cleanup services"""
        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            with open(temp_test_file, "rb") as f:
                conversion_response = client.post(
                    "/api/convert",
                    files={"file": ("test.txt", f, "text/plain")},
                    data={"target_format": "pdf"}
                )

            assert conversion_response.status_code == 200

            cleanup_response = client.post("/api/cleanup/run")
            assert cleanup_response.status_code == 200

    @pytest.mark.integration
    def test_health_check_reflects_service_state(self, client):
        """Test that health check accurately reflects service state"""
        detailed_health = client.get("/api/health/detailed")
        assert detailed_health.status_code == 200

        data = detailed_health.json()
        assert "components" in data
        assert "conversion_service" in data["components"]
        assert "batch_conversion_service" in data["components"]
        assert "ai_service" in data["components"]


class TestDataFlow:
    """Test data flow through the system"""

    @pytest.mark.integration
    def test_file_upload_to_download_flow(self, client, temp_test_file):
        """Test complete flow from file upload to download"""
        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            output_path = "/outputs/test_output.pdf"
            mock_convert.return_value = output_path

            with open(temp_test_file, "rb") as f:
                upload_response = client.post(
                    "/api/convert",
                    files={"file": ("test.txt", f, "text/plain")},
                    data={"target_format": "pdf"}
                )

            assert upload_response.status_code == 200
            conversion_data = upload_response.json()
            assert "output_file" in conversion_data

    @pytest.mark.integration
    def test_batch_progress_tracking_flow(self, client, tmp_path):
        """Test batch progress tracking throughout conversion"""
        test_file = tmp_path / "progress_test.txt"
        test_file.write_text("Progress test content")

        with patch("services.conversion_service.ConversionService.convert_file") as mock_convert:
            mock_convert.return_value = "/outputs/test.pdf"

            with open(str(test_file), "rb") as f:
                create_response = client.post(
                    "/api/batch/convert",
                    files=[("files", ("progress_test.txt", f, "text/plain"))],
                    data={"target_format": "pdf"}
                )

            assert create_response.status_code == 200
            batch_id = create_response.json()["batch_id"]

            status_response = client.get(f"/api/batch/status/{batch_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()
            assert "status" in status_data
            assert status_data["batch_id"] == batch_id
