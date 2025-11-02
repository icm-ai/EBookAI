# Enhanced PDF-to-EPUB Conversion - Test Verification Checklist

此清单用于验证增强的PDF转EPUB转换系统在部署前和部署后的各个阶段。

---

## Pre-Deployment Verification

### 1. Code Quality Checks

#### 1.1 Syntax Validation
```bash
cd backend/src/services/conversion
python3 -m py_compile pdf_parser.py
python3 -m py_compile layout_analyzer.py
python3 -m py_compile ocr_service.py
python3 -m py_compile chapter_detector.py
python3 -m py_compile image_processor.py
python3 -m py_compile epub_generator.py
python3 -m py_compile calibre_fallback.py
python3 -m py_compile conversion_pipeline.py
```

**Expected Result**: 无语法错误

- [ ] 所有模块编译通过
- [ ] 无语法错误报告

#### 1.2 Import Validation
```bash
cd backend
python3 -c "
import sys
sys.path.insert(0, 'src')
from services.conversion.pdf_parser import PDFParser
from services.conversion.layout_analyzer import LayoutAnalyzer
from services.conversion.ocr_service import OCRService
from services.conversion.chapter_detector import ChapterDetector
from services.conversion.image_processor import ImageProcessor
from services.conversion.epub_generator import EpubGenerator
from services.conversion.calibre_fallback import CalibreFallback
from services.conversion.conversion_pipeline import ConversionPipeline
print('All imports successful')
"
```

**Expected Result**: "All imports successful"

- [ ] PDFParser 导入成功
- [ ] LayoutAnalyzer 导入成功
- [ ] OCRService 导入成功
- [ ] ChapterDetector 导入成功
- [ ] ImageProcessor 导入成功
- [ ] EpubGenerator 导入成功
- [ ] CalibreFallback 导入成功
- [ ] ConversionPipeline 导入成功

#### 1.3 Configuration Validation
```bash
cd backend/src
python3 -c "
from config import (
    ENHANCED_PDF_CONVERSION,
    CONVERSION_QUALITY_LEVEL,
    OCR_CONFIDENCE_THRESHOLD,
    ENABLE_CALIBRE_FALLBACK,
    CALIBRE_QUALITY_THRESHOLD
)
print(f'ENHANCED_PDF_CONVERSION: {ENHANCED_PDF_CONVERSION}')
print(f'CONVERSION_QUALITY_LEVEL: {CONVERSION_QUALITY_LEVEL}')
print(f'OCR_CONFIDENCE_THRESHOLD: {OCR_CONFIDENCE_THRESHOLD}')
print(f'ENABLE_CALIBRE_FALLBACK: {ENABLE_CALIBRE_FALLBACK}')
print(f'CALIBRE_QUALITY_THRESHOLD: {CALIBRE_QUALITY_THRESHOLD}')
"
```

**Expected Result**: 所有配置变量加载成功

- [ ] ENHANCED_PDF_CONVERSION 可读取
- [ ] CONVERSION_QUALITY_LEVEL 可读取
- [ ] OCR_CONFIDENCE_THRESHOLD 可读取
- [ ] ENABLE_CALIBRE_FALLBACK 可读取
- [ ] CALIBRE_QUALITY_THRESHOLD 可读取

### 2. Docker Image Verification

#### 2.1 Image Build
```bash
docker build -f docker/Dockerfile.amd64 -t ebookai:enhanced-conversion .
```

**Expected Result**: 构建成功，无错误

- [ ] Docker镜像构建成功
- [ ] 镜像大小 < 2GB
- [ ] 无安全警告

#### 2.2 System Dependencies
```bash
docker run --rm ebookai:enhanced-conversion sh -c "
echo '=== Tesseract ===' && tesseract --version | head -1 && \
echo '=== Language Models ===' && tesseract --list-langs && \
echo '=== Calibre ===' && ebook-convert --version | head -1 && \
echo '=== Poppler ===' && pdfinfo -v 2>&1 | head -1
"
```

**Expected Result**: 所有工具已安装并可用

- [ ] Tesseract OCR 版本 ≥ 5.0
- [ ] Chinese Simplified (chi_sim) 语言模型可用
- [ ] Chinese Traditional (chi_tra) 语言模型可用
- [ ] English (eng) 语言模型可用
- [ ] Calibre ebook-convert 可用
- [ ] Poppler pdfinfo 可用

#### 2.3 Python Dependencies
```bash
docker run --rm ebookai:enhanced-conversion python -c "
import fitz
import pdfplumber
import pytesseract
from PIL import Image
import ebooklib
print('✓ All Python modules available')
print(f'  PyMuPDF: {fitz.__version__}')
print(f'  pdfplumber: {pdfplumber.__version__}')
"
```

**Expected Result**: 所有Python模块可导入

- [ ] PyMuPDF (fitz) 可导入
- [ ] pdfplumber 可导入
- [ ] pytesseract 可导入
- [ ] Pillow (PIL) 可导入
- [ ] ebooklib 可导入

### 3. Service Integration Verification

#### 3.1 Backend Service Health
```bash
docker-compose up -d
sleep 5
curl http://localhost:8000/api/health/detailed
```

**Expected Result**: HTTP 200, 健康状态 "healthy"

- [ ] 服务启动成功
- [ ] 健康检查返回 200
- [ ] 数据库连接正常
- [ ] Redis连接正常
- [ ] 所有组件状态正常

#### 3.2 Feature Flag Control
```bash
# Test with flag disabled
docker-compose exec backend sh -c "
export ENHANCED_PDF_CONVERSION=false
python -c '
from config import ENHANCED_PDF_CONVERSION
assert ENHANCED_PDF_CONVERSION == False, \"Flag should be False\"
print(\"✓ Feature flag disabled correctly\")
'
"

# Test with flag enabled
docker-compose exec backend sh -c "
export ENHANCED_PDF_CONVERSION=true
python -c '
from config import ENHANCED_PDF_CONVERSION
assert ENHANCED_PDF_CONVERSION == True, \"Flag should be True\"
print(\"✓ Feature flag enabled correctly\")
'
"
```

**Expected Result**: 特性标志正确控制

- [ ] ENHANCED_PDF_CONVERSION=false 工作正常
- [ ] ENHANCED_PDF_CONVERSION=true 工作正常
- [ ] 标志变化后路由正确切换

---

## Functional Testing

### 4. Legacy Pipeline Verification (Baseline)

#### 4.1 Basic PDF to EPUB (Legacy)
```bash
curl -X POST \
  -F "file=@test_files/simple_text.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output_legacy.epub

# Validate EPUB
java -jar epubcheck.jar output_legacy.epub
```

**Expected Result**: 转换成功，EPUB有效

- [ ] 转换完成，无错误
- [ ] EPUB文件生成
- [ ] EPUB验证通过
- [ ] 转换时间 < 60秒

### 5. Enhanced Pipeline Testing

#### 5.1 Text-based PDF with Chapters
```bash
curl -X POST \
  -F "file=@test_files/text_with_bookmarks.pdf" \
  -F "target_format=epub" \
  -F "quality_level=standard" \
  http://localhost:8000/api/convert \
  -o output_text.epub
```

**Expected Result**: 高质量EPUB，章节检测正确

- [ ] 转换成功
- [ ] 章节从书签中提取
- [ ] 目录结构正确
- [ ] 图片已提取和优化
- [ ] 转换时间 < 180秒
- [ ] 质量分数 > 80%

**Validation**:
```bash
# Extract and inspect EPUB
unzip -q output_text.epub -d output_text_dir
cat output_text_dir/OEBPS/toc.ncx  # Check TOC
cat output_text_dir/OEBPS/content.opf  # Check metadata
```

- [ ] toc.ncx 包含所有章节
- [ ] 元数据完整
- [ ] HTML结构良好
- [ ] CSS样式已应用

#### 5.2 Scanned PDF with OCR
```bash
curl -X POST \
  -F "file=@test_files/scanned_chinese.pdf" \
  -F "target_format=epub" \
  -F "quality_level=standard" \
  http://localhost:8000/api/convert \
  -o output_scanned.epub
```

**Expected Result**: OCR成功，文本可读

- [ ] 扫描性质检测成功
- [ ] OCR自动应用
- [ ] 中文语言模型使用
- [ ] 文本提取准确率 > 90%
- [ ] OCR置信度 > 85%
- [ ] 转换时间 < 300秒

**Validation**:
```bash
# Check OCR metadata
unzip -q output_scanned.epub -d output_scanned_dir
grep -i "ocr" output_scanned_dir/OEBPS/content.opf
grep -i "confidence" output_scanned_dir/OEBPS/content.opf
```

- [ ] OCR元数据记录
- [ ] 置信度分数记录
- [ ] 文本可读，格式正确

#### 5.3 Complex Multi-column Layout
```bash
curl -X POST \
  -F "file=@test_files/multi_column.pdf" \
  -F "target_format=epub" \
  -F "quality_level=high" \
  http://localhost:8000/api/convert \
  -o output_complex.epub
```

**Expected Result**: 布局分析正确，阅读顺序保持

- [ ] 多列布局检测
- [ ] 阅读顺序正确
- [ ] 表格结构保留
- [ ] 图片位置关联正确
- [ ] 转换时间 < 300秒
- [ ] 质量分数 > 75%

**Manual Validation**:
- [ ] 在EPUB阅读器中打开
- [ ] 文本流畅，无乱序
- [ ] 图片位置合理
- [ ] 表格可读

#### 5.4 Quality Presets

**Fast Mode**:
```bash
curl -X POST \
  -F "file=@test_files/large_document.pdf" \
  -F "target_format=epub" \
  -F "quality_level=fast" \
  http://localhost:8000/api/convert \
  -o output_fast.epub
```

- [ ] 转换时间 < 60秒
- [ ] 图片压缩激进 (max 600px)
- [ ] 跳过OCR（如适用）
- [ ] 基本章节检测
- [ ] EPUB可读

**Standard Mode** (默认):
```bash
curl -X POST \
  -F "file=@test_files/standard_document.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output_standard.epub
```

- [ ] 转换时间 < 180秒
- [ ] OCR应用（需要时）
- [ ] 多方法章节检测
- [ ] 图片优化 (max 800px)
- [ ] 良好质量

**High Quality Mode**:
```bash
curl -X POST \
  -F "file=@test_files/archival_document.pdf" \
  -F "target_format=epub" \
  -F "quality_level=high" \
  http://localhost:8000/api/convert \
  -o output_high.epub
```

- [ ] 转换时间 < 300秒
- [ ] 完整OCR预处理
- [ ] 所有检测方法
- [ ] AI增强应用
- [ ] 高分辨率图片 (max 1200px)
- [ ] 质量分数 > 90%

#### 5.5 Calibre Fallback

**Trigger by Error**:
```bash
# Use a problematic PDF
curl -X POST \
  -F "file=@test_files/problematic.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output_fallback.epub
```

- [ ] 自定义管道错误检测
- [ ] Calibre后备自动触发
- [ ] 转换成功完成
- [ ] 元数据标记后备使用
- [ ] 日志记录后备原因

**Trigger by Low Quality**:
```bash
# Configure low quality threshold
CALIBRE_QUALITY_THRESHOLD=70

# Convert a challenging PDF
curl -X POST \
  -F "file=@test_files/challenging.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output_quality_fallback.epub
```

- [ ] 质量分数计算
- [ ] 低于阈值触发后备
- [ ] 质量对比执行
- [ ] 返回更高质量结果

**Explicit Request**:
```bash
curl -X POST \
  -F "file=@test_files/standard.pdf" \
  -F "target_format=epub" \
  -F "conversion_mode=calibre" \
  http://localhost:8000/api/convert \
  -o output_explicit_calibre.epub
```

- [ ] 直接使用Calibre
- [ ] 跳过自定义管道
- [ ] 转换成功
- [ ] 元数据正确标记

#### 5.6 Progress Tracking

```bash
# Start conversion in background
TASK_ID=$(curl -X POST \
  -F "file=@test_files/large.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  | jq -r '.task_id')

# Monitor progress via WebSocket
wscat -c ws://localhost:8000/ws/task/$TASK_ID

# Or poll status
curl http://localhost:8000/api/task/$TASK_ID
```

**Expected Progress Updates**:
- [ ] Stage 1: PDF Analysis (0-20%)
- [ ] Stage 2: Content Extraction (20-40%)
- [ ] Stage 3: Structure Recognition (40-60%)
- [ ] Stage 4: AI Enhancement (60-80%)
- [ ] Stage 5: EPUB Generation (80-100%)

**Validation**:
- [ ] 进度百分比准确
- [ ] 阶段描述清晰
- [ ] 时间估算合理
- [ ] WebSocket更新及时
- [ ] 完成后状态正确

---

## Performance Testing

### 6. Performance Benchmarks

#### 6.1 Small PDF (< 10 pages)
- [ ] Fast mode: < 10秒
- [ ] Standard mode: < 30秒
- [ ] High mode: < 60秒
- [ ] Memory usage: < 100MB

#### 6.2 Medium PDF (50-100 pages)
- [ ] Fast mode: < 30秒
- [ ] Standard mode: < 120秒
- [ ] High mode: < 200秒
- [ ] Memory usage: < 300MB

#### 6.3 Large PDF (> 500 pages)
- [ ] Fast mode: < 60秒
- [ ] Standard mode: < 180秒
- [ ] High mode: < 300秒
- [ ] Memory usage: < 500MB
- [ ] No memory leaks

#### 6.4 Concurrent Conversions
```bash
# Start 5 conversions simultaneously
for i in {1..5}; do
  curl -X POST \
    -F "file=@test_files/test_$i.pdf" \
    -F "target_format=epub" \
    http://localhost:8000/api/convert \
    -o output_$i.epub &
done
wait
```

- [ ] 所有转换完成
- [ ] 无转换失败
- [ ] 总内存 < 2GB
- [ ] CPU使用合理
- [ ] 无资源耗尽

---

## Quality Assurance

### 7. Output Quality Validation

#### 7.1 EPUB Validation
```bash
# Use epubcheck for all outputs
for epub in output_*.epub; do
  java -jar epubcheck.jar $epub
done
```

- [ ] 所有EPUB文件符合规范
- [ ] 无结构错误
- [ ] 无元数据错误
- [ ] 无内容引用错误

#### 7.2 Readability Testing

测试每个EPUB在以下阅读器中的表现：

**Apple Books** (macOS/iOS):
- [ ] 文本正确显示
- [ ] 图片正常加载
- [ ] 导航功能正常
- [ ] 中文字符正确渲染
- [ ] 样式应用正确

**Calibre Viewer**:
- [ ] 文本正确显示
- [ ] 图片正常加载
- [ ] 目录结构完整
- [ ] 元数据显示正确

**Google Play Books**:
- [ ] 文本流畅
- [ ] 图片适配屏幕
- [ ] 字体渲染正常

#### 7.3 Quality Metrics

对于每个转换，验证质量指标：

```bash
# Check quality metadata in EPUB
unzip -q output_standard.epub -d temp
grep -A 5 "quality" temp/OEBPS/content.opf
```

- [ ] 质量分数记录
- [ ] 转换方法记录
- [ ] OCR置信度（如适用）
- [ ] 章节检测置信度
- [ ] 处理时间记录

---

## Regression Testing

### 8. Backward Compatibility

#### 8.1 Legacy API Compatibility
```bash
# Disable enhanced conversion
export ENHANCED_PDF_CONVERSION=false

# Run old test cases
curl -X POST \
  -F "file=@test_files/legacy_test.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output_legacy_compat.epub
```

- [ ] API接口未改变
- [ ] 参数兼容
- [ ] 返回格式一致
- [ ] 旧功能正常

#### 8.2 Other Format Conversions
```bash
# Verify other conversions still work
curl -X POST -F "file=@test.epub" -F "target_format=pdf" \
  http://localhost:8000/api/convert -o test_epub_to_pdf.pdf

curl -X POST -F "file=@test.docx" -F "target_format=epub" \
  http://localhost:8000/api/convert -o test_docx_to_epub.epub
```

- [ ] EPUB → PDF 正常
- [ ] DOCX → EPUB 正常
- [ ] MOBI → EPUB 正常
- [ ] 其他格式转换未受影响

---

## Security Testing

### 9. Security Validation

#### 9.1 Input Validation
```bash
# Test with malformed PDF
curl -X POST \
  -F "file=@test_files/malformed.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert
```

- [ ] 错误优雅处理
- [ ] 无服务崩溃
- [ ] 错误消息安全（不暴露内部信息）

#### 9.2 File Size Limits
```bash
# Test with oversized file
curl -X POST \
  -F "file=@test_files/huge_500mb.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert
```

- [ ] 文件大小限制有效
- [ ] 适当的错误消息
- [ ] 无内存溢出

#### 9.3 Command Injection Protection
```bash
# Test with malicious filenames
curl -X POST \
  -F "file=@test_files/; rm -rf /;.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert
```

- [ ] 文件名清理
- [ ] 命令注入防护
- [ ] 路径遍历防护

---

## Deployment Validation

### 10. Production Readiness

#### 10.1 Configuration Checklist
- [ ] ENHANCED_PDF_CONVERSION 默认值设置正确
- [ ] 质量级别默认为 "standard"
- [ ] OCR阈值配置合理
- [ ] Calibre后备已启用
- [ ] 超时设置适当
- [ ] 日志级别配置正确

#### 10.2 Monitoring Setup
- [ ] Prometheus指标导出
- [ ] 转换成功率监控
- [ ] 转换时间监控
- [ ] 错误率监控
- [ ] Calibre后备率监控
- [ ] 内存使用监控

#### 10.3 Alerting Configuration
- [ ] 错误率 > 5% 告警
- [ ] 平均转换时间 > 300s 告警
- [ ] 内存使用 > 80% 告警
- [ ] Calibre后备率 > 30% 告警

#### 10.4 Documentation Completeness
- [ ] API文档更新
- [ ] 用户指南编写
- [ ] 运维手册完成
- [ ] 故障排查指南可用
- [ ] 部署指南验证

---

## Sign-off

### Approval Checklist

- [ ] **开发团队**: 所有代码已审查和测试
- [ ] **QA团队**: 所有测试用例通过
- [ ] **运维团队**: 部署流程已验证
- [ ] **产品团队**: 功能符合需求
- [ ] **安全团队**: 安全审查通过

### Deployment Authorization

- **Environment**: _________________ (Staging / Production)
- **Date**: _________________
- **Approved By**: _________________
- **Notes**: _________________

---

**最后更新**: 2025-11-02
**版本**: 1.0
**下次审查**: 部署后一周
