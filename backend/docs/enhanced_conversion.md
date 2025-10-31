# Enhanced PDF to EPUB Conversion

This document describes the enhanced PDF to EPUB conversion system implemented in EBookAI.

## Overview

The enhanced conversion system provides professional-grade PDF to EPUB conversion with the following key features:

- **Multi-stage conversion pipeline** with quality checks at each stage
- **Advanced PDF parsing** using PyMuPDF for superior text extraction
- **Intelligent chapter detection** using multiple analysis methods
- **OCR support** for scanned PDFs using Tesseract
- **AI-powered content optimization** for metadata and quality improvement
- **Professional EPUB generation** with proper styling and navigation
- **Calibre fallback mechanism** for robustness and edge case handling

## Architecture

### Components

1. **PDFParser** (`pdf_parser.py`)
   - Advanced PDF parsing with PyMuPDF
   - Text extraction with position and font information
   - Image extraction with format detection
   - Scan detection and metadata extraction

2. **LayoutAnalyzer** (`layout_analyzer.py`)
   - Multi-column layout detection
   - Reading order analysis
   - Table structure identification
   - Content region analysis

3. **OCRService** (`ocr_service.py`)
   - Tesseract OCR integration
   - Language detection (Chinese/English)
   - Image preprocessing for better accuracy
   - Confidence scoring

4. **ChapterDetector** (`chapter_detector.py`)
   - Multi-method chapter detection
   - PDF bookmark/outline extraction
   - Font-based heading detection
   - AI-powered content analysis

5. **ImageProcessor** (`image_processor.py`)
   - Image extraction and optimization
   - Format conversion (JPEG/PNG)
   - Size optimization for different quality levels
   - Image-text association analysis

6. **EpubGenerator** (`epub_generator.py`)
   - Professional EPUB creation
   - Advanced CSS styling for Chinese/English
   - Table of contents generation
   - Metadata and navigation management

7. **CalibreFallback** (`calibre_fallback.py`)
   - Calibre ebook-convert wrapper
   - Automatic fallback triggering
   - Quality comparison and analysis
   - Error handling and logging

8. **ConversionPipeline** (`conversion_pipeline.py`)
   - Main orchestration component
   - 5-stage conversion process
   - Progress tracking and error handling
   - Quality assessment

## Conversion Process

### 5-Stage Pipeline

1. **PDF Analysis** (10%)
   - Validate PDF structure
   - Extract metadata
   - Detect scan nature
   - Estimate processing complexity

2. **Content Extraction** (30%)
   - Extract text with PyMuPDF
   - Extract images with optimization
   - Apply OCR for scanned pages
   - Combine and organize content

3. **Structure Recognition** (20%)
   - Detect chapters using multiple methods
   - Analyze layout and columns
   - Build document hierarchy
   - Associate content with structure

4. **AI Enhancement** (20%)
   - Generate metadata if missing
   - Refine chapter titles
   - Optimize content quality
   - Calculate quality scores

5. **EPUB Generation** (20%)
   - Generate professional EPUB
   - Apply proper styling
   - Create navigation and TOC
   - Validate output

### Quality Levels

- **Fast**: < 60 seconds, basic quality, no OCR
- **Standard**: < 180 seconds, good quality, OCR when needed
- **High**: < 300 seconds, professional quality, full AI enhancement

### Fallback Mechanism

The system automatically triggers Calibre fallback when:
- Custom pipeline encounters unrecoverable error
- Quality score falls below threshold (default 60%)
- User explicitly requests Calibre mode
- PDF has complex features not supported by custom pipeline

## Configuration

### Environment Variables

```bash
# Enable enhanced conversion
ENHANCED_PDF_CONVERSION=true

# Quality level (fast/standard/high)
CONVERSION_QUALITY_LEVEL=standard

# OCR settings
OCR_CONFIDENCE_THRESHOLD=85
TESSERACT_LANGUAGE_MODELS=chi_sim,chi_tra,eng

# Calibre fallback settings
ENABLE_CALIBRE_FALLBACK=true
CALIBRE_QUALITY_THRESHOLD=60
CALIBRE_TIMEOUT=300
```

### Dependencies

```bash
# Required Python packages
PyMuPDF>=1.23.8
pdfplumber>=0.10.0
pytesseract>=0.3.10
Pillow>=10.0.0
ebooklib>=0.18
```

### System Dependencies

```bash
# Required system packages
tesseract-ocr
tesseract-ocr-chi-sim
tesseract-ocr-chi-tra
tesseract-ocr-eng
poppler-utils
calibre
```

## Usage

### Basic Usage

```python
from services.conversion_service import ConversionService

# Initialize with AI service (optional)
conversion_service = ConversionService(ai_service)

# Convert PDF to EPUB
result = await conversion_service.convert_file(
    file_path="path/to/document.pdf",
    target_format="epub",
    task_id="conversion-123"
)
```

### Advanced Usage with Pipeline

```python
from services.conversion.conversion_pipeline import ConversionPipeline

# Initialize pipeline
pipeline = ConversionPipeline(ai_service)

# Convert with custom settings
result = pipeline.convert_pdf_to_epub(
    input_path=Path("document.pdf"),
    output_path=Path("document.epub"),
    quality_level="high"
)
```

### Using Calibre Directly

```python
result = pipeline.convert_pdf_to_epub(
    input_path=Path("document.pdf"),
    output_path=Path("document.epub"),
    use_calibre=True
)
```

## Performance Metrics

### Expected Performance

| Quality Level | Processing Time | Memory Usage | File Size |
|---------------|-----------------|--------------|-----------|
| Fast | < 60 seconds | < 200MB | Small |
| Standard | < 180 seconds | < 400MB | Medium |
| High | < 300 seconds | < 600MB | Large |

### Quality Targets

| Metric | Target | Acceptable |
|--------|--------|-----------|
| Chapter detection accuracy | 90%+ | 70%+ |
| Image extraction rate | 95%+ | 80%+ |
| OCR accuracy (clean scan) | 95%+ | 85%+ |
| Overall quality score | 80%+ | 60%+ |

## Troubleshooting

### Common Issues

1. **Calibre not found**
   ```bash
   # Install Calibre
   sudo apt-get install calibre
   # Or use the Docker image with Calibre pre-installed
   ```

2. **Tesseract not found**
   ```bash
   # Install Tesseract
   sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim
   ```

3. **Enhanced conversion disabled**
   ```bash
   # Enable in environment
   export ENHANCED_PDF_CONVERSION=true
   ```

4. **Poor OCR quality**
   - Ensure Tesseract language models are installed
   - Check image quality and resolution
   - Adjust `OCR_CONFIDENCE_THRESHOLD`

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Testing

Run the test suite:

```bash
cd backend
python -m pytest tests/test_enhanced_conversion.py -v
```

## Future Enhancements

Planned improvements for future releases:

1. **Mathematical formula rendering** with LaTeX support
2. **Advanced table layout preservation**
3. **Interactive PDF element handling**
4. **DRM-protected PDF support**
5. **Parallel processing** for large documents
6. **Batch optimization** for multiple files
7. **Custom quality presets** for different use cases

## Contributing

When contributing to the enhanced conversion system:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation
4. Consider backward compatibility
5. Test with various PDF types and quality levels

## License

This enhanced conversion system is part of the EBookAI project and follows the same license terms.