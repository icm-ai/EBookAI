# Enhanced PDF-to-EPUB Conversion Deployment Guide

## Overview

This guide covers the deployment process for the enhanced PDF-to-EPUB conversion system, including Docker build, configuration, testing, and gradual rollout strategy.

## Prerequisites

- Docker installed and running
- Access to deployment environment
- Test PDF files for validation

## Step 1: Build Docker Image

### Build Command

```bash
docker build -f docker/Dockerfile.amd64 -t ebookai:enhanced-conversion .
```

### What Gets Installed

The Docker image includes:
- **Tesseract OCR** with language models:
  - Chinese Simplified (chi_sim)
  - Chinese Traditional (chi_tra)
  - English (eng)
  - Chinese Traditional Vertical (chi_tra_vert)
- **Calibre** ebook-convert tool
- **Python dependencies**:
  - PyMuPDF 1.23.8
  - pdfplumber 0.10.0
  - pytesseract 0.3.10
  - Pillow 10.0.0

### Verify Build

```bash
# Check image size (should be < 2GB)
docker images ebookai:enhanced-conversion

# Verify Tesseract installation
docker run --rm ebookai:enhanced-conversion tesseract --version

# Verify Calibre installation
docker run --rm ebookai:enhanced-conversion ebook-convert --version

# Test Python imports
docker run --rm ebookai:enhanced-conversion python -c "import fitz, pdfplumber, pytesseract; print('All imports successful')"
```

## Step 2: Configuration

### Environment Variables

Create `.env` file with configuration:

```bash
# Feature Flags
ENHANCED_PDF_CONVERSION=false  # Start disabled for safety
CONVERSION_QUALITY_LEVEL=standard  # fast|standard|high

# OCR Configuration
OCR_CONFIDENCE_THRESHOLD=85
TESSERACT_LANGUAGE_MODELS=chi_sim,chi_tra,eng

# Calibre Fallback
ENABLE_CALIBRE_FALLBACK=true
CALIBRE_QUALITY_THRESHOLD=60
CALIBRE_TIMEOUT=300

# AI Enhancement
AI_ENABLED=true
AI_MAX_RETRIES=3
AI_TIMEOUT=30
```

### Docker Compose

Update `docker-compose.yml` to use the new image:

```yaml
services:
  backend:
    image: ebookai:enhanced-conversion
    env_file: .env
    volumes:
      - ./uploads:/app/uploads
      - ./outputs:/app/outputs
    ports:
      - "8000:8000"
```

## Step 3: Staging Environment Testing

### Start Services

```bash
# Start with enhanced conversion disabled
docker-compose up -d

# Check service health
curl http://localhost:8000/api/health/detailed
```

### Test Suite

#### 1. Backward Compatibility Test

Verify old conversion still works:

```bash
# Test with ENHANCED_PDF_CONVERSION=false
curl -X POST -F "file=@test_simple.pdf" -F "target_format=epub" \
  http://localhost:8000/api/convert
```

#### 2. Enable Enhanced Conversion

```bash
# Update environment
docker-compose exec backend sh -c 'export ENHANCED_PDF_CONVERSION=true'
docker-compose restart backend
```

#### 3. Text-based PDF Test

```bash
curl -X POST \
  -F "file=@test_files/text_based_with_bookmarks.pdf" \
  -F "target_format=epub" \
  -F "quality_level=standard" \
  http://localhost:8000/api/convert -o output_text.epub
```

Expected results:
- Conversion time: < 180 seconds
- Chapters detected from bookmarks
- Images extracted and optimized
- Well-formatted EPUB output

#### 4. Scanned PDF Test

```bash
curl -X POST \
  -F "file=@test_files/scanned_chinese.pdf" \
  -F "target_format=epub" \
  -F "quality_level=standard" \
  http://localhost:8000/api/convert -o output_scanned.epub
```

Expected results:
- OCR applied automatically
- Chinese language detected
- Confidence scores reported
- Readable EPUB output

#### 5. Complex Layout Test

```bash
curl -X POST \
  -F "file=@test_files/multi_column.pdf" \
  -F "target_format=epub" \
  -F "quality_level=high" \
  http://localhost:8000/api/convert -o output_complex.epub
```

Expected results:
- Multi-column layout detected
- Correct reading order
- Tables preserved
- High-quality images

#### 6. Calibre Fallback Test

```bash
# Test with problematic PDF that triggers fallback
curl -X POST \
  -F "file=@test_files/problematic.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert -o output_fallback.epub
```

Expected results:
- Fallback triggered automatically
- Calibre conversion successful
- Metadata indicates fallback used

#### 7. Performance Test

```bash
# Test large file handling
curl -X POST \
  -F "file=@test_files/large_500pages.pdf" \
  -F "target_format=epub" \
  -F "quality_level=fast" \
  http://localhost:8000/api/convert -o output_large.epub
```

Expected results:
- Memory usage < 500MB
- Progress updates via WebSocket
- Completion within timeout
- No memory leaks

### Validate EPUB Output

Use EPUB validation tools:

```bash
# Install epubcheck
wget https://github.com/w3c/epubcheck/releases/download/v5.1.0/epubcheck-5.1.0.zip
unzip epubcheck-5.1.0.zip

# Validate generated EPUBs
java -jar epubcheck-5.1.0/epubcheck.jar output_text.epub
java -jar epubcheck-5.1.0/epubcheck.jar output_scanned.epub
java -jar epubcheck-5.1.0/epubcheck.jar output_complex.epub
```

### Test on EPUB Readers

Verify readability on multiple readers:
- **Apple Books** (macOS/iOS)
- **Google Play Books** (Android/Web)
- **Calibre Viewer** (Desktop)
- **Adobe Digital Editions** (Desktop)

Check for:
- Proper text rendering
- Image display
- Navigation functionality
- Chinese character support
- Table of contents structure

## Step 4: Gradual Rollout Strategy

### Phase 1: Limited Rollout (Week 1)

**Target**: 10% of conversion traffic

```bash
# Configuration
ENHANCED_PDF_CONVERSION=true
ROLLOUT_PERCENTAGE=10  # If supported by routing layer
```

**Monitoring**:
- Conversion success rate
- Average conversion time
- Error rates by PDF type
- Calibre fallback trigger rate
- Memory usage patterns
- User feedback

**Acceptance Criteria**:
- Success rate ≥ 95%
- No increase in error rates vs. baseline
- Average conversion time within targets
- No critical bugs reported

### Phase 2: Expanded Rollout (Week 2-3)

**Target**: 50% of conversion traffic

```bash
ROLLOUT_PERCENTAGE=50
```

**Additional Monitoring**:
- Quality score distribution
- OCR accuracy metrics
- Chapter detection accuracy
- Image optimization effectiveness
- AI enhancement usage

**Acceptance Criteria**:
- Quality scores consistently > 80%
- OCR confidence > 85% for clean scans
- Chapter detection > 85% accuracy
- Positive user feedback

### Phase 3: Full Rollout (Week 4+)

**Target**: 100% of conversion traffic

```bash
ROLLOUT_PERCENTAGE=100
# or simply
ENHANCED_PDF_CONVERSION=true  # No percentage limiting
```

**Final Validation**:
- Compare metrics with baseline
- Verify no performance degradation
- Confirm quality improvements
- Document lessons learned

### Phase 4: Deprecate Legacy (Week 8+)

After 4+ weeks of stable operation:

```python
# In conversion_service.py
# Remove old _pdf_to_epub method
# Keep as @deprecated for emergency rollback
```

## Step 5: Monitoring and Metrics

### Key Metrics Dashboard

Track these metrics in real-time:

1. **Conversion Metrics**
   - Total conversions per hour
   - Success rate (%)
   - Average conversion time
   - Conversion by quality preset

2. **Quality Metrics**
   - Average quality score
   - OCR confidence distribution
   - Chapter detection accuracy
   - Calibre fallback rate

3. **Performance Metrics**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network bandwidth

4. **Error Metrics**
   - Error rate by type
   - Timeout occurrences
   - Failed conversions
   - Calibre fallback failures

### Alerting Rules

Set up alerts for:
- Error rate > 5%
- Average conversion time > 300s
- Memory usage > 80%
- Calibre fallback rate > 30%
- OCR confidence < 70% (high frequency)

## Step 6: Rollback Plan

### Immediate Rollback (< 5 minutes)

If critical issues occur:

```bash
# 1. Disable enhanced conversion
docker-compose exec backend sh -c 'export ENHANCED_PDF_CONVERSION=false'
docker-compose restart backend

# 2. Verify legacy pipeline working
curl http://localhost:8000/api/health/detailed
```

### Gradual Rollback

If issues are non-critical but persistent:

```bash
# Reduce rollout percentage
ROLLOUT_PERCENTAGE=25  # Reduce from 50% to 25%
# or
ROLLOUT_PERCENTAGE=10  # Reduce to 10%
```

### Emergency Procedures

1. **Memory Leak Detected**
   - Reduce ROLLOUT_PERCENTAGE immediately
   - Add memory monitoring
   - Restart services periodically
   - Investigate and patch

2. **High Error Rate**
   - Identify error patterns
   - Disable for problematic PDF types
   - Route those PDFs to Calibre fallback
   - Fix and redeploy

3. **Performance Degradation**
   - Check resource utilization
   - Scale horizontally if needed
   - Optimize slow components
   - Consider caching strategies

## Step 7: Post-Deployment Tasks

### Week 1
- [ ] Monitor metrics daily
- [ ] Review error logs
- [ ] Collect user feedback
- [ ] Adjust configuration if needed

### Week 2-4
- [ ] Analyze quality improvements
- [ ] Compare with baseline metrics
- [ ] Optimize based on real usage
- [ ] Document common issues

### Month 2+
- [ ] Archive OpenSpec change (completed)
- [ ] Update user documentation
- [ ] Train support team
- [ ] Plan future enhancements

## Troubleshooting

### Issue: Tesseract not found

```bash
# Verify installation
docker-compose exec backend which tesseract
docker-compose exec backend tesseract --list-langs

# If missing, rebuild image
docker-compose build --no-cache
```

### Issue: Calibre not available

```bash
# Verify installation
docker-compose exec backend which ebook-convert
docker-compose exec backend ebook-convert --version

# Fallback will be disabled if not found
# Check logs for warnings
docker-compose logs backend | grep -i calibre
```

### Issue: High memory usage

```bash
# Check current usage
docker stats backend

# Reduce quality preset
CONVERSION_QUALITY_LEVEL=fast

# Limit concurrent conversions
MAX_CONCURRENT_CONVERSIONS=2
```

### Issue: OCR accuracy low

```bash
# Check language models installed
docker-compose exec backend tesseract --list-langs

# Verify PDF quality
# - DPI should be > 300 for good results
# - Skewed pages need preprocessing

# Adjust confidence threshold
OCR_CONFIDENCE_THRESHOLD=80  # Lower from 85
```

### Issue: Conversion timeout

```bash
# Increase timeout
CONVERSION_TIMEOUT=600  # Increase to 10 minutes

# Use fast mode for large files
CONVERSION_QUALITY_LEVEL=fast

# Enable Calibre fallback
ENABLE_CALIBRE_FALLBACK=true
```

## Success Criteria

Deployment is considered successful when:

1. **Functionality**
   - ✓ All test cases pass
   - ✓ EPUB validation passes
   - ✓ Readable on multiple readers

2. **Performance**
   - ✓ Conversion times within targets
   - ✓ Memory usage < 500MB per conversion
   - ✓ No memory leaks detected

3. **Quality**
   - ✓ Quality scores > 80% average
   - ✓ OCR confidence > 85% for clean scans
   - ✓ Chapter detection > 85% accuracy

4. **Stability**
   - ✓ Success rate ≥ 95%
   - ✓ Error rate < 5%
   - ✓ No critical bugs in 4 weeks

5. **User Satisfaction**
   - ✓ Positive user feedback
   - ✓ Reduced support tickets
   - ✓ Improved EPUB quality noted

## Conclusion

Following this deployment guide ensures a safe, gradual rollout of the enhanced PDF-to-EPUB conversion system with proper testing, monitoring, and rollback capabilities. The phased approach minimizes risk while maximizing the opportunity to collect real-world feedback and optimize the system.

For questions or issues during deployment, refer to:
- `backend/docs/enhanced_conversion.md` - Technical documentation
- `openspec/changes/archive/2025-11-02-enhance-pdf-to-epub-conversion/` - Implementation details
- `IMPLEMENTATION_SUMMARY.md` - Summary of changes
