# Proposal: Enhance PDF to EPUB Conversion Quality

## Why

Current PDF-to-EPUB conversion produces low-quality output that is not suitable for reading. The implementation uses basic PyPDF2 text extraction with simplistic page-to-chapter mapping, resulting in:

- Loss of document structure (chapters, sections, headings)
- Missing images and graphics
- Poor typography and formatting
- No support for scanned PDFs (OCR needed)
- Incorrect paragraph breaks and text flow
- Missing metadata and table of contents

Target: Achieve human-level conversion quality with zero perceivable difference from professionally published EPUBs, making converted books immediately readable without manual post-processing.

## What Changes

**Core Enhancements:**
- Advanced PDF parsing using PyMuPDF (fitz) for better text and image extraction
- Intelligent chapter detection using heading styles, fonts, and AI analysis
- Full image extraction with format conversion and optimization
- OCR support for scanned PDFs using Tesseract
- Smart paragraph reconstruction with proper text flow
- Layout analysis for multi-column text, tables, and complex structures
- AI-powered content optimization (chapter naming, metadata generation, quality enhancement)
- Professional EPUB generation with proper styling and navigation
- Calibre fallback mechanism for difficult PDFs or error recovery

**Technical Improvements:**
- Replace PyPDF2 with PyMuPDF for superior PDF parsing
- Add pdfplumber for layout analysis
- Integrate Tesseract OCR for scanned documents
- Leverage existing AI services for content analysis and enhancement
- Implement multi-stage conversion pipeline with quality checks
- Integrate Calibre ebook-convert as fallback conversion engine for edge cases

## Impact

**Affected specs:**
- `format-conversion` - Major enhancement to PDF-to-EPUB conversion requirements

**Affected code:**
- `backend/src/services/conversion_service.py` - Complete rewrite of `_pdf_to_epub()` method
- `backend/src/services/conversion/parsers.py` - New PDF parsing module
- `backend/src/services/conversion/layout_analyzer.py` - New layout analysis module
- `backend/src/services/ai_service.py` - Extended AI integration for content enhancement
- `backend/requirements.txt` - Add PyMuPDF, pdfplumber, pytesseract, Pillow dependencies
- `docker/Dockerfile` - Add Tesseract OCR installation

**Affected infrastructure:**
- Docker image size increase (~500MB for Tesseract, Calibre, and language data)
- Conversion time increase (3-5x longer for high-quality processing)
- Memory usage increase for large PDFs with many images

**Breaking changes:**
- None - Enhancement maintains backward compatibility with existing API

**Dependencies:**
- PyMuPDF (fitz) >= 1.23.0
- pdfplumber >= 0.10.0
- pytesseract >= 0.3.10
- Tesseract OCR >= 5.0
- Pillow >= 10.0.0
- Calibre >= 6.0 (ebook-convert command-line tool)
- Chinese language support for OCR (chi_sim, chi_tra)
