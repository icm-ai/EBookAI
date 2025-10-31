"""
Conversion Pipeline Module - Main orchestration for PDF to EPUB conversion

This module provides the main conversion pipeline that coordinates all components:
- 5-stage conversion process with quality checks
- Progress tracking and error handling
- Calibre fallback integration
- Quality assessment and comparison
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.logging_config import get_logger
from utils.progress_tracker import progress_tracker

# Import all conversion components
from pdf_parser import PDFParser, PDFMetadata
from layout_analyzer import LayoutAnalyzer
from ocr_service import OCRService
from chapter_detector import ChapterDetector
from image_processor import ImageProcessor, ProcessedImage
from epub_generator import EpubGenerator, EpubChapter, EpubMetadata
from calibre_fallback import CalibreFallback

# Import configuration
from config import (
    ENHANCED_PDF_CONVERSION,
    CONVERSION_QUALITY_LEVEL,
    OCR_CONFIDENCE_THRESHOLD,
    ENABLE_CALIBRE_FALLBACK,
    CALIBRE_QUALITY_THRESHOLD
)


@dataclass
class ConversionStage:
    """Represents a stage in the conversion pipeline"""
    name: str
    description: str
    progress_weight: float  # Weight for overall progress calculation
    completed: bool = False
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class ConversionResult:
    """Final result of the conversion process"""
    success: bool
    output_path: Optional[Path]
    error_message: Optional[str]
    total_duration: float
    quality_score: float
    method_used: str  # 'custom' or 'calibre'
    stages_completed: List[str]
    metadata: Dict[str, Any]


class ConversionPipeline:
    """Main conversion pipeline orchestrating all components"""

    def __init__(self, ai_service=None):
        self.logger = get_logger("conversion_pipeline")
        self.ai_service = ai_service

        # Initialize components
        self.pdf_parser = PDFParser()
        self.layout_analyzer = LayoutAnalyzer()
        self.ocr_service = OCRService()
        self.chapter_detector = ChapterDetector(ai_service)
        self.image_processor = ImageProcessor(ai_service)
        self.epub_generator = EpubGenerator()
        self.calibre_fallback = CalibreFallback()

        # Define pipeline stages
        self.stages = [
            ConversionStage("pdf_analysis", "Analyzing PDF structure", 0.1),
            ConversionStage("content_extraction", "Extracting text and images", 0.3),
            ConversionStage("structure_recognition", "Detecting chapters and layout", 0.2),
            ConversionStage("ai_enhancement", "Enhancing content with AI", 0.2),
            ConversionStage("epub_generation", "Generating EPUB", 0.2)
        ]

    def convert_pdf_to_epub(self,
                            input_path: Path,
                            output_path: Path,
                            quality_level: str = None,
                            use_calibre: bool = False) -> ConversionResult:
        """
        Convert PDF to EPUB using the enhanced pipeline

        Args:
            input_path: Path to input PDF file
            output_path: Path for output EPUB file
            quality_level: Conversion quality level (fast/standard/high)
            use_calibre: Force use of Calibre instead of custom pipeline

        Returns:
            ConversionResult with conversion details
        """
        if not ENHANCED_PDF_CONVERSION:
            # Fallback to old implementation if feature flag is disabled
            return self._fallback_to_old_implementation(input_path, output_path)

        start_time = time.time()
        task_id = output_path.stem

        try:
            self.logger.info(f"Starting enhanced PDF to EPUB conversion: {input_path.name}")
            progress_tracker.start_task(task_id, input_path.name, '.pdf', 'epub', 5)

            # Check if we should use Calibre directly
            if use_calibre or not self._is_custom_pipeline_suitable(input_path):
                return self._convert_with_calibre(input_path, output_path, task_id, start_time)

            # Run custom pipeline stages
            pipeline_result = self._run_custom_pipeline(input_path, output_path, quality_level, task_id)

            # Check if we need Calibre fallback
            if not pipeline_result.success or self._should_trigger_fallback(pipeline_result):
                self.logger.info("Triggering Calibre fallback")
                calibre_result = self._convert_with_calibre(input_path, output_path, task_id, start_time)

                if calibre_result.success:
                    return calibre_result
                elif pipeline_result.success:
                    # Fallback failed, return custom result
                    return pipeline_result
                else:
                    # Both failed
                    return self._create_failure_result("Both custom pipeline and Calibre failed", start_time)

            return pipeline_result

        except Exception as e:
            self.logger.error(f"Pipeline conversion failed: {str(e)}")
            return self._create_failure_result(str(e), start_time)

    def _run_custom_pipeline(self,
                            input_path: Path,
                            output_path: Path,
                            quality_level: str,
                            task_id: str) -> ConversionResult:
        """Run the custom conversion pipeline"""
        start_time = time.time()
        completed_stages = []

        # Stage 1: PDF Analysis
        metadata, text_blocks, images = self._stage_1_pdf_analysis(input_path, task_id)
        if metadata is None:
            return self._create_failure_result("PDF analysis failed", start_time)
        completed_stages.append("pdf_analysis")

        # Stage 2: Content Extraction
        extracted_text, processed_images = self._stage_2_content_extraction(
            input_path, text_blocks, images, quality_level, task_id
        )
        completed_stages.append("content_extraction")

        # Stage 3: Structure Recognition
        chapter_structure = self._stage_3_structure_recognition(text_blocks, metadata, task_id)
        completed_stages.append("structure_recognition")

        # Stage 4: AI Enhancement
        enhanced_metadata, enhanced_chapters = self._stage_4_ai_enhancement(
            extracted_text, chapter_structure, metadata, task_id
        )
        completed_stages.append("ai_enhancement")

        # Stage 5: EPUB Generation
        success = self._stage_5_epub_generation(
            output_path, enhanced_chapters, enhanced_metadata, processed_images, task_id
        )
        if not success:
            return self._create_failure_result("EPUB generation failed", start_time)
        completed_stages.append("epub_generation")

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            metadata, chapter_structure, processed_images, enhanced_metadata
        )

        total_duration = time.time() - start_time
        progress_tracker.complete_task(task_id, output_path.name)

        return ConversionResult(
            success=True,
            output_path=output_path,
            error_message=None,
            total_duration=total_duration,
            quality_score=quality_score,
            method_used='custom',
            stages_completed=completed_stages,
            metadata={
                'quality_level': quality_level,
                'pages_processed': metadata.page_count,
                'chapters_detected': len(chapter_structure.chapters),
                'images_processed': len(processed_images),
                'has_bookmarks': metadata.has_bookmarks,
                'scan_probability': metadata.scan_probability
            }
        )

    def _stage_1_pdf_analysis(self, input_path: Path, task_id: str) -> Tuple[Optional[PDFMetadata], List, List]:
        """Stage 1: Analyze PDF structure and extract basic information"""
        try:
            progress_tracker.update_progress(task_id, 1, "Analyzing PDF structure...")

            # Parse PDF
            metadata, text_blocks, images = self.pdf_parser.parse_pdf(input_path)

            # Log analysis results
            self.logger.info(f"PDF Analysis: {metadata.page_count} pages, "
                           f"{len(text_blocks)} text blocks, {len(images)} images")
            self.logger.info(f"Scan probability: {metadata.scan_probability:.2f}")

            return metadata, text_blocks, images

        except Exception as e:
            self.logger.error(f"PDF analysis failed: {str(e)}")
            progress_tracker.fail_task(task_id, f"PDF analysis failed: {str(e)}")
            return None, [], []

    def _stage_2_content_extraction(self,
                                  input_path: Path,
                                  text_blocks: List,
                                  images: List,
                                  quality_level: str,
                                  task_id: str) -> Tuple[str, List[ProcessedImage]]:
        """Stage 2: Extract and process content including OCR if needed"""
        try:
            progress_tracker.update_progress(task_id, 2, "Extracting content...")

            # Determine if OCR is needed
            ocr_needed = self._determine_ocr_need(text_blocks)

            extracted_text = " ".join(block.text for block in text_blocks)

            # Apply OCR if needed
            if ocr_needed:
                progress_tracker.update_progress(task_id, 2, "Applying OCR for scanned content...")
                ocr_results = self.ocr_service.process_document(input_path)

                # Combine OCR results with existing text
                ocr_text = " ".join(result.result.text for result in ocr_results)
                if ocr_text and len(ocr_text) > len(extracted_text):
                    extracted_text = ocr_text
                    self.logger.info("Used OCR text due to better extraction")

            # Process images
            processed_images = self.image_processor.process_images(images, text_blocks, quality_level)

            return extracted_text, processed_images

        except Exception as e:
            self.logger.error(f"Content extraction failed: {str(e)}")
            progress_tracker.fail_task(task_id, f"Content extraction failed: {str(e)}")
            return "", []

    def _stage_3_structure_recognition(self,
                                    text_blocks: List,
                                    metadata: PDFMetadata,
                                    task_id: str) -> Any:
        """Stage 3: Recognize document structure and chapters"""
        try:
            progress_tracker.update_progress(task_id, 3, "Detecting document structure...")

            # Use chapter detector to find structure
            # Note: This would need the actual PDF document object
            # For now, return a simple structure
            chapter_structure = self.chapter_detector.detect_chapters(None, text_blocks, metadata.__dict__)

            self.logger.info(f"Structure recognition: {len(chapter_structure.chapters)} chapters detected")
            return chapter_structure

        except Exception as e:
            self.logger.error(f"Structure recognition failed: {str(e)}")
            progress_tracker.fail_task(task_id, f"Structure recognition failed: {str(e)}")
            return None

    def _stage_4_ai_enhancement(self,
                              extracted_text: str,
                              chapter_structure: Any,
                              metadata: PDFMetadata,
                              task_id: str) -> Tuple[EpubMetadata, List[EpubChapter]]:
        """Stage 4: Enhance content using AI"""
        try:
            progress_tracker.update_progress(task_id, 4, "Enhancing content with AI...")

            # Generate metadata
            epub_metadata = self.epub_generator.generate_metadata(metadata.__dict__)

            # Create chapters
            if chapter_structure and hasattr(chapter_structure, 'chapters'):
                chapters = self.epub_generator.create_chapters_from_text_blocks(
                    [], chapter_structure.chapters, metadata.__dict__
                )
            else:
                # Create single chapter if no structure detected
                chapters = [EpubChapter(
                    chapter_id="chapter_001",
                    title=metadata.title or "Document",
                    content=extracted_text,
                    file_name="chapter_001.xhtml",
                    level=1,
                    page_num=0,
                    images=[]
                )]

            return epub_metadata, chapters

        except Exception as e:
            self.logger.error(f"AI enhancement failed: {str(e)}")
            progress_tracker.fail_task(task_id, f"AI enhancement failed: {str(e)}")
            return None, []

    def _stage_5_epub_generation(self,
                               output_path: Path,
                               chapters: List[EpubChapter],
                               metadata: EpubMetadata,
                               images: List[ProcessedImage],
                               task_id: str) -> bool:
        """Stage 5: Generate final EPUB"""
        try:
            progress_tracker.update_progress(task_id, 4, "Generating EPUB...")

            # Convert images to bytes dictionary
            image_bytes = {img.image_id: img.processed_data for img in images}

            # Generate EPUB
            success = self.epub_generator.generate_epub(
                output_path, chapters, metadata, image_bytes
            )

            if success:
                progress_tracker.update_progress(task_id, 5, "EPUB generation completed", 100)
                self.logger.info(f"EPUB generated successfully: {output_path}")

            return success

        except Exception as e:
            self.logger.error(f"EPUB generation failed: {str(e)}")
            progress_tracker.fail_task(task_id, f"EPUB generation failed: {str(e)}")
            return False

    def _convert_with_calibre(self,
                             input_path: Path,
                             output_path: Path,
                             task_id: str,
                             start_time: float) -> ConversionResult:
        """Convert using Calibre fallback"""
        try:
            self.logger.info("Using Calibre fallback conversion")
            progress_tracker.update_progress(task_id, 1, "Using Calibre fallback...")

            calibre_result = self.calibre_fallback.convert_pdf_to_epub(input_path, output_path)

            if calibre_result.success:
                total_duration = time.time() - start_time
                progress_tracker.complete_task(task_id, output_path.name)

                return ConversionResult(
                    success=True,
                    output_path=output_path,
                    error_message=None,
                    total_duration=total_duration,
                    quality_score=75.0,  # Moderate quality score for Calibre
                    method_used='calibre',
                    stages_completed=['calibre_fallback'],
                    metadata={
                        'processing_time': calibre_result.processing_time,
                        'file_size': calibre_result.file_size,
                        'quality_indicators': calibre_result.quality_indicators
                    }
                )
            else:
                return self._create_failure_result(f"Calibre conversion failed: {calibre_result.error_message}", start_time)

        except Exception as e:
            self.logger.error(f"Calibre conversion failed: {str(e)}")
            return self._create_failure_result(f"Calibre conversion exception: {str(e)}", start_time)

    def _determine_ocr_need(self, text_blocks: List) -> bool:
        """Determine if OCR is needed based on text extraction results"""
        if not text_blocks:
            return True

        total_text = sum(len(block.text) for block in text_blocks)
        avg_text_per_block = total_text / len(text_blocks)

        # If very little text extracted, likely need OCR
        return avg_text_per_block < 50

    def _calculate_quality_score(self,
                               metadata: PDFMetadata,
                               chapter_structure: Any,
                               images: List[ProcessedImage],
                               enhanced_metadata: EpubMetadata) -> float:
        """Calculate overall quality score for the conversion"""
        score = 50.0  # Base score

        # Metadata quality
        if metadata.title and metadata.author:
            score += 10
        if metadata.has_bookmarks:
            score += 15

        # Chapter detection quality
        if chapter_structure and hasattr(chapter_structure, 'total_confidence'):
            score += chapter_structure.total_confidence * 0.2

        # Image processing quality
        if images:
            score += min(len(images) * 2, 15)  # Up to 15 points for images

        # Text extraction quality
        if metadata.scan_probability < 0.3:  # Low scan probability = good text extraction
            score += 10
        elif metadata.scan_probability < 0.7:
            score += 5

        return min(100.0, score)

    def _should_trigger_fallback(self, result: ConversionResult) -> bool:
        """Determine if Calibre fallback should be triggered"""
        if result.error_message:
            return True

        if result.quality_score < CALIBRE_QUALITY_THRESHOLD:
            return True

        return False

    def _is_custom_pipeline_suitable(self, input_path: Path) -> bool:
        """Check if custom pipeline is suitable for this PDF"""
        try:
            # Quick validation
            validation = self.pdf_parser.validate_pdf(input_path)
            if not validation.get('is_valid', False):
                return False

            # Check if PDF is encrypted
            if validation.get('is_encrypted', False):
                return False

            return True

        except Exception:
            return False

    def _fallback_to_old_implementation(self, input_path: Path, output_path: Path) -> ConversionResult:
        """Fallback to old implementation when enhanced conversion is disabled"""
        self.logger.warning("Enhanced conversion disabled, using old implementation")

        try:
            # Import and use old conversion service
            from conversion_service import ConversionService
            old_service = ConversionService()

            start_time = time.time()
            result = old_service.convert_file(str(input_path), "epub")
            total_duration = time.time() - start_time

            if result.get('status') == 'completed':
                return ConversionResult(
                    success=True,
                    output_path=output_path,
                    error_message=None,
                    total_duration=total_duration,
                    quality_score=60.0,  # Moderate score for old implementation
                    method_used='legacy',
                    stages_completed=['legacy_conversion'],
                    metadata={'legacy_mode': True}
                )
            else:
                return self._create_failure_result(result.get('message', 'Unknown error'), start_time)

        except Exception as e:
            return self._create_failure_result(f"Legacy conversion failed: {str(e)}", time.time())

    def _create_failure_result(self, error_message: str, start_time: float) -> ConversionResult:
        """Create a failure result"""
        return ConversionResult(
            success=False,
            output_path=None,
            error_message=error_message,
            total_duration=time.time() - start_time,
            quality_score=0.0,
            method_used='failed',
            stages_completed=[],
            metadata={'error': error_message}
        )

    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get statistics about the pipeline and its components"""
        return {
            'enhanced_conversion_enabled': ENHANCED_PDF_CONVERSION,
            'calibre_fallback_enabled': ENABLE_CALIBRE_FALLBACK,
            'ocr_service_available': self.ocr_service.is_available(),
            'calibre_available': self.calibre_fallback.is_available(),
            'quality_level': CONVERSION_QUALITY_LEVEL,
            'ocr_confidence_threshold': OCR_CONFIDENCE_THRESHOLD,
            'calibre_quality_threshold': CALIBRE_QUALITY_THRESHOLD,
            'pipeline_stages': [stage.name for stage in self.stages]
        }