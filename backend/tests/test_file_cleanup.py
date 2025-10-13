"""
Tests for file cleanup functionality.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from utils.file_cleanup import FileCleanupManager


class TestFileCleanupManager:
    """Test file cleanup manager functionality"""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary upload and output directories"""
        upload_dir = tmp_path / "uploads"
        output_dir = tmp_path / "outputs"
        upload_dir.mkdir()
        output_dir.mkdir()
        return upload_dir, output_dir

    @pytest.fixture
    def cleanup_manager(self, temp_dirs):
        """Create cleanup manager instance"""
        upload_dir, output_dir = temp_dirs
        return FileCleanupManager(
            upload_dir=str(upload_dir),
            output_dir=str(output_dir),
            max_age_hours=1,
            cleanup_interval_minutes=1,
        )

    def test_initialization(self, cleanup_manager, temp_dirs):
        """Test cleanup manager initialization"""
        upload_dir, output_dir = temp_dirs
        assert cleanup_manager.upload_dir == Path(upload_dir)
        assert cleanup_manager.output_dir == Path(output_dir)
        assert cleanup_manager.max_age_seconds == 3600
        assert cleanup_manager.cleanup_interval_seconds == 60

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self, cleanup_manager, temp_dirs):
        """Test cleanup of old files"""
        upload_dir, output_dir = temp_dirs

        # Create old files
        old_file1 = upload_dir / "old_file1.txt"
        old_file2 = output_dir / "old_file2.pdf"
        old_file1.write_text("old content 1")
        old_file2.write_text("old content 2")

        # Set modification time to 2 hours ago
        old_time = time.time() - 7200
        old_file1.touch()
        old_file2.touch()

        with patch("time.time", return_value=time.time()):
            with patch("pathlib.Path.stat") as mock_stat:
                # Mock file modification time
                mock_stat.return_value.st_mtime = old_time
                mock_stat.return_value.st_size = 1024

                stats = await cleanup_manager.cleanup_old_files()

                assert stats["upload_files_removed"] >= 0
                assert stats["output_files_removed"] >= 0
                assert "errors" in stats

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_files(self, cleanup_manager, temp_dirs):
        """Test that recent files are not removed"""
        upload_dir, _ = temp_dirs

        # Create recent file
        recent_file = upload_dir / "recent_file.txt"
        recent_file.write_text("recent content")

        stats = await cleanup_manager.cleanup_old_files()

        # Recent file should still exist
        assert recent_file.exists()
        assert stats["upload_files_removed"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_directory_with_subdirectories(
        self, cleanup_manager, temp_dirs
    ):
        """Test cleanup of directories with subdirectories"""
        upload_dir, _ = temp_dirs

        # Create subdirectory with old files
        sub_dir = upload_dir / "task_123"
        sub_dir.mkdir()
        old_file = sub_dir / "file.txt"
        old_file.write_text("content")

        # Set modification time to 2 hours ago
        old_time = time.time() - 7200

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_time
            mock_stat.return_value.st_size = 1024

            stats = await cleanup_manager.cleanup_old_files()

            assert "errors" in stats

    @pytest.mark.asyncio
    async def test_cleanup_specific_file(self, cleanup_manager, temp_dirs):
        """Test cleanup of specific file"""
        upload_dir, _ = temp_dirs

        # Create test file
        test_file = upload_dir / "test.txt"
        test_file.write_text("test content")

        assert test_file.exists()

        result = await cleanup_manager.cleanup_specific_file(str(test_file))

        assert result is True
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_specific_nonexistent_file(self, cleanup_manager):
        """Test cleanup of nonexistent file"""
        result = await cleanup_manager.cleanup_specific_file("/nonexistent/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_specific_directory(self, cleanup_manager, temp_dirs):
        """Test cleanup of specific directory"""
        upload_dir, _ = temp_dirs

        # Create test directory
        test_dir = upload_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        assert test_dir.exists()

        result = await cleanup_manager.cleanup_specific_file(str(test_dir))

        assert result is True
        assert not test_dir.exists()

    def test_get_disk_usage(self, cleanup_manager, temp_dirs):
        """Test disk usage statistics"""
        upload_dir, output_dir = temp_dirs

        # Create test files
        (upload_dir / "file1.txt").write_text("test content 1")
        (upload_dir / "file2.txt").write_text("test content 2")
        (output_dir / "file3.pdf").write_text("test content 3")

        stats = cleanup_manager.get_disk_usage()

        assert "upload_dir" in stats
        assert "output_dir" in stats
        assert "total" in stats
        assert stats["upload_dir"]["file_count"] == 2
        assert stats["output_dir"]["file_count"] == 1
        assert stats["total"]["file_count"] == 3
        assert stats["total"]["size_mb"] > 0

    def test_get_disk_usage_empty_directories(self, cleanup_manager):
        """Test disk usage with empty directories"""
        stats = cleanup_manager.get_disk_usage()

        assert stats["upload_dir"]["size_mb"] == 0
        assert stats["upload_dir"]["file_count"] == 0
        assert stats["output_dir"]["size_mb"] == 0
        assert stats["output_dir"]["file_count"] == 0

    def test_get_directory_stats(self, cleanup_manager, temp_dirs):
        """Test directory statistics calculation"""
        upload_dir, _ = temp_dirs

        # Create test files
        (upload_dir / "file1.txt").write_text("a" * 1024)
        (upload_dir / "file2.txt").write_text("b" * 2048)

        stats = cleanup_manager._get_directory_stats(upload_dir)

        assert stats["file_count"] == 2
        assert stats["size_mb"] > 0

    def test_get_directory_stats_nonexistent(self, cleanup_manager):
        """Test stats for nonexistent directory"""
        stats = cleanup_manager._get_directory_stats(Path("/nonexistent"))

        assert stats["file_count"] == 0
        assert stats["size_mb"] == 0

    def test_get_dir_size(self, cleanup_manager, temp_dirs):
        """Test directory size calculation"""
        upload_dir, _ = temp_dirs

        # Create nested structure
        sub_dir = upload_dir / "sub"
        sub_dir.mkdir()
        (upload_dir / "file1.txt").write_text("a" * 1000)
        (sub_dir / "file2.txt").write_text("b" * 2000)

        size = cleanup_manager._get_dir_size(upload_dir)

        assert size == 3000

    def test_start_and_stop(self, cleanup_manager):
        """Test starting and stopping cleanup manager"""
        assert not cleanup_manager._running

        cleanup_manager.start()
        assert cleanup_manager._running
        assert cleanup_manager._cleanup_task is not None

        # Start again should log warning but not fail
        cleanup_manager.start()

    @pytest.mark.asyncio
    async def test_stop_cleanup_manager(self, cleanup_manager):
        """Test stopping cleanup manager"""
        cleanup_manager.start()
        assert cleanup_manager._running

        await cleanup_manager.stop()
        assert not cleanup_manager._running

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, cleanup_manager):
        """Test stopping when not running"""
        # Should not raise error
        await cleanup_manager.stop()
        assert not cleanup_manager._running

    @pytest.mark.asyncio
    async def test_cleanup_loop_error_handling(self, cleanup_manager):
        """Test error handling in cleanup loop"""
        cleanup_manager._running = True

        with patch.object(
            cleanup_manager, "cleanup_old_files", side_effect=Exception("Test error")
        ):
            # Start loop
            task = asyncio.create_task(cleanup_manager._cleanup_loop())

            # Let it run briefly
            await asyncio.sleep(0.1)

            # Stop loop
            cleanup_manager._running = False
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cleanup_with_errors(self, cleanup_manager, temp_dirs):
        """Test cleanup with file access errors"""
        upload_dir, _ = temp_dirs

        # Create file
        test_file = upload_dir / "test.txt"
        test_file.write_text("content")

        old_time = time.time() - 7200

        with patch("pathlib.Path.stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_time
            mock_stat.return_value.st_size = 1024

            with patch("pathlib.Path.unlink", side_effect=PermissionError()):
                stats = await cleanup_manager.cleanup_old_files()

                assert len(stats["errors"]) > 0


def test_get_cleanup_manager():
    """Test getting global cleanup manager instance"""
    from utils.file_cleanup import get_cleanup_manager

    manager1 = get_cleanup_manager()
    manager2 = get_cleanup_manager()

    # Should return same instance
    assert manager1 is manager2
