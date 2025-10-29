# Implementation Tasks

## 1. Foundation Setup

- [ ] 1.1 Add dependencies to `backend/requirements.txt`
  - PyMuPDF (fitz) >= 1.23.0
  - pdfplumber >= 0.10.0
  - pytesseract >= 0.3.10
  - Pillow >= 10.0.0
- [ ] 1.2 Update Docker configuration
  - Add Tesseract OCR installation to Dockerfile
  - Add Chinese language data (chi_sim, chi_tra)
  - Optimize multi-stage build for size
- [ ] 1.3 Create new module structure
  - `backend/src/services/conversion/pdf_parser.py`
  - `backend/src/services/conversion/layout_analyzer.py`
  - `backend/src/services/conversion/ocr_service.py`
  - `backend/src/services/conversion/chapter_detector.py`
  - `backend/src/services/conversion/image_processor.py`
  - `backend/src/services/conversion/epub_generator.py`
  - `backend/src/services/conversion/conversion_pipeline.py`
- [ ] 1.4 Add configuration options to `config.py`
  - ENHANCED_PDF_CONVERSION feature flag
  - CONVERSION_QUALITY_LEVEL (fast/standard/high)
  - OCR_CONFIDENCE_THRESHOLD
  - IMAGE_MAX_WIDTH settings
  - TESSERACT_LANGUAGE_MODELS path

## 2. PDF Parser Implementation

- [ ] 2.1 Create PDFParser class with PyMuPDF
  - Extract text with position information
  - Get font information (size, family, weight)
  - Extract page dimensions and layout
  - Detect text blocks and reading order
- [ ] 2.2 Implement metadata extraction
  - Extract title, author, subject from PDF metadata
  - Get page count and PDF version
  - Detect encryption and permissions
  - Extract bookmark/outline structure
- [ ] 2.3 Add scan detection logic
  - Calculate text-to-page ratio
  - Detect image-only pages
  - Return scan probability score
- [ ] 2.4 Write unit tests for PDFParser
  - Test with text-based PDF
  - Test with scanned PDF
  - Test with mixed PDF
  - Test with encrypted PDF (should fail gracefully)

## 3. Layout Analyzer Implementation

- [ ] 3.1 Create LayoutAnalyzer class with pdfplumber
  - Detect multi-column layouts
  - Identify table structures
  - Find text blocks and their positions
  - Determine reading order for complex layouts
- [ ] 3.2 Implement column detection algorithm
  - Analyze text block positions
  - Calculate column boundaries
  - Order content by reading flow
- [ ] 3.3 Add table detection
  - Identify table structures
  - Extract table content as HTML
  - Handle nested tables
- [ ] 3.4 Write unit tests for LayoutAnalyzer
  - Test single-column layout
  - Test two-column layout
  - Test complex multi-column layout
  - Test with tables

## 4. OCR Service Implementation

- [ ] 4.1 Create OCRService class with Tesseract
  - Render PDF page to image using PyMuPDF
  - Apply image preprocessing (deskew, denoise, contrast)
  - Perform OCR with language detection
  - Return text with confidence scores
- [ ] 4.2 Implement preprocessing pipeline
  - Deskew tilted pages
  - Enhance contrast for low-quality scans
  - Denoise for cleaner text
  - Binarization for better OCR accuracy
- [ ] 4.3 Add language detection
  - Auto-detect Chinese (simplified/traditional)
  - Support English and mixed content
  - Use appropriate Tesseract language models
- [ ] 4.4 Implement confidence scoring
  - Per-character confidence from Tesseract
  - Per-line and per-page confidence aggregation
  - Warning generation for low confidence sections
- [ ] 4.5 Write unit tests for OCRService
  - Test with clean Chinese scan
  - Test with low-quality scan
  - Test with mixed language content
  - Test with skewed pages

## 5. Chapter Detector Implementation

- [ ] 5.1 Create ChapterDetector class
  - Implement multi-method detection strategy
  - Calculate confidence scores per method
  - Merge results from different methods
  - Generate hierarchical chapter structure
- [ ] 5.2 Implement bookmark-based detection
  - Extract PDF bookmark structure
  - Map bookmarks to page numbers
  - Build hierarchy from bookmark levels
  - Achieve 95%+ accuracy for PDFs with bookmarks
- [ ] 5.3 Implement font-based detection
  - Analyze font sizes across pages
  - Detect heading patterns (larger/bold text)
  - Calculate heading confidence scores
  - Group pages into chapters based on headings
- [ ] 5.4 Implement page-break detection
  - Identify natural chapter breaks
  - Analyze content similarity between pages
  - Detect pattern changes (blank pages, page numbering)
- [ ] 5.5 Add AI-based detection fallback
  - Send page content to AI service
  - Request chapter boundary suggestions
  - Parse AI response for chapter divisions
  - Use when other methods have low confidence
- [ ] 5.6 Write unit tests for ChapterDetector
  - Test with bookmark-enabled PDF
  - Test with clear heading structure
  - Test with minimal structure
  - Test AI fallback logic

## 6. Image Processor Implementation

- [ ] 6.1 Create ImageProcessor class
  - Extract images from PDF pages with PyMuPDF
  - Associate images with text positions
  - Optimize image size and format
  - Generate image metadata
- [ ] 6.2 Implement image extraction
  - Get all images from PDF pages
  - Extract image format, dimensions, DPI
  - Determine optimal extraction method per image
  - Handle inline images and full-page images
- [ ] 6.3 Add image optimization
  - Resize images based on quality preset
  - Convert formats (preserve PNG for diagrams, JPEG for photos)
  - Compress images (target <500KB per image)
  - Maintain aspect ratios
- [ ] 6.4 Implement image-text association
  - Calculate image positions relative to text
  - Find nearest text blocks
  - Generate alt text from surrounding content
  - Preserve reading order with images
- [ ] 6.5 Write unit tests for ImageProcessor
  - Test image extraction from various PDFs
  - Test resizing and optimization
  - Test format conversion
  - Test image-text association accuracy

## 7. EPUB Generator Implementation

- [ ] 7.1 Create EPUBGenerator class
  - Build EPUB structure from extracted content
  - Generate proper HTML chapters
  - Create navigation and table of contents
  - Add metadata and styling
- [ ] 7.2 Implement chapter HTML generation
  - Convert text blocks to HTML paragraphs
  - Embed images with proper positioning
  - Apply CSS styling for readability
  - Handle special characters and encoding
- [ ] 7.3 Create table of contents
  - Build EPUB NCX navigation
  - Generate HTML table of contents
  - Map chapters to file structure
  - Support multi-level hierarchies
- [ ] 7.4 Add metadata generation
  - Populate Dublin Core metadata
  - Add language and encoding information
  - Include generation timestamp and source info
  - Embed confidence scores for quality reference
- [ ] 7.5 Implement CSS styling
  - Create professional stylesheet for Chinese/English
  - Set proper line height and spacing
  - Define heading styles (h1-h6)
  - Add image styling (centered, max-width)
- [ ] 7.6 Write unit tests for EPUBGenerator
  - Test EPUB structure validation
  - Test HTML generation
  - Test TOC creation
  - Test metadata population

## 8. Conversion Pipeline Implementation

- [ ] 8.1 Create ConversionPipeline orchestrator
  - Implement 5-stage pipeline
  - Coordinate component interactions
  - Handle errors at each stage
  - Track progress and update status
- [ ] 8.2 Implement Stage 1: PDF Analysis
  - Parse PDF metadata
  - Detect scan nature
  - Analyze page structure
  - Estimate processing complexity
- [ ] 8.3 Implement Stage 2: Content Extraction
  - Extract text using PDFParser
  - Extract images using ImageProcessor
  - Apply OCR if needed for scanned pages
  - Combine text and image content
- [ ] 8.4 Implement Stage 3: Structure Recognition
  - Detect chapters using ChapterDetector
  - Analyze layout using LayoutAnalyzer
  - Build document hierarchy
  - Associate content with structure
- [ ] 8.5 Implement Stage 4: AI Enhancement
  - Generate metadata if missing
  - Refine chapter titles
  - Optimize content quality for low OCR confidence
  - Calculate overall quality score
- [ ] 8.6 Implement Stage 5: EPUB Generation
  - Generate EPUB using EPUBGenerator
  - Validate EPUB structure
  - Add quality report to metadata
  - Return final file path and statistics
- [ ] 8.7 Add progress tracking integration
  - Update progress_tracker at each stage
  - Calculate time estimates
  - Broadcast WebSocket updates
  - Handle cancellation requests
- [ ] 8.8 Implement quality presets
  - Fast mode: skip OCR, basic detection, aggressive image compression
  - Standard mode: OCR when needed, multi-method detection, normal optimization
  - High-quality mode: full OCR, all methods, AI enhancement, detailed analysis
- [ ] 8.9 Write integration tests for pipeline
  - Test complete flow with text-based PDF
  - Test with scanned PDF
  - Test with complex layout PDF
  - Test with Chinese content
  - Test each quality preset

## 9. Service Integration

- [ ] 9.1 Update ConversionService
  - Add feature flag check for enhanced conversion
  - Route to new pipeline when enabled
  - Keep old implementation as fallback
  - Add logging for comparison
- [ ] 9.2 Extend AI service integration
  - Add metadata inference endpoint usage
  - Add chapter title generation
  - Add content optimization for OCR results
  - Handle AI service timeouts gracefully
- [ ] 9.3 Update progress tracking
  - Add new stage names and descriptions
  - Calculate stage-specific progress percentages
  - Update WebSocket message format
  - Add quality warnings in progress updates
- [ ] 9.4 Write integration tests
  - Test with feature flag enabled/disabled
  - Test AI service integration
  - Test progress updates
  - Test error handling and fallback

## 10. Testing and Quality Assurance

- [ ] 10.1 Create test fixture PDFs
  - Text-based PDF with bookmarks (English)
  - Text-based PDF with bookmarks (Chinese)
  - Scanned PDF (clean, high quality)
  - Scanned PDF (low quality, skewed)
  - Mixed PDF (text + scanned pages)
  - Complex layout PDF (multi-column, tables)
  - Large PDF (>500 pages)
  - PDF with many images
- [ ] 10.2 Write end-to-end tests
  - Test each fixture through complete pipeline
  - Validate EPUB structure and content
  - Check metadata accuracy
  - Verify image extraction
  - Validate chapter detection
- [ ] 10.3 Performance testing
  - Measure conversion time for each quality preset
  - Monitor memory usage during conversion
  - Test with large files (100MB+)
  - Verify timeout handling
- [ ] 10.4 Quality validation
  - Compare output with professional EPUBs
  - Validate readability on multiple EPUB readers
  - Check Chinese character rendering
  - Test image display and positioning
- [ ] 10.5 Add regression tests
  - Ensure old PDF-to-EPUB still works with flag off
  - Test backward compatibility
  - Verify no breaking changes to API

## 11. Documentation and Configuration

- [ ] 11.1 Update API documentation
  - Document new quality preset parameter
  - Describe conversion stages
  - List supported features and limitations
  - Add examples for different PDF types
- [ ] 11.2 Add environment variables documentation
  - ENHANCED_PDF_CONVERSION flag
  - CONVERSION_QUALITY_LEVEL
  - OCR_CONFIDENCE_THRESHOLD
  - IMAGE_MAX_WIDTH_FAST/STANDARD/HIGH
  - TESSERACT_DATA_PATH
- [ ] 11.3 Create troubleshooting guide
  - OCR language model installation
  - Memory issues with large PDFs
  - Low OCR confidence handling
  - Chapter detection tuning
- [ ] 11.4 Update README
  - List new features
  - Show example usage
  - Describe quality presets
  - Add performance benchmarks

## 12. Deployment and Rollout

- [ ] 12.1 Build and test Docker image
  - Verify Tesseract installation
  - Test Chinese language models
  - Check image size (<2GB)
  - Validate all dependencies
- [ ] 12.2 Deploy with feature flag disabled
  - Deploy to staging environment
  - Verify backward compatibility
  - Test with production-like data
- [ ] 12.3 Enable feature flag for testing
  - Enable for internal testing
  - Monitor performance metrics
  - Collect quality feedback
  - Compare with old implementation
- [ ] 12.4 Gradual rollout to users
  - Enable for 10% of conversions
  - Monitor error rates and completion times
  - Gather user feedback
  - Increase to 50%, then 100%
- [ ] 12.5 Monitor and optimize
  - Track conversion success rate
  - Monitor average conversion time
  - Analyze quality scores
  - Optimize based on real usage patterns

## 13. Post-Implementation

- [ ] 13.1 Archive old implementation
  - Move old _pdf_to_epub to deprecated module
  - Keep for reference and emergency rollback
  - Schedule removal for future version
- [ ] 13.2 Update CHANGELOG
  - Document major enhancement
  - List key features
  - Note breaking changes (none expected)
  - Include migration guide if needed
- [ ] 13.3 Create user guide
  - How to choose quality preset
  - Tips for best results
  - Handling low-quality scans
  - When to use OCR enhancement
