"""Tests for file cleanup functionality."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from utils.file_cleanup import FileCleanupManager


@pytest.fixture
def temp_dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    return upload_dir, output_dir


@pytest.fixture
def cleanup_manager(temp_dirs):
    upload_dir, output_dir = temp_dirs
    return FileCleanupManager(
        upload_dir=str(upload_dir),
        output_dir=str(output_dir),
        max_age_hours=1,
        cleanup_interval_minutes=1,
    )


class TestFileCleanupManager:
    def test_initialization(self, cleanup_manager, temp_dirs):
        upload_dir, output_dir = temp_dirs
        assert cleanup_manager.upload_dir == Path(upload_dir)
        assert cleanup_manager.output_dir == Path(output_dir)
        assert cleanup_manager.max_age_seconds == 3600
        assert cleanup_manager.cleanup_interval_seconds == 60

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self, cleanup_manager, temp_dirs):
        upload_dir, output_dir = temp_dirs
        old_upload = upload_dir / "old.txt"
        old_output = output_dir / "old.pdf"
        old_upload.write_text("old")
        old_output.write_text("old")
        old_time = time.time() - 7200
        os.utime(old_upload, (old_time, old_time))
        os.utime(old_output, (old_time, old_time))

        stats = await cleanup_manager.cleanup_old_files()
        assert stats["upload_files_removed"] == 1
        assert stats["output_files_removed"] == 1
        assert not old_upload.exists()
        assert not old_output.exists()

    @pytest.mark.asyncio
    async def test_cleanup_keeps_recent_files(self, cleanup_manager, temp_dirs):
        upload_dir, _ = temp_dirs
        recent = upload_dir / "recent.txt"
        recent.write_text("recent")
        stats = await cleanup_manager.cleanup_old_files()
        assert recent.exists()
        assert stats["upload_files_removed"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_specific_file(self, cleanup_manager, temp_dirs):
        upload_dir, _ = temp_dirs
        target = upload_dir / "test.txt"
        target.write_text("test")
        assert await cleanup_manager.cleanup_specific_file(str(target)) is True
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_cleanup_specific_nonexistent_file(self, cleanup_manager):
        assert (
            await cleanup_manager.cleanup_specific_file("/nonexistent/file.txt")
            is False
        )

    @pytest.mark.asyncio
    async def test_cleanup_specific_directory(self, cleanup_manager, temp_dirs):
        upload_dir, _ = temp_dirs
        target = upload_dir / "task"
        target.mkdir()
        (target / "file.txt").write_text("content")
        assert await cleanup_manager.cleanup_specific_file(str(target)) is True
        assert not target.exists()

    def test_get_disk_usage(self, cleanup_manager, temp_dirs):
        upload_dir, output_dir = temp_dirs
        (upload_dir / "a.txt").write_text("a")
        (upload_dir / "b.txt").write_text("bb")
        (output_dir / "c.pdf").write_text("ccc")
        stats = cleanup_manager.get_disk_usage()
        assert stats["upload_dir"]["file_count"] == 2
        assert stats["output_dir"]["file_count"] == 1
        assert stats["total"]["file_count"] == 3
        assert stats["total"]["size_mb"] > 0

    def test_get_disk_usage_empty_directories(self, cleanup_manager):
        stats = cleanup_manager.get_disk_usage()
        assert stats["upload_dir"] == {"size_mb": 0.0, "file_count": 0}
        assert stats["output_dir"] == {"size_mb": 0.0, "file_count": 0}

    def test_get_dir_size(self, cleanup_manager, temp_dirs):
        upload_dir, _ = temp_dirs
        sub = upload_dir / "sub"
        sub.mkdir()
        (upload_dir / "a.txt").write_text("a" * 1000)
        (sub / "b.txt").write_text("b" * 2000)
        assert cleanup_manager._get_dir_size(upload_dir) == 3000

    @pytest.mark.asyncio
    async def test_start_and_stop(self, cleanup_manager):
        assert not cleanup_manager._running
        cleanup_manager.start()
        assert cleanup_manager._running
        assert cleanup_manager._cleanup_task is not None
        cleanup_manager.start()
        await cleanup_manager.stop()
        assert not cleanup_manager._running

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, cleanup_manager):
        await cleanup_manager.stop()
        assert not cleanup_manager._running

    @pytest.mark.asyncio
    async def test_cleanup_loop_error_handling(self, cleanup_manager):
        cleanup_manager._running = True

        async def failing_cleanup():
            cleanup_manager._running = False
            raise RuntimeError("test error")

        cleanup_manager.cleanup_old_files = failing_cleanup
        task = asyncio.create_task(cleanup_manager._cleanup_loop())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_get_cleanup_manager():
    from utils.file_cleanup import get_cleanup_manager

    assert get_cleanup_manager() is get_cleanup_manager()
