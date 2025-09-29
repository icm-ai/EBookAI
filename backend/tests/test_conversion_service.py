import pytest
import asyncio
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from services.conversion_service import ConversionService
from utils.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    ConversionError,
    ConversionTimeoutError,
)


class TestConversionService:
    """Test file conversion service functionality"""

    @pytest.fixture
    def service(self):
        """Create conversion service instance"""
        return ConversionService()

    @pytest.fixture
    def test_file_path(self, tmp_path):
        """Create temporary test file"""
        test_file = tmp_path / "test.epub"
        test_file.write_text("dummy content")
        return test_file

    @pytest.mark.asyncio
    async def test_convert_file_missing_file(self, service):
        """Test conversion with missing input file"""
        with pytest.raises(ResourceNotFoundError, match="Input file not found"):
            await service.convert_file("/nonexistent/file.epub", "pdf")

    @pytest.mark.asyncio
    async def test_convert_file_invalid_source_format(self, service, test_file_path):
        """Test conversion with invalid source format"""
        invalid_file = test_file_path.parent / "test.invalid"
        invalid_file.write_text("dummy")

        with pytest.raises(ValidationError, match="Unsupported source format"):
            await service.convert_file(str(invalid_file), "pdf")

    @pytest.mark.asyncio
    async def test_convert_file_invalid_target_format(self, service, test_file_path):
        """Test conversion with invalid target format"""
        with pytest.raises(ValidationError, match="Unsupported target format"):
            await service.convert_file(str(test_file_path), "docx")

    @pytest.mark.asyncio
    async def test_convert_file_same_format(self, service, test_file_path):
        """Test conversion with same source and target format"""
        with pytest.raises(ValidationError, match="Source and target formats cannot be the same"):
            await service.convert_file(str(test_file_path), "epub")

    @pytest.mark.asyncio
    async def test_convert_file_unsupported_conversion(self, service):
        """Test unsupported conversion path"""
        # Create temporary mobi file (unsupported format)
        test_file = Path("/tmp/test.mobi")
        test_file.write_text("dummy")

        try:
            with pytest.raises(ValidationError, match="Unsupported source format"):
                await service.convert_file(str(test_file), "pdf")
        finally:
            if test_file.exists():
                test_file.unlink()

    @pytest.mark.asyncio
    @patch('services.conversion_service.ConversionService._epub_to_pdf')
    async def test_epub_to_pdf_conversion(self, mock_epub_to_pdf, service, test_file_path):
        """Test successful EPUB to PDF conversion"""
        mock_epub_to_pdf.return_value = None
        task_id = str(uuid.uuid4())

        result = await service.convert_file(str(test_file_path), "pdf", task_id)

        assert result["task_id"] == task_id
        assert result["status"] == "completed"
        assert result["output_file"].endswith(".pdf")
        mock_epub_to_pdf.assert_called_once()

    @pytest.mark.asyncio
    @patch('services.conversion_service.ConversionService._pdf_to_epub')
    async def test_pdf_to_epub_conversion(self, mock_pdf_to_epub, service, tmp_path):
        """Test successful PDF to EPUB conversion"""
        mock_pdf_to_epub.return_value = None

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy pdf content")
        task_id = str(uuid.uuid4())

        result = await service.convert_file(str(pdf_file), "epub", task_id)

        assert result["task_id"] == task_id
        assert result["status"] == "completed"
        assert result["output_file"].endswith(".epub")
        mock_pdf_to_epub.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversion_timeout(self, service, test_file_path):
        """Test conversion timeout handling"""
        with patch('services.conversion_service.asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()

            with pytest.raises(ConversionTimeoutError, match="Conversion timed out after"):
                await service.convert_file(str(test_file_path), "pdf")

    def test_cleanup_file(self, service, tmp_path):
        """Test file cleanup functionality"""
        test_file = tmp_path / "cleanup_test.txt"
        test_file.write_text("test content")

        assert test_file.exists()
        service.cleanup_file(str(test_file))
        assert not test_file.exists()

    def test_cleanup_nonexistent_file(self, service):
        """Test cleanup of nonexistent file (should not raise error)"""
        # Should not raise any exception
        service.cleanup_file("/nonexistent/file.txt")

    def test_get_conversion_status(self, service):
        """Test getting conversion status"""
        task_id = str(uuid.uuid4())
        result = service.get_conversion_status(task_id)

        assert result["task_id"] == task_id
        assert result["status"] == "completed"  # Simplified implementation