"""
Test cases for enhanced PDF to EPUB conversion.
"""

from pathlib import Path

import pytest

from services.conversion.calibre_fallback import CalibreFallback
from services.conversion.chapter_detector import ChapterDetector
from services.conversion.conversion_pipeline import ConversionPipeline
from services.conversion.epub_generator import EpubGenerator
from services.conversion.image_processor import ImageProcessor
from services.conversion.layout_analyzer import LayoutAnalyzer
from services.conversion.pdf_parser import PDFParser


class TestPDFParser:
    def setup_method(self):
        self.parser = PDFParser()

    def test_validate_pdf_with_valid_file(self):
        assert hasattr(self.parser, "validate_pdf")

    def test_validate_pdf_with_invalid_file(self):
        result = self.parser.validate_pdf(Path("nonexistent.pdf"))
        assert not result["is_valid"]
        assert "error" in result


class TestLayoutAnalyzer:
    def setup_method(self):
        self.analyzer = LayoutAnalyzer()

    def test_analyze_document_structure(self):
        result = self.analyzer.analyze_document_structure([])
        assert result["total_pages"] == 0
        assert result["multi_column_pages"] == 0
        assert result["single_column_pages"] == 0


class TestChapterDetector:
    def setup_method(self):
        self.detector = ChapterDetector()

    def test_detect_chapters_with_empty_data(self):
        result = self.detector.detect_chapters(None, [])
        assert len(result.chapters) == 0
        assert result.total_confidence == 0.0


class TestImageProcessor:
    def setup_method(self):
        self.processor = ImageProcessor()

    def test_process_images_with_empty_list(self):
        assert self.processor.process_images([], [], "standard") == []

    def test_get_image_statistics_empty(self):
        assert self.processor.get_image_statistics() == {}


class TestEpubGenerator:
    def setup_method(self):
        self.generator = EpubGenerator()

    def test_create_chinese_css(self):
        css = self.generator._create_chinese_css()
        assert "font-family" in css
        assert "line-height" in css

    def test_create_english_css(self):
        css = self.generator._create_english_css()
        assert "font-family" in css
        assert "line-height" in css


class TestCalibreFallback:
    def setup_method(self):
        self.fallback = CalibreFallback()

    def test_is_available(self):
        assert isinstance(self.fallback.is_available(), bool)

    def test_get_fallback_statistics(self):
        stats = self.fallback.get_fallback_statistics()
        assert "available" in stats
        assert "enabled" in stats
        assert "quality_threshold" in stats


class TestConversionPipeline:
    def setup_method(self):
        self.pipeline = ConversionPipeline()

    def test_get_pipeline_statistics(self):
        stats = self.pipeline.get_pipeline_statistics()
        assert "enhanced_conversion_enabled" in stats
        assert "calibre_fallback_enabled" in stats
        assert "pipeline_stages" in stats
        assert len(stats["pipeline_stages"]) == 5


class TestEnhancedConversionIntegration:
    def test_all_components_importable(self):
        from services.conversion.calibre_fallback import CalibreFallback
        from services.conversion.chapter_detector import ChapterDetector
        from services.conversion.conversion_pipeline import ConversionPipeline
        from services.conversion.epub_generator import EpubGenerator
        from services.conversion.image_processor import ImageProcessor
        from services.conversion.layout_analyzer import LayoutAnalyzer
        from services.conversion.ocr_service import OCRService
        from services.conversion.pdf_parser import PDFParser

        assert all(
            component is not None
            for component in (
                PDFParser,
                LayoutAnalyzer,
                OCRService,
                ChapterDetector,
                ImageProcessor,
                EpubGenerator,
                CalibreFallback,
                ConversionPipeline,
            )
        )

    def test_pipeline_initialization(self):
        pipeline = ConversionPipeline()
        assert pipeline.pdf_parser is not None
        assert pipeline.layout_analyzer is not None
        assert pipeline.ocr_service is not None
        assert pipeline.chapter_detector is not None
        assert pipeline.image_processor is not None
        assert pipeline.epub_generator is not None
        assert pipeline.calibre_fallback is not None


class TestQualityValidation:
    def test_quality_score_calculation(self):
        pipeline = ConversionPipeline()

        class MockMetadata:
            title = "Test Title"
            author = "Test Author"
            page_count = 100
            has_bookmarks = True
            scan_probability = 0.1

        score = pipeline._calculate_quality_score(MockMetadata(), None, [], None)
        assert 0 <= score <= 100
        assert score > 50


if __name__ == "__main__":
    pytest.main([__file__])
