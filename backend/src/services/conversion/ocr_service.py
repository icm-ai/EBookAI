"""
OCR Service Module - Optical Character Recognition using Tesseract

This module provides OCR capabilities for scanned PDF documents including:
- Language detection (Chinese/English)
- Image preprocessing for better OCR accuracy
- Confidence scoring
- Text extraction from scanned pages
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from utils.logging_config import get_logger

# Import configuration
from config import OCR_CONFIDENCE_THRESHOLD, TESSERACT_LANGUAGE_MODELS


@dataclass
class OCRResult:
    """Result of OCR processing for a page"""
    text: str
    confidence: float
    language: str
    word_confidences: List[Tuple[str, float]]
    preprocessing_applied: List[str]
    processing_time: float


@dataclass
class PageOCRResult:
    """OCR result for a specific page"""
    page_num: int
    result: OCRResult
    image_size: Tuple[int, int]
    dpi: int
    warnings: List[str]


class OCRService:
    """OCR service using Tesseract for scanned document processing"""

    def __init__(self):
        self.logger = get_logger("ocr_service")
        self.supported_languages = self._parse_language_models(TESSERACT_LANGUAGE_MODELS)

        # Verify Tesseract is available
        try:
            pytesseract.get_tesseract_version()
            self.logger.info(f"Tesseract version: {pytesseract.get_tesseract_version()}")
        except Exception as e:
            self.logger.error(f"Tesseract not available: {str(e)}")
            raise RuntimeError("Tesseract OCR engine not found")

    def _parse_language_models(self, language_models: str) -> List[str]:
        """Parse language models string into list"""
        return [lang.strip() for lang in language_models.split(',') if lang.strip()]

    def process_page_image(self, image_bytes: bytes, page_num: int = 0, dpi: int = 200) -> PageOCRResult:
        """
        Process a page image and extract text using OCR

        Args:
            image_bytes: Image data as bytes
            page_num: Page number for reference
            dpi: Resolution of the image

        Returns:
            PageOCRResult with extracted text and metadata
        """
        try:
            self.logger.debug(f"Processing OCR for page {page_num}")

            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_bytes))

            # Preprocess image for better OCR
            processed_image, preprocessing_steps = self._preprocess_image(image)

            # Detect language
            detected_language = self._detect_language(processed_image)

            # Perform OCR
            start_time = time.time()
            ocr_result = self._perform_ocr(processed_image, detected_language)
            processing_time = time.time() - start_time

            # Create result
            page_result = PageOCRResult(
                page_num=page_num,
                result=ocr_result,
                image_size=image.size,
                dpi=dpi,
                warnings=[]
            )

            # Add warnings if confidence is low
            if ocr_result.confidence < OCR_CONFIDENCE_THRESHOLD:
                page_result.warnings.append(
                    f"Low OCR confidence ({ocr_result.confidence:.1f}% < {OCR_CONFIDENCE_THRESHOLD}%)"
                )

            self.logger.debug(f"Page {page_num} OCR complete: {len(ocr_result.text)} chars, "
                             f"confidence: {ocr_result.confidence:.1f}%")

            return page_result

        except Exception as e:
            self.logger.error(f"OCR processing failed for page {page_num}: {str(e)}")
            raise RuntimeError(f"OCR processing failed: {str(e)}")

    def _preprocess_image(self, image: Image.Image) -> Tuple[Image.Image, List[str]]:
        """
        Apply image preprocessing to improve OCR accuracy

        Args:
            image: PIL Image object

        Returns:
            Tuple of (processed_image, applied_steps)
        """
        applied_steps = []
        processed_image = image.convert('RGB')  # Ensure RGB mode

        try:
            # Check if image needs deskewing
            if self._needs_deskewing(processed_image):
                processed_image = self._deskew_image(processed_image)
                applied_steps.append("deskew")

            # Enhance contrast
            if self._needs_contrast_enhancement(processed_image):
                enhancer = ImageEnhance.Contrast(processed_image)
                processed_image = enhancer.enhance(1.5)
                applied_steps.append("contrast_enhance")

            # Convert to grayscale for better OCR
            processed_image = processed_image.convert('L')

            # Apply thresholding (binarization)
            processed_image = self._apply_threshold(processed_image)
            applied_steps.append("threshold")

            # Denoise
            processed_image = processed_image.filter(ImageFilter.MedianFilter(size=3))
            applied_steps.append("denoise")

        except Exception as e:
            self.logger.warning(f"Image preprocessing failed: {str(e)}")
            # Return original image if preprocessing fails
            processed_image = image.convert('RGB')

        return processed_image, applied_steps

    def _needs_deskewing(self, image: Image.Image) -> bool:
        """Check if image needs deskewing"""
        # Simple heuristic: if image width > height, might need deskewing
        return image.width > image.height * 1.5

    def _deskew_image(self, image: Image.Image) -> Image.Image:
        """Deskew image (simplified implementation)"""
        # This is a simplified deskewing - in production, you might want to use
        # more sophisticated algorithms like those in OpenCV
        try:
            # For now, just return the original image
            # In a real implementation, you would:
            # 1. Detect text lines
            # 2. Calculate skew angle
            # 3. Rotate image to correct skew
            return image
        except Exception:
            return image

    def _needs_contrast_enhancement(self, image: Image.Image) -> bool:
        """Check if image needs contrast enhancement"""
        try:
            # Calculate histogram to determine if contrast is low
            histogram = image.histogram()
            # Simple check: if most pixels are in a narrow range, enhance contrast
            total_pixels = sum(histogram)
            middle_range = sum(histogram[100:155])  # Middle part of histogram

            return (middle_range / total_pixels) > 0.7
        except Exception:
            return False

    def _apply_threshold(self, image: Image.Image) -> Image.Image:
        """Apply thresholding to binarize image"""
        try:
            # Convert to grayscale if not already
            if image.mode != 'L':
                image = image.convert('L')

            # Apply adaptive threshold
            threshold = 128
            return image.point(lambda x: 0 if x < threshold else 255, '1')
        except Exception:
            return image

    def _detect_language(self, image: Image.Image) -> str:
        """
        Detect the primary language in the image

        Returns:
            Language code (e.g., 'chi_sim', 'eng')
        """
        try:
            # Quick OCR for language detection
            config = '--psm 6'  # Assume uniform block of text

            # Try Chinese first
            try:
                chinese_result = pytesseract.image_to_string(
                    image, lang='chi_sim+chi_tra', config=config
                )
                chinese_text = re.sub(r'[^\u4e00-\u9fff]', '', chinese_result)
                if len(chinese_text) > 10:
                    return 'chi_sim+chi_tra'
            except Exception:
                pass

            # Fallback to English
            return 'eng'

        except Exception as e:
            self.logger.warning(f"Language detection failed: {str(e)}")
            return 'eng'  # Default to English

    def _perform_ocr(self, image: Image.Image, language: str) -> OCRResult:
        """
        Perform OCR on the processed image

        Args:
            image: Preprocessed PIL Image
            language: Language code for OCR

        Returns:
            OCRResult with text and confidence scores
        """
        try:
            # Configure Tesseract
            config = '--psm 6 --oem 3'  # Assume uniform text, default OCR engine

            # Get word-level data with confidence
            data = pytesseract.image_to_data(
                image, lang=language, config=config, output_type=pytesseract.Output.DICT
            )

            # Extract text and confidences
            text_parts = []
            word_confidences = []
            total_confidence = 0
            word_count = 0

            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                if word:
                    conf = int(data['conf'][i])
                    text_parts.append(word)
                    word_confidences.append((word, conf))
                    total_confidence += conf
                    word_count += 1

            # Calculate overall confidence
            overall_confidence = (total_confidence / word_count) if word_count > 0 else 0

            # Combine text
            full_text = ' '.join(text_parts)

            return OCRResult(
                text=full_text,
                confidence=overall_confidence,
                language=language,
                word_confidences=word_confidences,
                preprocessing_applied=[],  # Will be set by caller
                processing_time=0  # Will be set by caller
            )

        except Exception as e:
            self.logger.error(f"OCR processing failed: {str(e)}")
            raise RuntimeError(f"OCR processing failed: {str(e)}")

    def process_document(self, pdf_path: Path, page_range: Optional[Tuple[int, int]] = None) -> List[PageOCRResult]:
        """
        Process an entire PDF document using OCR

        Args:
            pdf_path: Path to PDF file
            page_range: Optional tuple (start_page, end_page) to process specific pages

        Returns:
            List of PageOCRResult objects
        """
        try:
            self.logger.info(f"Starting OCR processing for {pdf_path.name}")

            # Import here to avoid circular imports
            from pdf_parser import PDFParser

            pdf_parser = PDFParser()
            results = []

            # Validate PDF first
            validation = pdf_parser.validate_pdf(pdf_path)
            if not validation['is_valid']:
                raise ValueError(f"Invalid PDF file: {validation.get('error', 'Unknown error')}")

            # Determine page range
            total_pages = validation['page_count']
            if page_range:
                start_page, end_page = page_range
                start_page = max(0, start_page)
                end_page = min(total_pages - 1, end_page)
            else:
                start_page, end_page = 0, total_pages - 1

            # Process each page
            for page_num in range(start_page, end_page + 1):
                try:
                    # Render page as image
                    image_bytes = pdf_parser.render_page_as_image(pdf_path, page_num, dpi=300)

                    if image_bytes:
                        page_result = self.process_page_image(image_bytes, page_num, dpi=300)
                        results.append(page_result)
                    else:
                        self.logger.warning(f"Failed to render page {page_num} as image")

                except Exception as e:
                    self.logger.error(f"Failed to process page {page_num}: {str(e)}")
                    # Continue with other pages
                    continue

            self.logger.info(f"OCR processing complete: {len(results)} pages processed")
            return results

        except Exception as e:
            self.logger.error(f"Document OCR processing failed: {str(e)}")
            raise RuntimeError(f"Document OCR processing failed: {str(e)}")

    def is_available(self) -> bool:
        """Check if OCR service is available"""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return self.supported_languages.copy()

    def extract_text_with_layout(self, image: Image.Image, language: str = None) -> Dict[str, Any]:
        """
        Extract text while preserving layout information

        Args:
            image: PIL Image object
            language: Optional language override

        Returns:
            Dictionary with text and layout information
        """
        try:
            if not language:
                language = self._detect_language(image)

            # Use hOCR output to preserve layout
            hocr = pytesseract.image_to_pdf_or_hocr(
                image, lang=language, extension='hocr', config='--psm 6'
            )

            # Also get regular text for comparison
            text = pytesseract.image_to_string(image, lang=language, config='--psm 6')

            return {
                'text': text,
                'hocr': hocr,
                'language': language,
                'has_layout': True
            }

        except Exception as e:
            self.logger.error(f"Layout-aware OCR failed: {str(e)}")
            # Fallback to regular OCR
            text = pytesseract.image_to_string(image, lang=language or 'eng')
            return {
                'text': text,
                'hocr': None,
                'language': language or 'eng',
                'has_layout': False
            }


# Import required modules
import io
import time