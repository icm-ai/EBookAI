"""
Tests for cleanup API endpoints.
"""

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import app


class TestCleanupAPI:
    """Test cleanup API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_success(self, mock_get_manager, client):
        """Test successful manual cleanup"""
        mock_manager = mock_get_manager.return_value
        mock_manager.cleanup_old_files.return_value = {
            "upload_files_removed": 5,
            "output_files_removed": 3,
            "upload_space_freed_mb": 25.5,
            "output_space_freed_mb": 15.2,
            "errors": [],
        }

        response = client.post("/api/cleanup/run")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "statistics" in result
        assert result["statistics"]["files_removed"]["total"] == 8
        assert result["statistics"]["space_freed_mb"]["total"] == 40.7

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_with_errors(self, mock_get_manager, client):
        """Test cleanup with errors"""
        mock_manager = mock_get_manager.return_value
        mock_manager.cleanup_old_files.return_value = {
            "upload_files_removed": 2,
            "output_files_removed": 1,
            "upload_space_freed_mb": 10.0,
            "output_space_freed_mb": 5.0,
            "errors": ["Error deleting file1.txt", "Permission denied for file2.pdf"],
        }

        response = client.post("/api/cleanup/run")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert len(result["statistics"]["errors"]) == 2

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_failure(self, mock_get_manager, client):
        """Test cleanup failure"""
        mock_manager = mock_get_manager.return_value
        mock_manager.cleanup_old_files.side_effect = Exception("Cleanup failed")

        response = client.post("/api/cleanup/run")

        assert response.status_code == 500
        assert "Cleanup failed" in response.json()["detail"]

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_success(self, mock_get_manager, client):
        """Test successful cleanup status retrieval"""
        mock_manager = mock_get_manager.return_value
        mock_manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 150.5, "file_count": 25},
            "output_dir": {"size_mb": 200.3, "file_count": 30},
            "total": {"size_mb": 350.8, "file_count": 55},
        }
        mock_manager.max_age_seconds = 86400
        mock_manager.cleanup_interval_seconds = 3600

        response = client.get("/api/cleanup/status")

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert "disk_usage" in result
        assert result["disk_usage"]["uploads"]["file_count"] == 25
        assert result["disk_usage"]["outputs"]["file_count"] == 30
        assert result["disk_usage"]["total"]["file_count"] == 55
        assert "config" in result
        assert result["config"]["max_age_hours"] == 24
        assert result["config"]["cleanup_interval_minutes"] == 60

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_empty(self, mock_get_manager, client):
        """Test cleanup status with empty directories"""
        mock_manager = mock_get_manager.return_value
        mock_manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 0, "file_count": 0},
            "output_dir": {"size_mb": 0, "file_count": 0},
            "total": {"size_mb": 0, "file_count": 0},
        }
        mock_manager.max_age_seconds = 86400
        mock_manager.cleanup_interval_seconds = 3600

        response = client.get("/api/cleanup/status")

        assert response.status_code == 200
        result = response.json()
        assert result["disk_usage"]["total"]["file_count"] == 0
        assert result["disk_usage"]["total"]["size_mb"] == 0

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_failure(self, mock_get_manager, client):
        """Test cleanup status failure"""
        mock_manager = mock_get_manager.return_value
        mock_manager.get_disk_usage.side_effect = Exception("Disk access failed")

        response = client.get("/api/cleanup/status")

        assert response.status_code == 500
        assert "Failed to get status" in response.json()["detail"]

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_no_files_removed(self, mock_get_manager, client):
        """Test cleanup when no files need to be removed"""
        mock_manager = mock_get_manager.return_value
        mock_manager.cleanup_old_files.return_value = {
            "upload_files_removed": 0,
            "output_files_removed": 0,
            "upload_space_freed_mb": 0,
            "output_space_freed_mb": 0,
            "errors": [],
        }

        response = client.post("/api/cleanup/run")

        assert response.status_code == 200
        result = response.json()
        assert result["statistics"]["files_removed"]["total"] == 0
        assert result["statistics"]["space_freed_mb"]["total"] == 0

    @patch("api.cleanup.get_cleanup_manager")
    def test_cleanup_status_large_numbers(self, mock_get_manager, client):
        """Test status with large file counts and sizes"""
        mock_manager = mock_get_manager.return_value
        mock_manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 5000.75, "file_count": 1500},
            "output_dir": {"size_mb": 8000.25, "file_count": 2000},
            "total": {"size_mb": 13001.0, "file_count": 3500},
        }
        mock_manager.max_age_seconds = 43200
        mock_manager.cleanup_interval_seconds = 1800

        response = client.get("/api/cleanup/status")

        assert response.status_code == 200
        result = response.json()
        assert result["disk_usage"]["total"]["size_mb"] == 13001.0
        assert result["config"]["max_age_hours"] == 12
        assert result["config"]["cleanup_interval_minutes"] == 30
