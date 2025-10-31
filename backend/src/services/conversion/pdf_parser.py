"""
PDF Parser Module - Advanced PDF parsing with PyMuPDF

This module provides high-quality PDF parsing capabilities including:
- Text extraction with position information
- Font and layout analysis
- Metadata extraction
- Image extraction
- Scan detection
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import fitz  # PyMuPDF
from utils.logging_config import get_logger


@dataclass
class TextBlock:
    """Represents a block of text with position and font information"""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_name: str
    font_size: float
    is_bold: bool
    page_num: int
    block_id: int


@dataclass
class PDFMetadata:
    """PDF document metadata"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    page_count: int = 0
    is_encrypted: bool = False
    has_bookmarks: bool = False
    scan_probability: float = 0.0


@dataclass
class ImageInfo:
    """Information about an extracted image"""
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
    width: int
    height: int
    image_format: str
    image_data: bytes
    is_color: bool


class PDFParser:
    """Advanced PDF parser using PyMuPDF for high-quality text and image extraction"""

    def __init__(self):
        self.logger = get_logger("pdf_parser")

    def parse_pdf(self, pdf_path: Path) -> Tuple[PDFMetadata, List[TextBlock], List[ImageInfo]]:
        """
        Parse PDF and extract metadata, text blocks, and images

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (metadata, text_blocks, images)

        Raises:
            ValueError: If PDF cannot be parsed
            IOError: If file cannot be read
        """
        try:
            doc = fitz.open(str(pdf_path))
            self.logger.info(f"Parsing PDF: {pdf_path.name}, pages: {len(doc)}")

            # Extract metadata
            metadata = self._extract_metadata(doc)

            # Extract text blocks from all pages
            text_blocks = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = self._extract_text_blocks(page, page_num)
                text_blocks.extend(blocks)

            # Extract images
            images = self._extract_images(doc)

            # Calculate scan probability
            metadata.scan_probability = self._calculate_scan_probability(text_blocks, len(doc))

            doc.close()

            self.logger.info(f"Parsing complete: {len(text_blocks)} text blocks, {len(images)} images")
            return metadata, text_blocks, images

        except Exception as e:
            self.logger.error(f"Failed to parse PDF {pdf_path}: {str(e)}")
            raise ValueError(f"PDF parsing failed: {str(e)}")

    def _extract_metadata(self, doc: fitz.Document) -> PDFMetadata:
        """Extract PDF metadata"""
        metadata_dict = doc.metadata or {}

        # Extract bookmarks/outline
        has_bookmarks = len(doc.get_toc()) > 0

        return PDFMetadata(
            title=metadata_dict.get('title'),
            author=metadata_dict.get('author'),
            subject=metadata_dict.get('subject'),
            creator=metadata_dict.get('creator'),
            producer=metadata_dict.get('producer'),
            page_count=len(doc),
            is_encrypted=doc.needs_pass,
            has_bookmarks=has_bookmarks
        )

    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> List[TextBlock]:
        """Extract text blocks from a page with font information"""
        text_blocks = []

        try:
            # Get text blocks with position information
            blocks = page.get_text("dict")

            for block in blocks.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                # Get font information
                                font_name = span.get("font", "")
                                font_size = span.get("size", 0)
                                is_bold = "bold" in font_name.lower()

                                # Get bounding box
                                bbox = span.get("bbox", [0, 0, 0, 0])

                                text_block = TextBlock(
                                    text=text,
                                    x0=bbox[0],
                                    y0=bbox[1],
                                    x1=bbox[2],
                                    y1=bbox[3],
                                    font_name=font_name,
                                    font_size=font_size,
                                    is_bold=is_bold,
                                    page_num=page_num,
                                    block_id=len(text_blocks)
                                )
                                text_blocks.append(text_block)

        except Exception as e:
            self.logger.warning(f"Error extracting text blocks from page {page_num}: {str(e)}")

        return text_blocks

    def _extract_images(self, doc: fitz.Document) -> List[ImageInfo]:
        """Extract all images from PDF"""
        images = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            try:
                # Get image list from page
                image_list = page.get_images(full=True)

                for img_index, img in enumerate(image_list):
                    try:
                        # Extract image
                        xref = img[0]
                        base_image = doc.extract_image(xref)

                        if base_image:
                            # Get image position
                            rect = page.get_image_bbox(img)

                            image_info = ImageInfo(
                                page_num=page_num,
                                x0=rect.x0,
                                y0=rect.y0,
                                x1=rect.x1,
                                y1=rect.y1,
                                width=base_image.get("width", 0),
                                height=base_image.get("height", 0),
                                image_format=base_image.get("ext", "png"),
                                image_data=base_image.get("image", b""),
                                is_color=base_image.get("colorspace", None) is not None
                            )
                            images.append(image_info)

                    except Exception as e:
                        self.logger.warning(f"Failed to extract image {img_index} from page {page_num}: {str(e)}")
                        continue

            except Exception as e:
                self.logger.warning(f"Error processing images on page {page_num}: {str(e)}")

        return images

    def _calculate_scan_probability(self, text_blocks: List[TextBlock], page_count: int) -> float:
        """
        Calculate probability that PDF is scanned based on text extraction results

        Returns:
            Float between 0.0 (definitely digital) and 1.0 (definitely scanned)
        """
        if page_count == 0:
            return 1.0

        # Calculate average text per page
        total_text_length = sum(len(block.text) for block in text_blocks)
        avg_text_per_page = total_text_length / page_count

        # If very little text extracted, likely scanned
        if avg_text_per_page < 50:
            return 0.9
        elif avg_text_per_page < 100:
            return 0.6
        elif avg_text_per_page < 200:
            return 0.3
        else:
            return 0.1

    def get_bookmarks(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract bookmark/outline structure from PDF"""
        try:
            toc = doc.get_toc()
            bookmarks = []

            for item in toc:
                level, title, page = item
                bookmarks.append({
                    'level': level,
                    'title': title,
                    'page': page,
                    'type': 'bookmark'
                })

            return bookmarks

        except Exception as e:
            self.logger.warning(f"Failed to extract bookmarks: {str(e)}")
            return []

    def render_page_as_image(self, pdf_path: Path, page_num: int, dpi: int = 200) -> Optional[bytes]:
        """
        Render a specific page as an image for OCR processing

        Args:
            pdf_path: Path to PDF file
            page_num: Page number to render (0-indexed)
            dpi: Resolution for rendering

        Returns:
            Image bytes as PNG, or None if rendering fails
        """
        try:
            doc = fitz.open(str(pdf_path))

            if page_num >= len(doc):
                doc.close()
                return None

            page = doc[page_num]

            # Set zoom level based on DPI
            zoom = dpi / 72.0  # Default PDF is 72 DPI
            matrix = fitz.Matrix(zoom, zoom)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")

            doc.close()
            return img_bytes

        except Exception as e:
            self.logger.error(f"Failed to render page {page_num} as image: {str(e)}")
            return None

    def validate_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Validate PDF file and return analysis

        Returns:
            Dictionary with validation results
        """
        try:
            doc = fitz.open(str(pdf_path))

            result = {
                'is_valid': True,
                'page_count': len(doc),
                'is_encrypted': doc.needs_pass,
                'has_bookmarks': len(doc.get_toc()) > 0,
                'file_size': pdf_path.stat().st_size,
                'version': getattr(doc, 'pdf_version', 'unknown')
            }

            # Quick text extraction test
            try:
                first_page = doc[0]
                text_sample = first_page.get_text()
                result['has_text'] = len(text_sample.strip()) > 10
            except:
                result['has_text'] = False

            doc.close()
            return result

        except Exception as e:
            return {
                'is_valid': False,
                'error': str(e)
            }