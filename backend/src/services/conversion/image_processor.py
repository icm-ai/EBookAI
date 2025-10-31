"""
Image Processor Module - Advanced image extraction and optimization

This module provides comprehensive image processing capabilities:
- Image extraction from PDF with format detection
- Size optimization for different quality levels
- Format conversion (JPEG/PNG optimization)
- Image-text association analysis
- Alt text generation for accessibility
"""

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

from PIL import Image, ImageFilter, ImageEnhance
from utils.logging_config import get_logger

# Import configuration
from config import (
    IMAGE_MAX_WIDTH_FAST,
    IMAGE_MAX_WIDTH_STANDARD,
    IMAGE_MAX_WIDTH_HIGH,
    CONVERSION_QUALITY_LEVEL
)


@dataclass
class ProcessedImage:
    """Represents a processed image ready for EPUB embedding"""
    image_id: str
    original_data: bytes
    processed_data: bytes
    original_format: str
    final_format: str
    original_size: Tuple[int, int]
    final_size: Tuple[int, int]
    original_file_size: int
    final_file_size: int
    compression_ratio: float
    position_info: Dict[str, Any]
    alt_text: Optional[str] = None
    associated_text: Optional[str] = None
    quality_level: str = "standard"


@dataclass
class ImageAssociation:
    """Information about how an image relates to surrounding text"""
    image_id: str
    nearest_text_blocks: List[str]
    position_in_text: str  # 'before', 'after', 'between'
    contextual_relevance: float
    suggested_caption: Optional[str] = None


class ImageProcessor:
    """Advanced image processor for PDF to EPUB conversion"""

    def __init__(self, ai_service=None):
        self.logger = get_logger("image_processor")
        self.ai_service = ai_service
        self.processed_images = {}
        self.image_counter = 0

    def process_images(self, pdf_images: List, text_blocks: List, quality_level: str = None) -> List[ProcessedImage]:
        """
        Process and optimize all images from PDF

        Args:
            pdf_images: List of image information from PDF parser
            text_blocks: List of text blocks for association analysis
            quality_level: Image quality level (fast/standard/high)

        Returns:
            List of processed images
        """
        if quality_level is None:
            quality_level = CONVERSION_QUALITY_LEVEL

        try:
            self.logger.info(f"Processing {len(pdf_images)} images with quality level: {quality_level}")

            processed_images = []

            for pdf_image in pdf_images:
                try:
                    processed_image = self._process_single_image(pdf_image, quality_level)
                    processed_images.append(processed_image)

                    # Store for reference
                    self.processed_images[processed_image.image_id] = processed_image

                except Exception as e:
                    self.logger.warning(f"Failed to process image: {str(e)}")
                    continue

            # Analyze image-text associations
            if processed_images and text_blocks:
                self._analyze_text_associations(processed_images, text_blocks)

            # Generate alt text using AI if available
            if self.ai_service:
                self._generate_alt_text(processed_images)

            self.logger.info(f"Image processing complete: {len(processed_images)} images processed")
            return processed_images

        except Exception as e:
            self.logger.error(f"Image processing failed: {str(e)}")
            return []

    def _process_single_image(self, pdf_image, quality_level: str) -> ProcessedImage:
        """Process a single image with optimization"""
        self.image_counter += 1
        image_id = f"img_{self.image_counter:04d}"

        try:
            # Convert image data to PIL Image
            original_image = Image.open(io.BytesIO(pdf_image.image_data))

            # Get original information
            original_format = pdf_image.image_format.lower()
            original_size = original_image.size
            original_file_size = len(pdf_image.image_data)

            # Determine optimal format and size
            target_width = self._get_target_width(quality_level)
            optimal_format = self._determine_optimal_format(original_image, original_format)

            # Process image (resize, optimize)
            processed_image = self._resize_and_optimize(original_image, target_width, quality_level)

            # Convert to target format
            final_data = self._convert_to_format(processed_image, optimal_format, quality_level)

            # Calculate compression metrics
            final_size = processed_image.size
            final_file_size = len(final_data)
            compression_ratio = final_file_size / original_file_size if original_file_size > 0 else 1.0

            # Create position info
            position_info = {
                'page_num': pdf_image.page_num,
                'x0': pdf_image.x0,
                'y0': pdf_image.y0,
                'x1': pdf_image.x1,
                'y1': pdf_image.y1,
                'width': pdf_image.width,
                'height': pdf_image.height,
                'is_color': pdf_image.is_color
            }

            return ProcessedImage(
                image_id=image_id,
                original_data=pdf_image.image_data,
                processed_data=final_data,
                original_format=original_format,
                final_format=optimal_format,
                original_size=original_size,
                final_size=final_size,
                original_file_size=original_file_size,
                final_file_size=final_file_size,
                compression_ratio=compression_ratio,
                position_info=position_info,
                quality_level=quality_level
            )

        except Exception as e:
            self.logger.error(f"Failed to process image {image_id}: {str(e)}")
            raise

    def _get_target_width(self, quality_level: str) -> int:
        """Get target width based on quality level"""
        width_map = {
            'fast': IMAGE_MAX_WIDTH_FAST,
            'standard': IMAGE_MAX_WIDTH_STANDARD,
            'high': IMAGE_MAX_WIDTH_HIGH
        }
        return width_map.get(quality_level, IMAGE_MAX_WIDTH_STANDARD)

    def _determine_optimal_format(self, image: Image.Image, original_format: str) -> str:
        """Determine optimal output format for the image"""
        # If original is PNG with transparency, keep PNG
        if original_format == 'png' and image.mode in ('RGBA', 'LA'):
            return 'png'

        # For photographs and complex images, use JPEG
        if self._is_photograph(image):
            return 'jpeg'

        # For diagrams, charts, and simple graphics, use PNG
        if self._is_diagram(image):
            return 'png'

        # Default to JPEG for better compression
        return 'jpeg'

    def _is_photograph(self, image: Image.Image) -> bool:
        """Determine if image is a photograph"""
        # Simple heuristic based on size and color complexity
        if image.mode not in ('RGB', 'RGBA'):
            return False

        width, height = image.size

        # Large images are likely photographs
        if width > 500 or height > 500:
            return True

        # Check color diversity
        try:
            colors = image.getcolors(maxcolors=256)
            if colors and len(colors) > 100:
                return True
        except Exception:
            pass

        return False

    def _is_diagram(self, image: Image.Image) -> bool:
        """Determine if image is a diagram or chart"""
        # Simple heuristic based on size and color characteristics
        width, height = image.size

        # Small to medium images are likely diagrams
        if width <= 500 and height <= 500:
            return True

        # Limited color palette suggests diagram
        try:
            colors = image.getcolors(maxcolors=256)
            if colors and len(colors) <= 16:
                return True
        except Exception:
            pass

        return False

    def _resize_and_optimize(self, image: Image.Image, target_width: int, quality_level: str) -> Image.Image:
        """Resize and optimize image"""
        # Calculate new dimensions maintaining aspect ratio
        width, height = image.size
        if width > target_width:
            ratio = target_width / width
            new_width = target_width
            new_height = int(height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Apply quality-specific optimizations
        if quality_level == 'high':
            # High quality: minimal processing
            pass
        elif quality_level == 'standard':
            # Standard: mild sharpening
            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
        else:  # fast
            # Fast: aggressive optimization
            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=5))

        # Ensure RGB mode for JPEG
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background

        return image

    def _convert_to_format(self, image: Image.Image, target_format: str, quality_level: str) -> bytes:
        """Convert image to target format and return bytes"""
        buffer = io.BytesIO()

        if target_format.lower() == 'jpeg':
            # JPEG settings based on quality level
            quality_map = {
                'fast': 70,
                'standard': 85,
                'high': 95
            }
            quality = quality_map.get(quality_level, 85)

            image.save(buffer, format='JPEG', quality=quality, optimize=True)
        else:  # PNG
            # PNG settings based on quality level
            if quality_level == 'fast':
                # Fast: lower compression
                image.save(buffer, format='PNG', optimize=False, compress_level=3)
            elif quality_level == 'standard':
                # Standard: balanced compression
                image.save(buffer, format='PNG', optimize=True, compress_level=6)
            else:  # high
                # High: maximum compression
                image.save(buffer, format='PNG', optimize=True, compress_level=9)

        buffer.seek(0)
        return buffer.getvalue()

    def _analyze_text_associations(self, processed_images: List[ProcessedImage], text_blocks: List):
        """Analyze how images relate to surrounding text"""
        for image in processed_images:
            associations = self._find_nearest_text_blocks(image, text_blocks)

            if associations:
                # Store association information
                image.associated_text = ' '.join(associations['nearest_text_blocks'])

                # Generate suggested caption
                if associations['nearest_text_blocks']:
                    image.position_info['suggested_caption'] = associations['nearest_text_blocks'][0][:100]

    def _find_nearest_text_blocks(self, image: ProcessedImage, text_blocks: List) -> Dict[str, Any]:
        """Find text blocks nearest to an image"""
        if not text_blocks:
            return {}

        # Get image position
        img_page = image.position_info['page_num']
        img_y0 = image.position_info['y0']
        img_x0 = image.position_info['x0']

        # Find text blocks on the same or nearby pages
        nearby_blocks = []
        for block in text_blocks:
            if abs(block.page_num - img_page) <= 1:  # Same page or adjacent pages
                nearby_blocks.append(block)

        if not nearby_blocks:
            return {}

        # Calculate distances and sort by proximity
        blocks_with_distance = []
        for block in nearby_blocks:
            # Simple distance calculation
            if block.page_num == img_page:
                # Same page - calculate actual distance
                distance = abs(block.y0 - img_y0) + abs(block.x0 - img_x0)
            else:
                # Different page - large distance
                distance = 1000 + abs(block.page_num - img_page) * 100

            blocks_with_distance.append((distance, block))

        blocks_with_distance.sort(key=lambda x: x[0])

        # Get nearest blocks
        nearest_blocks = [block.text for distance, block in blocks_with_distance[:3]]

        # Determine position relative to text
        if blocks_with_distance:
            nearest_block = blocks_with_distance[0][1]
            if nearest_block.y0 < img_y0:
                position = 'after'
            else:
                position = 'before'
        else:
            position = 'unknown'

        return {
            'nearest_text_blocks': nearest_blocks,
            'position_in_text': position,
            'contextual_relevance': 0.8  # Simple relevance score
        }

    def _generate_alt_text(self, processed_images: List[ProcessedImage]):
        """Generate alt text for images using AI"""
        if not self.ai_service:
            return

        for image in processed_images:
            try:
                # Prepare image for AI analysis
                image_for_ai = Image.open(io.BytesIO(image.processed_data))

                # Resize for AI processing (smaller for efficiency)
                max_size = (512, 512)
                image_for_ai.thumbnail(max_size, Image.Resampling.LANCZOS)

                # Convert to bytes
                buffer = io.BytesIO()
                image_for_ai.save(buffer, format='JPEG', quality=85)
                image_bytes = buffer.getvalue()

                # Prepare prompt for AI
                prompt = f"""
                Describe this image in detail for accessibility purposes.
                Focus on what's important for understanding the content.
                Keep the description concise but informative.

                Context: This image appears in a document about {image.associated_text or 'various topics'}.
                """

                # Call AI service (implementation depends on your AI service interface)
                try:
                    alt_text = self.ai_service.analyze_image(image_bytes, prompt)
                    image.alt_text = alt_text.strip() if alt_text else None
                except Exception as e:
                    self.logger.warning(f"AI alt text generation failed for {image.image_id}: {str(e)}")

            except Exception as e:
                self.logger.warning(f"Failed to generate alt text for {image.image_id}: {str(e)}")

    def get_image_statistics(self) -> Dict[str, Any]:
        """Get statistics about processed images"""
        if not self.processed_images:
            return {}

        stats = {
            'total_images': len(self.processed_images),
            'total_original_size': 0,
            'total_final_size': 0,
            'format_counts': {},
            'quality_levels': {},
            'average_compression': 0.0
        }

        compression_ratios = []

        for image in self.processed_images.values():
            stats['total_original_size'] += image.original_file_size
            stats['total_final_size'] += image.final_file_size

            # Count formats
            fmt = image.final_format
            stats['format_counts'][fmt] = stats['format_counts'].get(fmt, 0) + 1

            # Count quality levels
            ql = image.quality_level
            stats['quality_levels'][ql] = stats['quality_levels'].get(ql, 0) + 1

            compression_ratios.append(image.compression_ratio)

        if compression_ratios:
            stats['average_compression'] = sum(compression_ratios) / len(compression_ratios)

        # Calculate overall compression
        if stats['total_original_size'] > 0:
            stats['overall_compression'] = stats['total_final_size'] / stats['total_original_size']
        else:
            stats['overall_compression'] = 1.0

        return stats

    def save_images_to_directory(self, output_dir: Path) -> Dict[str, str]:
        """Save processed images to directory and return mapping"""
        image_paths = {}

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            for image_id, image in self.processed_images.items():
                filename = f"{image_id}.{image.final_format}"
                file_path = output_dir / filename

                with open(file_path, 'wb') as f:
                    f.write(image.processed_data)

                image_paths[image_id] = str(file_path)

            self.logger.info(f"Saved {len(image_paths)} images to {output_dir}")
            return image_paths

        except Exception as e:
            self.logger.error(f"Failed to save images to directory: {str(e)}")
            return {}

    def create_epub_manifest_items(self, image_paths: Dict[str, str]) -> List[Dict[str, str]]:
        """Create EPUB manifest items for images"""
        manifest_items = []

        for image_id, file_path in image_paths.items():
            # Get image info
            image = self.processed_images.get(image_id)
            if not image:
                continue

            # Determine MIME type
            mime_type = f"image/{image.final_format}"
            if image.final_format == 'jpg':
                mime_type = 'image/jpeg'

            # Create manifest item
            item = {
                'id': image_id,
                'href': f"images/{Path(file_path).name}",
                'media-type': mime_type,
                'properties': []
            }

            # Add properties if available
            if image.alt_text:
                item['properties'].append('alt-text-available')

            manifest_items.append(item)

        return manifest_items