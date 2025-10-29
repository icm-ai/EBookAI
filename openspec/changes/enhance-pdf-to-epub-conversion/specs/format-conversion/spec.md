# Format Conversion Specification Delta

## MODIFIED Requirements

### Requirement: PDF to EPUB Conversion

The system SHALL convert PDF files to EPUB format with professional-grade quality suitable for immediate reading, preserving document structure, images, and formatting.

#### Scenario: Text-based PDF with chapters and images
- **WHEN** a text-based PDF file with clear chapter structure and embedded images is uploaded for EPUB conversion
- **THEN** the system extracts text with proper paragraph breaks, detects chapter boundaries using font analysis and bookmarks, extracts and optimizes all images, generates a table of contents, and produces a well-formatted EPUB with proper navigation

#### Scenario: Scanned PDF requiring OCR
- **WHEN** a scanned PDF (image-based) is uploaded for EPUB conversion
- **THEN** the system detects the scan nature (low text extraction ratio), applies Tesseract OCR with appropriate language model (Chinese/English auto-detected), reconstructs text with proper paragraph structure, and produces a readable EPUB with OCR confidence warnings if accuracy is below 85%

#### Scenario: PDF with complex layout (multi-column, mixed content)
- **WHEN** a PDF with multi-column layout, tables, and mixed text-image content is uploaded
- **THEN** the system uses layout analysis to detect columns and reading order, preserves table structure in basic HTML format, associates images with surrounding text, and generates EPUB with proper content flow

#### Scenario: Chinese language PDF with special characters
- **WHEN** a Chinese language PDF with special characters, punctuation, and mixed CJK content is uploaded
- **THEN** the system correctly extracts Chinese text using UTF-8 encoding, preserves character integrity, applies Chinese language OCR if needed, and generates EPUB with proper Chinese typography and font embedding

#### Scenario: Large PDF exceeding memory limits
- **WHEN** a PDF file with more than 500 pages or file size exceeding 100MB is uploaded
- **THEN** the system processes the file in streaming mode (page-by-page), manages memory usage below 500MB threshold, provides progress updates via WebSocket, and completes conversion within configurable timeout (default 5 minutes)

## ADDED Requirements

### Requirement: Intelligent Chapter Detection

The system SHALL automatically detect chapter boundaries and hierarchical structure in PDF documents using multiple analysis methods.

#### Scenario: PDF with bookmark structure
- **WHEN** a PDF contains bookmark/outline metadata
- **THEN** the system extracts the bookmark structure, maps bookmarks to chapter titles and hierarchy levels, and generates EPUB table of contents matching the PDF structure with 95%+ accuracy

#### Scenario: PDF without bookmarks but clear typography
- **WHEN** a PDF lacks bookmarks but has consistent heading styles (larger font, bold text)
- **THEN** the system analyzes font sizes and styles across pages, identifies heading patterns with confidence scores, detects chapter boundaries using heading positions and page breaks, and generates hierarchical structure with 80%+ accuracy

#### Scenario: PDF with minimal structure indicators
- **WHEN** a PDF has no clear bookmarks or heading styles
- **THEN** the system applies AI-based content analysis to detect chapter transitions, uses page break patterns and content similarity scoring, generates reasonable chapter divisions (every 20-30 pages), and provides user with confidence score for manual review if below 70%

### Requirement: Image Extraction and Optimization

The system SHALL extract all images from PDF files, optimize them for EPUB format, and embed them with proper positioning.

#### Scenario: PDF with embedded photographs and diagrams
- **WHEN** a PDF contains embedded JPEG photographs and PNG diagrams
- **THEN** the system extracts all images preserving format (JPEG for photos, PNG for diagrams), resizes images exceeding 800px width while maintaining aspect ratio, optimizes file size (target: <500KB per image), associates images with nearest text content, and embeds images in EPUB at appropriate positions with alt text

#### Scenario: PDF with high-resolution images for print
- **WHEN** a PDF contains high-resolution images (>300 DPI) intended for print
- **THEN** the system converts images to web-optimized resolution (150 DPI for EPUB), reduces file size by 60-80% while maintaining visual quality, includes resolution metadata, and keeps total EPUB size under 50MB

#### Scenario: PDF with inline images and text wrapping
- **WHEN** a PDF has images embedded inline with text wrapping around them
- **THEN** the system detects image positions relative to text blocks, preserves basic spatial relationships, generates EPUB with images positioned between paragraphs, and maintains reading flow continuity

### Requirement: OCR Support for Scanned Documents

The system SHALL detect scanned PDFs and apply Optical Character Recognition to extract readable text.

#### Scenario: Clean scanned PDF with Chinese text
- **WHEN** a scanned PDF with clear Chinese text (>300 DPI, good contrast) is uploaded
- **THEN** the system detects scan nature (text extraction yields <10% of expected content), renders PDF pages as images, applies Tesseract OCR with Chinese language model (chi_sim or chi_tra), achieves >90% character accuracy, and produces readable EPUB with confidence scores per page

#### Scenario: Low-quality scan requiring preprocessing
- **WHEN** a scanned PDF has skewed pages, low resolution, or poor contrast
- **THEN** the system applies preprocessing (deskew, denoise, contrast enhancement), performs OCR on improved images, reports OCR confidence scores, warns user if confidence is below 85%, and suggests manual review for critical content

#### Scenario: Mixed PDF with both digital text and scanned pages
- **WHEN** a PDF contains both digital text pages and scanned image pages
- **THEN** the system detects text availability per page, extracts digital text directly for text-based pages, applies OCR only to scanned pages, combines results seamlessly, and produces unified EPUB with consistent formatting

### Requirement: AI-Enhanced Content Optimization

The system SHALL leverage AI services to improve conversion quality through intelligent content analysis and enhancement.

#### Scenario: Metadata generation from content
- **WHEN** a PDF lacks proper metadata (no title, author, or subject fields)
- **THEN** the system extracts text from first few pages, sends to AI service for metadata inference, generates title from first-page content or heading, extracts author name if present, generates subject/category tags, and populates EPUB metadata with AI-generated values and confidence scores

#### Scenario: Chapter title refinement
- **WHEN** detected chapter boundaries lack clear titles or have generic titles
- **THEN** the system extracts content from chapter starts, sends to AI service for title generation, generates descriptive chapter titles reflecting content, preserves original titles if they exist and are meaningful, and updates EPUB table of contents with refined titles

#### Scenario: Content quality enhancement for poor OCR results
- **WHEN** OCR produces text with errors or fragmentation
- **THEN** the system detects low confidence sections, sends problematic text to AI for correction, applies grammar and structure fixes, preserves original meaning, marks enhanced sections in metadata, and improves overall readability score by 20%+

### Requirement: Conversion Quality Levels

The system SHALL provide configurable quality presets balancing speed and output quality.

#### Scenario: Fast conversion mode for preview
- **WHEN** user selects "fast" quality preset
- **THEN** the system skips OCR for scanned pages (extracts available text only), uses basic chapter detection (page breaks only), resizes images aggressively (max 600px width), skips AI enhancement, completes conversion in <60 seconds, and produces basic readable EPUB suitable for preview

#### Scenario: Standard conversion mode for general use
- **WHEN** user selects "standard" quality preset (default)
- **THEN** the system applies OCR when needed, uses multi-method chapter detection (bookmarks + font analysis), optimizes images normally (max 800px width), applies basic AI enhancement (metadata only), completes conversion in <180 seconds, and produces good-quality EPUB suitable for reading

#### Scenario: High-quality conversion mode for archival
- **WHEN** user selects "high-quality" preset
- **THEN** the system applies OCR with preprocessing for all scanned content, uses all chapter detection methods including AI analysis, preserves higher image resolution (max 1200px width), applies full AI enhancement (metadata + chapter titles + content optimization), accepts longer processing time (<5 minutes), and produces professional-grade EPUB matching commercial quality

### Requirement: Progress Tracking and Transparency

The system SHALL provide detailed progress information during conversion with estimated completion time.

#### Scenario: Real-time progress updates via WebSocket
- **WHEN** a PDF-to-EPUB conversion is in progress
- **THEN** the system broadcasts progress updates via WebSocket at each pipeline stage (Analysis, Extraction, Recognition, Enhancement, Generation), includes percentage complete and current operation description, estimates time remaining based on page count and complexity, and updates UI with current stage and progress bar

#### Scenario: Conversion with quality warnings
- **WHEN** conversion encounters quality issues (low OCR confidence, unclear structure)
- **THEN** the system includes warning messages in progress updates, specifies affected pages or sections, provides confidence scores for detected structure, suggests review areas, and includes warnings in final EPUB metadata for user awareness

## REMOVED Requirements

None - This change is purely additive and enhancing existing functionality.
