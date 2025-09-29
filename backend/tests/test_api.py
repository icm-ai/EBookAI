import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app


class TestConversionAPI:
    """Test conversion API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "allowed_formats" in data

    def test_convert_no_file(self, client):
        """Test conversion endpoint without file"""
        response = client.post("/convert")

        assert response.status_code == 422  # Validation error

    def test_convert_invalid_format(self, client):
        """Test conversion with invalid target format"""
        test_data = {"target_format": "invalid_format"}
        files = {"file": ("test.epub", b"dummy content", "application/epub+zip")}

        response = client.post("/convert", data=test_data, files=files)

        assert response.status_code == 400
        assert "Unsupported target format" in response.json()["detail"]

    def test_convert_empty_file(self, client):
        """Test conversion with empty file"""
        test_data = {"target_format": "pdf"}
        files = {"file": ("test.epub", b"", "application/epub+zip")}

        response = client.post("/convert", data=test_data, files=files)

        assert response.status_code == 400
        assert "Empty file" in response.json()["detail"]

    @patch("api.conversion.conversion_service.convert_file")
    def test_convert_success(self, mock_convert, client):
        """Test successful conversion"""
        mock_convert.return_value = {
            "task_id": "test-task-id",
            "status": "completed",
            "output_file": "test_output.pdf",
            "message": "Conversion completed successfully",
        }

        test_data = {"target_format": "pdf"}
        files = {"file": ("test.epub", b"dummy epub content", "application/epub+zip")}

        response = client.post("/convert", data=test_data, files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["task_id"] == "test-task-id"

    def test_download_invalid_filename(self, client):
        """Test download with invalid filename"""
        response = client.get("/download/../invalid")

        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]

    def test_download_nonexistent_file(self, client):
        """Test download of nonexistent file"""
        response = client.get("/download/nonexistent.pdf")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    def test_status_invalid_task_id(self, client):
        """Test status with invalid task ID format"""
        response = client.get("/status/invalid-task-id")

        assert response.status_code == 400
        assert "Invalid task ID format" in response.json()["detail"]

    def test_status_valid_task_id(self, client):
        """Test status with valid task ID"""
        import uuid

        task_id = str(uuid.uuid4())

        response = client.get(f"/status/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data

    def test_files_endpoint(self, client):
        """Test files listing endpoint"""
        response = client.get("/files")

        assert response.status_code == 200
        data = response.json()
        assert "file_type" in data
        assert "files" in data
        assert "total_files" in data

    def test_files_endpoint_input_type(self, client):
        """Test files listing with input type"""
        response = client.get("/files?file_type=input")

        assert response.status_code == 200
        data = response.json()
        assert data["file_type"] == "input"

    def test_cleanup_invalid_task_id(self, client):
        """Test cleanup with invalid task ID"""
        response = client.delete("/cleanup/invalid-task-id")

        assert response.status_code == 400
        assert "Invalid task ID format" in response.json()["detail"]

    def test_cleanup_valid_task_id(self, client):
        """Test cleanup with valid task ID"""
        import uuid

        task_id = str(uuid.uuid4())

        response = client.delete(f"/cleanup/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "cleaned_files" in data
