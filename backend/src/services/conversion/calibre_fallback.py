"""
Calibre Fallback Module - Fallback conversion using Calibre ebook-convert

This module provides Calibre integration as a fallback conversion engine:
- Automatic detection of Calibre availability
- Wrapper for ebook-convert command
- Error handling and logging
- Quality comparison with custom pipeline
- Fallback trigger management
"""

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.logging_config import get_logger

# Import configuration
from config import ENABLE_CALIBRE_FALLBACK, CALIBRE_QUALITY_THRESHOLD, CALIBRE_TIMEOUT


@dataclass
class CalibreResult:
    """Result of Calibre conversion"""
    success: bool
    output_path: Optional[Path]
    error_message: Optional[str]
    processing_time: float
    command_used: str
    stdout: str
    stderr: str
    file_size: int = 0
    quality_indicators: Dict[str, Any] = None


@dataclass
class ConversionQualityMetrics:
    """Quality metrics for conversion comparison"""
    text_extraction_quality: float
    structure_preservation: float
    image_quality: float
    metadata_completeness: float
    overall_score: float
    file_size_ratio: float


class CalibreFallback:
    """Calibre ebook-convert wrapper for fallback conversion"""

    def __init__(self):
        self.logger = get_logger("calibre_fallback")
        self.calibre_available = self._check_calibre_availability()
        self.calibre_version = self._get_calibre_version() if self.calibre_available else None

    def _check_calibre_availability(self) -> bool:
        """Check if Calibre ebook-convert is available"""
        try:
            result = subprocess.run(
                ['ebook-convert', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.info("Calibre ebook-convert is available")
                return True
            else:
                self.logger.warning("Calibre ebook-convert not found in PATH")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.warning(f"Calibre availability check failed: {str(e)}")
            return False

    def _get_calibre_version(self) -> Optional[str]:
        """Get Calibre version information"""
        try:
            result = subprocess.run(
                ['ebook-convert', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if Calibre fallback is available"""
        return ENABLE_CALIBRE_FALLBACK and self.calibre_available

    def convert_pdf_to_epub(self,
                           input_path: Path,
                           output_path: Path,
                           options: Dict[str, Any] = None) -> CalibreResult:
        """
        Convert PDF to EPUB using Calibre ebook-convert

        Args:
            input_path: Path to input PDF file
            output_path: Path for output EPUB file
            options: Additional conversion options

        Returns:
            CalibreResult with conversion details
        """
        if not self.is_available():
            return CalibreResult(
                success=False,
                output_path=None,
                error_message="Calibre is not available",
                processing_time=0,
                command_used="",
                stdout="",
                stderr=""
            )

        start_time = time.time()

        try:
            self.logger.info(f"Starting Calibre conversion: {input_path.name} -> {output_path.name}")

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Build command
            cmd = self._build_conversion_command(input_path, output_path, options)

            # Execute conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CALIBRE_TIMEOUT
            )

            processing_time = time.time() - start_time

            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size

                self.logger.info(f"Calibre conversion successful: {processing_time:.2f}s, "
                               f"file size: {file_size:,} bytes")

                return CalibreResult(
                    success=True,
                    output_path=output_path,
                    error_message=None,
                    processing_time=processing_time,
                    command_used=' '.join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    file_size=file_size,
                    quality_indicators=self._analyze_calibre_output(result.stdout)
                )
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                self.logger.error(f"Calibre conversion failed: {error_msg}")

                return CalibreResult(
                    success=False,
                    output_path=None,
                    error_message=error_msg,
                    processing_time=processing_time,
                    command_used=' '.join(cmd),
                    stdout=result.stdout,
                    stderr=result.stderr
                )

        except subprocess.TimeoutExpired:
            processing_time = time.time() - start_time
            self.logger.error(f"Calibre conversion timed out after {CALIBRE_TIMEOUT} seconds")

            return CalibreResult(
                success=False,
                output_path=None,
                error_message=f"Conversion timed out after {CALIBRE_TIMEOUT} seconds",
                processing_time=processing_time,
                command_used=' '.join(cmd) if 'cmd' in locals() else "",
                stdout="",
                stderr="Timeout"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Calibre conversion exception: {str(e)}")

            return CalibreResult(
                success=False,
                output_path=None,
                error_message=str(e),
                processing_time=processing_time,
                command_used=' '.join(cmd) if 'cmd' in locals() else "",
                stdout="",
                stderr=str(e)
            )

    def _build_conversion_command(self,
                                 input_path: Path,
                                 output_path: Path,
                                 options: Dict[str, Any] = None) -> List[str]:
        """Build ebook-convert command with options"""
        cmd = ['ebook-convert', str(input_path), str(output_path)]

        # Add default options for better quality
        default_options = {
            '--pdf-engine': 'mupdf',  # Use MuPDF for better PDF handling
            '--enable-heuristics': '',  # Enable heuristic processing
            '--keep-ligatures': '',  # Preserve ligatures
            '--no-inline-toc': '',  # Generate separate TOC
            '--pretty-print': '',  # Format HTML nicely
            '--language': 'zh' if self._is_chinese_pdf(input_path) else 'en',
        }

        # Add custom options
        if options:
            default_options.update(options)

        # Add options to command
        for option, value in default_options.items():
            cmd.append(option)
            if value:  # Only add value if it's not empty
                cmd.append(str(value))

        return cmd

    def _is_chinese_pdf(self, pdf_path: Path) -> bool:
        """Simple heuristic to detect if PDF contains Chinese content"""
        try:
            # Read first few bytes to check for Chinese characters
            with open(pdf_path, 'rb') as f:
                sample = f.read(1000).decode('utf-8', errors='ignore')

            return any('\u4e00' <= char <= '\u9fff' for char in sample)
        except Exception:
            return False

    def _analyze_calibre_output(self, stdout: str) -> Dict[str, Any]:
        """Analyze Calibre output for quality indicators"""
        indicators = {
            'pages_processed': 0,
            'images_extracted': 0,
            'toc_generated': False,
            'metadata_found': False,
            'warnings_count': 0
        }

        lines = stdout.split('\n')
        for line in lines:
            line_lower = line.lower()

            if 'pages' in line_lower:
                try:
                    # Try to extract page count
                    import re
                    match = re.search(r'(\d+)\s+pages?', line_lower)
                    if match:
                        indicators['pages_processed'] = int(match.group(1))
                except Exception:
                    pass

            if 'image' in line_lower or 'extracting' in line_lower:
                indicators['images_extracted'] += 1

            if 'toc' in line_lower or 'table of contents' in line_lower:
                indicators['toc_generated'] = True

            if 'metadata' in line_lower:
                indicators['metadata_found'] = True

            if 'warning' in line_lower or 'warn' in line_lower:
                indicators['warnings_count'] += 1

        return indicators

    def compare_conversion_quality(self,
                                   custom_result: Path,
                                   calibre_result: CalibreResult) -> ConversionQualityMetrics:
        """
        Compare quality between custom and Calibre conversion results

        Args:
            custom_result: Path to custom EPUB
            calibre_result: CalibreResult object

        Returns:
            ConversionQualityMetrics with comparison results
        """
        if not calibre_result.success:
            return ConversionQualityMetrics(
                text_extraction_quality=0,
                structure_preservation=0,
                image_quality=0,
                metadata_completeness=0,
                overall_score=0,
                file_size_ratio=1.0
            )

        try:
            # Basic quality comparison based on file size and structure
            custom_size = custom_result.stat().st_size if custom_result.exists() else 0
            calibre_size = calibre_result.file_size

            # Calculate file size ratio
            file_size_ratio = calibre_size / custom_size if custom_size > 0 else 1.0

            # Simple scoring (this could be enhanced with actual EPUB analysis)
            text_score = 85  # Assume good text extraction
            structure_score = 80  # Assume decent structure
            image_score = 90 if calibre_result.quality_indicators['images_extracted'] > 0 else 50
            metadata_score = 90 if calibre_result.quality_indicators['metadata_found'] else 60

            # Calculate overall score
            overall_score = (text_score + structure_score + image_score + metadata_score) / 4

            return ConversionQualityMetrics(
                text_extraction_quality=text_score,
                structure_preservation=structure_score,
                image_quality=image_score,
                metadata_completeness=metadata_score,
                overall_score=overall_score,
                file_size_ratio=file_size_ratio
            )

        except Exception as e:
            self.logger.error(f"Quality comparison failed: {str(e)}")
            return ConversionQualityMetrics(
                text_extraction_quality=50,
                structure_preservation=50,
                image_quality=50,
                metadata_completeness=50,
                overall_score=50,
                file_size_ratio=1.0
            )

    def should_trigger_fallback(self,
                               custom_quality_score: float,
                               error_occurred: bool = False,
                               user_requested: bool = False,
                               pdf_complexity: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Determine if Calibre fallback should be triggered

        Args:
            custom_quality_score: Quality score from custom pipeline (0-100)
            error_occurred: True if custom pipeline failed
            user_requested: True if user explicitly requested Calibre
            pdf_complexity: PDF complexity analysis results

        Returns:
            Tuple of (should_trigger, reason)
        """
        if not self.is_available():
            return False, "Calibre not available"

        # User requested override
        if user_requested:
            return True, "User explicitly requested Calibre conversion"

        # Error in custom pipeline
        if error_occurred:
            return True, "Custom pipeline encountered unrecoverable error"

        # Quality below threshold
        if custom_quality_score < CALIBRE_QUALITY_THRESHOLD:
            return True, f"Custom quality score ({custom_quality_score:.1f}) below threshold ({CALIBRE_QUALITY_THRESHOLD})"

        # Complex PDF features
        if pdf_complexity:
            if pdf_complexity.get('is_encrypted', False):
                return True, "PDF is encrypted"
            if pdf_complexity.get('has_drm', False):
                return True, "PDF has DRM protection"
            if pdf_complexity.get('complex_layout', False):
                return True, "PDF has complex layout requiring specialized handling"

        return False, "Custom conversion quality acceptable"

    def get_fallback_statistics(self) -> Dict[str, Any]:
        """Get statistics about Calibre fallback usage"""
        return {
            'available': self.is_available(),
            'version': self.calibre_version,
            'enabled': ENABLE_CALIBRE_FALLBACK,
            'quality_threshold': CALIBRE_QUALITY_THRESHOLD,
            'timeout': CALIBRE_TIMEOUT,
            'command_path': shutil.which('ebook-convert') or 'Not found'
        }

    def test_conversion(self, test_pdf_path: Path) -> bool:
        """Test Calibre conversion with a sample file"""
        if not self.is_available() or not test_pdf_path.exists():
            return False

        try:
            test_output = test_pdf_path.parent / "test_calibre_output.epub"
            result = self.convert_pdf_to_epub(test_pdf_path, test_output)

            # Clean up test file
            if test_output.exists():
                test_output.unlink()

            return result.success

        except Exception as e:
            self.logger.error(f"Calibre test conversion failed: {str(e)}")
            return False

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get supported input and output formats from Calibre"""
        if not self.is_available():
            return {'input': [], 'output': []}

        try:
            result = subprocess.run(
                ['ebook-convert', '--list-formats'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse the output to extract formats
                lines = result.stdout.split('\n')
                input_formats = []
                output_formats = []

                for line in lines:
                    if 'input formats:' in line.lower():
                        # This is simplified - in practice you'd parse more carefully
                        input_formats = ['pdf', 'mobi', 'azw', 'azw3', 'txt', 'doc', 'docx']
                    elif 'output formats:' in line.lower():
                        output_formats = ['epub', 'mobi', 'azw3', 'pdf', 'txt']

                return {
                    'input': input_formats,
                    'output': output_formats
                }

        except Exception as e:
            self.logger.warning(f"Failed to get supported formats: {str(e)}")

        # Return default known formats
        return {
            'input': ['pdf', 'mobi', 'azw', 'azw3', 'txt', 'doc', 'docx', 'html', 'rtf'],
            'output': ['epub', 'mobi', 'azw3', 'pdf', 'txt', 'html', 'rtf']
        }