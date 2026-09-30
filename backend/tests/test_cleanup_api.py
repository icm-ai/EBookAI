"""Tests for cleanup API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


class TestCleanupAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_success(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.cleanup_old_files = AsyncMock(
            return_value={
                "upload_files_removed": 5,
                "output_files_removed": 3,
                "upload_space_freed_mb": 25.5,
                "output_space_freed_mb": 15.2,
                "errors": [],
            }
        )

        response = client.post("/api/cleanup/run")
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["statistics"]["files_removed"]["total"] == 8
        assert result["statistics"]["space_freed_mb"]["total"] == 40.7

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_with_errors(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.cleanup_old_files = AsyncMock(
            return_value={
                "upload_files_removed": 2,
                "output_files_removed": 1,
                "upload_space_freed_mb": 10.0,
                "output_space_freed_mb": 5.0,
                "errors": ["file1", "file2"],
            }
        )
        response = client.post("/api/cleanup/run")
        assert response.status_code == 200
        assert len(response.json()["statistics"]["errors"]) == 2

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_failure(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.cleanup_old_files = AsyncMock(side_effect=Exception("Cleanup failed"))
        response = client.post("/api/cleanup/run")
        assert response.status_code == 500
        assert "error" in response.json()

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_success(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 150.5, "file_count": 25},
            "output_dir": {"size_mb": 200.3, "file_count": 30},
            "total": {"size_mb": 350.8, "file_count": 55},
        }
        manager.max_age_seconds = 86400
        manager.cleanup_interval_seconds = 3600

        response = client.get("/api/cleanup/status")
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        assert result["disk_usage"]["uploads"]["file_count"] == 25
        assert result["disk_usage"]["outputs"]["file_count"] == 30
        assert result["disk_usage"]["total"]["file_count"] == 55
        assert result["config"]["max_age_hours"] == 24
        assert result["config"]["cleanup_interval_minutes"] == 60

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_empty(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 0, "file_count": 0},
            "output_dir": {"size_mb": 0, "file_count": 0},
            "total": {"size_mb": 0, "file_count": 0},
        }
        manager.max_age_seconds = 86400
        manager.cleanup_interval_seconds = 3600
        response = client.get("/api/cleanup/status")
        assert response.status_code == 200
        assert response.json()["disk_usage"]["total"]["file_count"] == 0

    @patch("api.cleanup.get_cleanup_manager")
    def test_get_cleanup_status_failure(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.get_disk_usage.side_effect = Exception("Disk access failed")
        response = client.get("/api/cleanup/status")
        assert response.status_code == 500
        assert "error" in response.json()

    @patch("api.cleanup.get_cleanup_manager")
    def test_run_cleanup_no_files_removed(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.cleanup_old_files = AsyncMock(
            return_value={
                "upload_files_removed": 0,
                "output_files_removed": 0,
                "upload_space_freed_mb": 0,
                "output_space_freed_mb": 0,
                "errors": [],
            }
        )
        response = client.post("/api/cleanup/run")
        assert response.status_code == 200
        result = response.json()["statistics"]
        assert result["files_removed"]["total"] == 0
        assert result["space_freed_mb"]["total"] == 0

    @patch("api.cleanup.get_cleanup_manager")
    def test_cleanup_status_large_numbers(self, mock_get_manager, client):
        manager = mock_get_manager.return_value
        manager.get_disk_usage.return_value = {
            "upload_dir": {"size_mb": 5000.75, "file_count": 1500},
            "output_dir": {"size_mb": 8000.25, "file_count": 2000},
            "total": {"size_mb": 13001.0, "file_count": 3500},
        }
        manager.max_age_seconds = 43200
        manager.cleanup_interval_seconds = 1800
        response = client.get("/api/cleanup/status")
        assert response.status_code == 200
        result = response.json()
        assert result["disk_usage"]["total"]["size_mb"] == 13001.0
        assert result["config"]["max_age_hours"] == 12
        assert result["config"]["cleanup_interval_minutes"] == 30
