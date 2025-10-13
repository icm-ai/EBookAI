"""
Tests for batch conversion API endpoints.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app


class TestBatchConversionAPI:
    """Test batch conversion API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_batch_convert_no_files(self, client):
        """Test batch conversion without files"""
        response = client.post("/api/batch/convert")
        assert response.status_code == 422

    def test_batch_convert_no_target_format(self, client):
        """Test batch conversion without target format"""
        files = [
            ("files", ("test1.epub", b"content1", "application/epub+zip")),
            ("files", ("test2.epub", b"content2", "application/epub+zip")),
        ]
        response = client.post("/api/batch/convert", files=files)
        assert response.status_code == 422

    def test_batch_convert_invalid_format(self, client):
        """Test batch conversion with invalid format"""
        files = [("files", ("test.epub", b"content", "application/epub+zip"))]
        data = {"target_format": "invalid"}
        response = client.post("/api/batch/convert", data=data, files=files)
        assert response.status_code == 400

    def test_batch_convert_empty_files(self, client):
        """Test batch conversion with empty files"""
        files = [
            ("files", ("test1.epub", b"", "application/epub+zip")),
            ("files", ("test2.epub", b"", "application/epub+zip")),
        ]
        data = {"target_format": "pdf"}
        response = client.post("/api/batch/convert", data=data, files=files)
        assert response.status_code == 400

    @patch("api.batch.batch_conversion_service.convert_batch")
    def test_batch_convert_success(self, mock_convert, client):
        """Test successful batch conversion"""
        mock_convert.return_value = {
            "batch_id": "test-batch-id",
            "status": "processing",
            "total_files": 2,
            "completed": 0,
            "failed": 0,
        }

        files = [
            ("files", ("test1.epub", b"content1", "application/epub+zip")),
            ("files", ("test2.epub", b"content2", "application/epub+zip")),
        ]
        data = {"target_format": "pdf"}

        response = client.post("/api/batch/convert", data=data, files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["batch_id"] == "test-batch-id"
        assert result["status"] == "processing"
        assert result["total_files"] == 2

    def test_batch_status_invalid_id(self, client):
        """Test batch status with invalid batch ID"""
        response = client.get("/api/batch/status/invalid-id")
        assert response.status_code in [400, 404]

    @patch("api.batch.batch_conversion_service.get_batch_status")
    def test_batch_status_success(self, mock_status, client):
        """Test successful batch status retrieval"""
        mock_status.return_value = {
            "batch_id": "test-batch-id",
            "status": "completed",
            "total_files": 2,
            "completed": 2,
            "failed": 0,
            "results": [],
        }

        response = client.get("/api/batch/status/test-batch-id")

        assert response.status_code == 200
        result = response.json()
        assert result["batch_id"] == "test-batch-id"
        assert result["status"] == "completed"

    @patch("api.batch.batch_conversion_service.get_all_batches")
    def test_batch_list(self, mock_list, client):
        """Test batch list endpoint"""
        mock_list.return_value = {
            "batches": [
                {"batch_id": "batch1", "status": "completed", "total_files": 2},
                {"batch_id": "batch2", "status": "processing", "total_files": 3},
            ],
            "total": 2,
        }

        response = client.get("/api/batch/list")

        assert response.status_code == 200
        result = response.json()
        assert "batches" in result
        assert "total" in result
        assert result["total"] == 2

    @patch("api.batch.batch_conversion_service.cleanup_completed_batches")
    def test_batch_cleanup(self, mock_cleanup, client):
        """Test batch cleanup endpoint"""
        mock_cleanup.return_value = {
            "cleaned_batches": 3,
            "freed_space_mb": 150.5,
        }

        response = client.post("/api/batch/cleanup")

        assert response.status_code == 200
        result = response.json()
        assert "cleaned_batches" in result
        assert result["cleaned_batches"] == 3

    def test_batch_convert_single_file(self, client):
        """Test batch conversion with single file"""
        files = [("files", ("test.epub", b"content", "application/epub+zip"))]
        data = {"target_format": "pdf"}

        with patch("api.batch.batch_conversion_service.convert_batch") as mock:
            mock.return_value = {
                "batch_id": "test-id",
                "status": "processing",
                "total_files": 1,
                "completed": 0,
                "failed": 0,
            }

            response = client.post("/api/batch/convert", data=data, files=files)
            assert response.status_code == 200

    @patch("api.batch.batch_conversion_service.convert_batch")
    def test_batch_convert_large_batch(self, mock_convert, client):
        """Test batch conversion with many files"""
        mock_convert.return_value = {
            "batch_id": "large-batch-id",
            "status": "processing",
            "total_files": 10,
            "completed": 0,
            "failed": 0,
        }

        files = [
            ("files", (f"test{i}.epub", b"content", "application/epub+zip"))
            for i in range(10)
        ]
        data = {"target_format": "pdf"}

        response = client.post("/api/batch/convert", data=data, files=files)

        assert response.status_code == 200
        result = response.json()
        assert result["total_files"] == 10

    def test_batch_status_nonexistent(self, client):
        """Test status for nonexistent batch"""
        import uuid

        batch_id = str(uuid.uuid4())
        response = client.get(f"/api/batch/status/{batch_id}")

        # Should return 404 or empty result
        assert response.status_code in [200, 404]
