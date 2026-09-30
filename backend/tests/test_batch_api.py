"""Tests for the current batch conversion API contract."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


class TestBatchConversionAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_batch_convert_no_files(self, client):
        response = client.post("/api/batch/convert")
        assert response.status_code == 422

    def test_batch_convert_no_target_format(self, client):
        files = [("files", ("test.epub", b"content", "application/epub+zip"))]
        response = client.post("/api/batch/convert", files=files)
        assert response.status_code == 422

    def test_batch_convert_invalid_format(self, client):
        files = [("files", ("test.epub", b"content", "application/epub+zip"))]
        response = client.post(
            "/api/batch/convert",
            data={"target_format": "invalid"},
            files=files,
        )
        assert response.status_code == 400

    def test_batch_convert_empty_files(self, client):
        files = [
            ("files", ("test1.epub", b"", "application/epub+zip")),
            ("files", ("test2.epub", b"", "application/epub+zip")),
        ]
        response = client.post(
            "/api/batch/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 400

    @patch(
        "api.batch.batch_conversion_service.start_batch_conversion",
        new_callable=AsyncMock,
    )
    @patch(
        "api.batch.batch_conversion_service.create_batch_job", new_callable=AsyncMock
    )
    def test_batch_convert_success(self, mock_create, mock_start, client):
        mock_create.return_value = {
            "batch_id": "test-batch-id",
            "total_files": 2,
            "status": "created",
        }
        mock_start.return_value = {
            "batch_id": "test-batch-id",
            "status": "processing",
        }
        files = [
            ("files", ("test1.epub", b"content1", "application/epub+zip")),
            ("files", ("test2.epub", b"content2", "application/epub+zip")),
        ]
        response = client.post(
            "/api/batch/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 200
        result = response.json()
        assert result["batch_id"] == "test-batch-id"
        assert result["status"] == "processing"
        assert result["total_files"] == 2

    def test_batch_status_invalid_id(self, client):
        response = client.get("/api/batch/status/invalid-id")
        assert response.status_code == 404

    @patch("api.batch.batch_conversion_service.get_batch_status")
    def test_batch_status_success(self, mock_status, client):
        mock_status.return_value = {
            "batch_id": "test-batch-id",
            "status": "completed",
            "total_files": 2,
            "completed_files": 2,
            "failed_files": 0,
            "tasks": [],
            "progress_percent": 100,
        }
        response = client.get("/api/batch/status/test-batch-id")
        assert response.status_code == 200
        result = response.json()
        assert result["batch_id"] == "test-batch-id"
        assert result["status"]["status"] == "completed"

    @patch("api.batch.batch_conversion_service.get_all_batches")
    def test_batch_list(self, mock_list, client):
        mock_list.return_value = {
            "batch1": {"batch_id": "batch1", "status": "completed"},
            "batch2": {"batch_id": "batch2", "status": "processing"},
        }
        response = client.get("/api/batch/list")
        assert response.status_code == 200
        result = response.json()
        assert result["count"] == 2
        assert set(result["batches"]) == {"batch1", "batch2"}

    @patch("api.batch.batch_conversion_service.cleanup_completed_batches")
    def test_batch_cleanup(self, mock_cleanup, client):
        response = client.post("/api/batch/cleanup")
        assert response.status_code == 200
        assert response.json()["message"] == "Cleanup completed successfully"
        mock_cleanup.assert_called_once_with(max_age_hours=2)

    @patch(
        "api.batch.batch_conversion_service.start_batch_conversion",
        new_callable=AsyncMock,
    )
    @patch(
        "api.batch.batch_conversion_service.create_batch_job", new_callable=AsyncMock
    )
    def test_batch_convert_single_file(self, mock_create, mock_start, client):
        mock_create.return_value = {
            "batch_id": "test-id",
            "total_files": 1,
            "status": "created",
        }
        mock_start.return_value = {"batch_id": "test-id", "status": "processing"}
        files = [("files", ("test.epub", b"content", "application/epub+zip"))]
        response = client.post(
            "/api/batch/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 200
        assert response.json()["total_files"] == 1

    @patch(
        "api.batch.batch_conversion_service.start_batch_conversion",
        new_callable=AsyncMock,
    )
    @patch(
        "api.batch.batch_conversion_service.create_batch_job", new_callable=AsyncMock
    )
    def test_batch_convert_large_batch(self, mock_create, mock_start, client):
        mock_create.return_value = {
            "batch_id": "large-batch-id",
            "total_files": 10,
            "status": "created",
        }
        mock_start.return_value = {
            "batch_id": "large-batch-id",
            "status": "processing",
        }
        files = [
            ("files", (f"test{i}.epub", b"content", "application/epub+zip"))
            for i in range(10)
        ]
        response = client.post(
            "/api/batch/convert", data={"target_format": "pdf"}, files=files
        )
        assert response.status_code == 200
        assert response.json()["total_files"] == 10

    def test_batch_status_nonexistent(self, client):
        response = client.get("/api/batch/status/nonexistent-batch-id")
        assert response.status_code == 404
