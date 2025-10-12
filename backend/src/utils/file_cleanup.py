"""
File cleanup utility for managing temporary files.
Automatically removes old uploaded and output files to prevent disk space issues.
"""

import asyncio
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


class FileCleanupManager:
    """Manages automatic cleanup of temporary files."""

    def __init__(
        self,
        upload_dir: str = "uploads",
        output_dir: str = "outputs",
        max_age_hours: int = 24,
        cleanup_interval_minutes: int = 60,
    ):
        """
        Initialize file cleanup manager.

        Args:
            upload_dir: Directory containing uploaded files
            output_dir: Directory containing output files
            max_age_hours: Maximum age of files in hours before cleanup
            cleanup_interval_minutes: Interval between cleanup runs in minutes
        """
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.max_age_seconds = max_age_hours * 3600
        self.cleanup_interval_seconds = cleanup_interval_minutes * 60
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            f"FileCleanupManager initialized: "
            f"max_age={max_age_hours}h, "
            f"interval={cleanup_interval_minutes}m"
        )

    def start(self):
        """Start the automatic cleanup background task."""
        if self._running:
            logger.warning("Cleanup manager already running")
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("File cleanup task started")

    async def stop(self):
        """Stop the automatic cleanup background task."""
        if not self._running:
            return

        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("File cleanup task stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        while self._running:
            try:
                await self.cleanup_old_files()
                await asyncio.sleep(self.cleanup_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def cleanup_old_files(self) -> dict:
        """
        Clean up old files from upload and output directories.

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "upload_files_removed": 0,
            "output_files_removed": 0,
            "upload_space_freed_mb": 0,
            "output_space_freed_mb": 0,
            "errors": [],
        }

        current_time = time.time()
        cutoff_time = current_time - self.max_age_seconds

        cutoff_datetime = datetime.fromtimestamp(cutoff_time)
        logger.info(f"Starting cleanup of files older than {cutoff_datetime}")

        # Clean upload directory
        if self.upload_dir.exists():
            upload_stats = await self._cleanup_directory(
                self.upload_dir, cutoff_time
            )
            stats["upload_files_removed"] = upload_stats["files_removed"]
            stats["upload_space_freed_mb"] = upload_stats["space_freed_mb"]
            stats["errors"].extend(upload_stats["errors"])

        # Clean output directory
        if self.output_dir.exists():
            output_stats = await self._cleanup_directory(
                self.output_dir, cutoff_time
            )
            stats["output_files_removed"] = output_stats["files_removed"]
            stats["output_space_freed_mb"] = output_stats["space_freed_mb"]
            stats["errors"].extend(output_stats["errors"])

        total_files = stats["upload_files_removed"] + stats["output_files_removed"]
        total_space = stats["upload_space_freed_mb"] + stats["output_space_freed_mb"]

        logger.info(
            f"Cleanup completed: {total_files} files removed, "
            f"{total_space:.2f} MB freed"
        )

        return stats

    async def _cleanup_directory(
        self, directory: Path, cutoff_time: float
    ) -> dict:
        """
        Clean up old files in a specific directory.

        Args:
            directory: Directory path to clean
            cutoff_time: Unix timestamp cutoff

        Returns:
            Dictionary with cleanup statistics for this directory
        """
        stats = {
            "files_removed": 0,
            "space_freed_mb": 0,
            "errors": [],
        }

        try:
            for item in directory.iterdir():
                try:
                    # Get file modification time
                    mtime = item.stat().st_mtime

                    if mtime < cutoff_time:
                        # Calculate file size before deletion
                        if item.is_file():
                            file_size = item.stat().st_size
                        elif item.is_dir():
                            file_size = self._get_dir_size(item)
                        else:
                            continue

                        # Remove file or directory
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)

                        stats["files_removed"] += 1
                        stats["space_freed_mb"] += file_size / (1024 * 1024)

                        age_hours = (time.time() - mtime) / 3600
                        logger.debug(
                            f"Removed: {item.name} "
                            f"(age: {age_hours:.1f}h, size: {file_size / 1024:.1f}KB)"
                        )

                except Exception as e:
                    error_msg = f"Error removing {item.name}: {str(e)}"
                    logger.warning(error_msg)
                    stats["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Error accessing directory {directory}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

        return stats

    def _get_dir_size(self, directory: Path) -> int:
        """Calculate total size of directory contents."""
        total_size = 0
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception as e:
            logger.warning(f"Error calculating directory size: {e}")
        return total_size

    async def cleanup_specific_file(self, file_path: str) -> bool:
        """
        Clean up a specific file.

        Args:
            file_path: Path to the file to clean up

        Returns:
            True if file was removed, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists():
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                logger.info(f"Cleaned up specific file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cleaning up {file_path}: {e}")
            return False

    def get_disk_usage(self) -> dict:
        """
        Get disk usage statistics for managed directories.

        Returns:
            Dictionary with disk usage information
        """
        stats = {
            "upload_dir": self._get_directory_stats(self.upload_dir),
            "output_dir": self._get_directory_stats(self.output_dir),
        }

        total_size = (
            stats["upload_dir"]["size_mb"] + stats["output_dir"]["size_mb"]
        )
        total_files = (
            stats["upload_dir"]["file_count"] + stats["output_dir"]["file_count"]
        )

        stats["total"] = {
            "size_mb": total_size,
            "file_count": total_files,
        }

        return stats

    def _get_directory_stats(self, directory: Path) -> dict:
        """Get statistics for a directory."""
        if not directory.exists():
            return {"size_mb": 0, "file_count": 0}

        total_size = 0
        file_count = 0

        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
        except Exception as e:
            logger.warning(f"Error getting directory stats: {e}")

        return {
            "size_mb": total_size / (1024 * 1024),
            "file_count": file_count,
        }


# Global instance
_cleanup_manager: Optional[FileCleanupManager] = None


def get_cleanup_manager() -> FileCleanupManager:
    """Get the global cleanup manager instance."""
    global _cleanup_manager
    if _cleanup_manager is None:
        max_age_hours = int(os.getenv("FILE_CLEANUP_MAX_AGE_HOURS", "24"))
        cleanup_interval = int(os.getenv("FILE_CLEANUP_INTERVAL_MINUTES", "60"))

        _cleanup_manager = FileCleanupManager(
            max_age_hours=max_age_hours,
            cleanup_interval_minutes=cleanup_interval,
        )
    return _cleanup_manager
