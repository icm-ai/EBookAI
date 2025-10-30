# Design: Enhanced PDF to EPUB Conversion

## Context

Current PDF-to-EPUB conversion uses PyPDF2 with basic text extraction, producing poor-quality output. Target is human-level conversion quality with professional EPUB output suitable for immediate reading.

### Constraints
- Must maintain existing API interface for backward compatibility
- Should handle both text-based and scanned (image-based) PDFs
- Need to support Chinese and English content
- Must complete within reasonable timeout (configurable, default 5 minutes)
- Follow KISS principle - add complexity only where necessary

### Stakeholders
- End users requiring high-quality EPUB conversion for reading
- Existing API clients expecting same endpoint behavior

## Goals / Non-Goals

**Goals:**
- Extract and preserve document structure (chapters, headings, paragraphs)
- Extract and embed images in proper positions
- Support OCR for scanned PDFs
- Generate proper EPUB metadata and table of contents
- Leverage AI for content enhancement and quality improvement
- Maintain reasonable conversion performance (< 5 minutes for typical books)

**Non-Goals:**
- Perfect mathematical formula rendering (defer to future enhancement)
- Advanced table layout preservation (basic support only)
- Interactive PDF elements (forms, annotations)
- DRM-protected PDF handling

## Decisions

### 1. PDF Parsing Library: PyMuPDF (fitz)

**Decision:** Use PyMuPDF as primary PDF parsing engine, supplemented by pdfplumber for layout analysis.

**Rationale:**
- PyMuPDF provides superior text extraction with position information
- Built-in image extraction with format support
- Better handling of fonts and encoding (especially Chinese)
- Active maintenance and good performance
- Supports page rendering for OCR fallback

**Alternatives considered:**
- PyPDF2: Current solution, insufficient quality
- pdfminer.six: Good extraction but slower, more complex
- Camelot: Specialized for tables, not general-purpose

### 2. OCR Engine: Tesseract 5.x

**Decision:** Integrate Tesseract OCR for scanned PDF support with Chinese language models.

**Rationale:**
- Industry standard, high accuracy
- Supports Chinese (simplified and traditional)
- Can be containerized easily
- Free and open-source

**Implementation approach:**
- Detect if PDF is scanned (low text extraction ratio)
- Render pages as images using PyMuPDF
- Apply Tesseract with language auto-detection
- Use Chinese models when detected

### 3. Multi-Stage Conversion Pipeline

**Decision:** Implement 5-stage pipeline with quality checkpoints.

**Stages:**
```
1. PDF Analysis (metadata, page count, scan detection)
2. Content Extraction (text, images, structure)
3. Structure Recognition (chapters, headings, TOC)
4. AI Enhancement (content optimization, metadata)
5. EPUB Generation (assembly, styling, validation)
```

**Rationale:**
- Each stage can be tested independently
- Progress tracking at stage boundaries
- Allows optimization at each stage
- Easier debugging and error handling

### 4. AI Integration for Quality Enhancement

**Decision:** Leverage existing AI service for:
- Chapter title generation from content
- Table of contents generation
- Metadata extraction (author, title, subject)
- Content quality improvement (paragraph detection)

**Rationale:**
- Existing AI infrastructure available
- Significant quality improvement with minimal code
- User-configurable (can disable for speed)
- Aligns with project's AI-enhanced value proposition

### 5. Image Processing Strategy

**Decision:** Extract images, optimize size, embed in EPUB with proper positioning.

**Approach:**
- Extract all images from PDF pages
- Convert to JPEG/PNG based on content type
- Resize large images (max 800px width for mobile readers)
- Associate images with nearest text content
- Embed with relative positioning in chapters

**Rationale:**
- EPUBs must be reasonable file size (< 50MB typical)
- Mobile reader compatibility requires smaller images
- Proper image-text association improves reading experience

### 6. Chapter Detection Algorithm

**Decision:** Multi-method chapter detection with confidence scoring.

**Methods (in priority order):**
1. PDF bookmark/outline extraction
2. Font size and style analysis (larger/bold = heading)
3. Page break patterns
4. AI-based content analysis
5. Fallback: every N pages

**Rationale:**
- Different PDFs have different structure indicators
- Combining methods improves accuracy
- AI fallback ensures reasonable output even without structure
- Configurable sensitivity for user control

### 7. Calibre Fallback Mechanism

**Decision:** Integrate Calibre ebook-convert as fallback conversion engine when custom pipeline fails or produces low-quality output.

**Fallback Triggers:**
1. Custom pipeline throws unrecoverable error
2. Conversion quality score below threshold (< 60%)
3. User explicitly requests Calibre mode
4. PDF has complex features not handled by custom pipeline

**Implementation approach:**
- Detect need for fallback during pipeline execution
- Call Calibre ebook-convert via subprocess
- Parse Calibre output and warnings
- Return Calibre-generated EPUB with metadata about fallback usage
- Log comparison metrics when both methods are available

**Rationale:**
- Calibre is mature and handles many edge cases well
- Provides robustness for difficult PDFs
- Increases overall success rate of conversions
- Allows quality comparison between custom and Calibre approaches
- Maintains flexibility without full dependency on Calibre

**Trade-offs:**
- Increases Docker image size (~300MB for Calibre)
- Fallback conversion loses AI enhancement benefits
- Less control over Calibre conversion process
- Acceptable: Primary path remains custom pipeline with full control

**Alternatives considered:**
- Calibre as primary engine: Rejected due to lack of customization and AI integration
- No fallback: Rejected due to need for robustness and edge case handling
- Multiple fallback engines: Rejected as overly complex for MVP

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  ConversionService                          │
│                  (Orchestrator)                             │
└────────────┬────────────────────────────────────────────────┘
             │
    ┌────────┼────────┬──────────┬────────────┬─────────────┐
    │        │        │          │            │             │
    ▼        ▼        ▼          ▼            ▼             ▼
┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│  PDF   │ │ Layout  │ │   OCR    │ │   AI    │ │  EPUB    │ │ Calibre  │
│ Parser │ │Analyzer │ │ Service  │ │ Service │ │Generator │ │ Fallback │
└────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────┘ └──────────┘
    │            │           │            │           │             │
    │            │           │            │           │             │
    └────────────┴───────────┴────────────┴───────────┴─────────────┘
                         │
                    ┌────▼─────┐
                    │ Progress │
                    │ Tracker  │
                    └──────────┘
```

### File Structure

```
backend/src/services/conversion/
├── pdf_parser.py          # PyMuPDF-based PDF parsing
├── layout_analyzer.py     # pdfplumber layout analysis
├── ocr_service.py         # Tesseract OCR integration
├── chapter_detector.py    # Intelligent chapter detection
├── image_processor.py     # Image extraction and optimization
├── epub_generator.py      # Professional EPUB creation
├── calibre_fallback.py    # Calibre ebook-convert wrapper
└── conversion_pipeline.py # Pipeline orchestration
```

## Risks / Trade-offs

### Risk: Increased conversion time
- **Mitigation:** Configurable quality levels (fast/standard/high)
- **Mitigation:** Progress tracking with ETA
- **Mitigation:** Async processing with WebSocket updates

### Risk: Docker image size increase
- **Mitigation:** Multi-stage build to minimize final image
- **Mitigation:** Optional OCR language models (download on demand)
- **Impact:** Acceptable for quality improvement

### Risk: OCR accuracy for low-quality scans
- **Mitigation:** Preprocessing (deskew, denoise)
- **Mitigation:** AI-based post-processing
- **Mitigation:** User warning when OCR confidence is low

### Risk: Memory usage for large PDFs
- **Mitigation:** Streaming processing (page-by-page)
- **Mitigation:** Configurable image resolution limits
- **Mitigation:** Automatic fallback to simplified mode

### Trade-off: Complexity vs Quality
- **Decision:** Accept increased complexity for significant quality improvement
- **Justification:** Core value proposition of the platform
- **Safeguard:** Comprehensive testing and rollback capability

## Migration Plan

### Phase 1: Foundation (Week 1-2)
1. Add new dependencies to requirements.txt
2. Create new module structure
3. Implement PDFParser with PyMuPDF
4. Add basic image extraction
5. Unit tests for new modules

### Phase 2: Core Features (Week 3-4)
1. Implement layout analysis
2. Build chapter detection algorithm
3. Add OCR service integration
4. Implement EPUB generator
5. Integration tests

### Phase 3: AI Enhancement (Week 5)
1. Integrate AI service for metadata
2. Add content optimization
3. Implement quality checks
4. End-to-end tests

### Phase 4: Optimization & Deployment (Week 6)
1. Performance optimization
2. Error handling and edge cases
3. Documentation updates
4. Gradual rollout with feature flag

### Rollback Strategy
- Feature flag `ENHANCED_PDF_CONVERSION` (default: false)
- Old implementation remains available
- Can switch back via environment variable
- Monitor quality metrics and user feedback

## Performance Targets

| Metric | Current | Target | Acceptable |
|--------|---------|--------|------------|
| Conversion time (200-page book) | 20s | 90s | 180s |
| Memory usage | 100MB | 300MB | 500MB |
| EPUB file size | N/A | 5-20MB | 50MB |
| Chapter detection accuracy | 0% | 90% | 70% |
| Image extraction rate | 0% | 95% | 80% |
| OCR accuracy (good scan) | N/A | 95% | 85% |

## Open Questions

1. **Should we support PDF password protection?**
   - Decision: Not in this phase, defer to future enhancement

2. **How to handle footnotes and endnotes?**
   - Decision: Preserve in-place, AI can help identify patterns

3. **Support for right-to-left languages (Arabic, Hebrew)?**
   - Decision: Not in MVP, focus on Chinese/English first

4. **Configurable quality presets for users?**
   - Decision: Yes, three levels: fast, standard, high-quality
