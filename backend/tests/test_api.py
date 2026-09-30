from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


class TestConversionAPI:
    """Tests for the current /api conversion contract."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ebook-ai-api"
        assert "version" in data

    def test_convert_no_file(self, client):
        response = client.post("/api/convert")
        assert response.status_code == 422

    def test_convert_invalid_format(self, client):
        files = {"file": ("test.epub", b"dummy content", "application/epub+zip")}
        response = client.post(
            "/api/convert", data={"target_format": "invalid_format"}, files=files
        )
        assert response.status_code == 400

    def test_convert_empty_file(self, client):
        files = {"file": ("test.epub", b"", "application/epub+zip")}
        response = client.post(
            "/api/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 400

    @patch("api.conversion.conversion_service.convert_file", new_callable=AsyncMock)
    def test_convert_success(self, mock_convert, client):
        mock_convert.return_value = {
            "task_id": "test-task-id",
            "status": "completed",
            "output_file": "test_output.pdf",
            "message": "Conversion completed successfully",
        }
        files = {"file": ("test.epub", b"dummy epub content", "application/epub+zip")}
        response = client.post(
            "/api/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["task_id"] == "test-task-id"

    def test_download_invalid_filename(self, client):
        response = client.get("/api/download/.hidden")
        assert response.status_code == 400

    def test_download_nonexistent_file(self, client):
        response = client.get("/api/download/nonexistent.pdf")
        assert response.status_code == 404

    def test_status_invalid_task_id(self, client):
        response = client.get("/api/status/invalid-task-id")
        assert response.status_code == 400

    def test_status_valid_task_id(self, client):
        import uuid

        task_id = str(uuid.uuid4())
        response = client.get(f"/api/status/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data

    def test_files_endpoint(self, client):
        response = client.get("/api/files")
        assert response.status_code == 200
        data = response.json()
        assert "file_type" in data
        assert "files" in data
        assert "total_files" in data

    def test_files_endpoint_input_type(self, client):
        response = client.get("/api/files?file_type=input")
        assert response.status_code == 200
        assert response.json()["file_type"] == "input"

    def test_cleanup_invalid_task_id(self, client):
        response = client.delete("/api/cleanup/invalid-task-id")
        assert response.status_code == 400

    def test_cleanup_valid_task_id(self, client):
        import uuid

        task_id = str(uuid.uuid4())
        response = client.delete(f"/api/cleanup/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "cleaned_files" in data
