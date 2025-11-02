# EBookAI Enhanced Conversion - Quick Start Guide

由于Docker网络问题，这里提供多种快速部署方案。

## 方案1：本地Python环境测试（推荐用于快速验证）

### 适用场景
- 快速验证增强转换功能
- 开发和调试
- 无需Docker

### 步骤

**1. 安装系统依赖**

```bash
# macOS
brew install tesseract tesseract-lang calibre poppler

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    calibre \
    poppler-utils

# Arch Linux
sudo pacman -S tesseract tesseract-data-chi_sim tesseract-data-chi_tra calibre poppler
```

**2. 创建Python虚拟环境**

```bash
cd /Users/mingchen/workspace/github_repository/EBookAI/backend
python3 -m venv venv-enhanced
source venv-enhanced/bin/activate
```

**3. 安装Python依赖**

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装增强转换依赖
pip install PyMuPDF==1.23.8 pdfplumber==0.10.0 pytesseract==0.3.10 Pillow==10.0.0
```

**4. 验证安装**

```bash
python -c "
import sys
sys.path.insert(0, 'src')
from services.conversion.pdf_parser import PDFParser
from services.conversion.conversion_pipeline import ConversionPipeline
print('✓ All modules imported successfully')
"
```

**5. 运行服务**

```bash
cd src
export ENHANCED_PDF_CONVERSION=true
export CONVERSION_QUALITY_LEVEL=standard
uvicorn main:app --reload --port 8000
```

**6. 测试转换**

```bash
# 在另一个终端
curl -X POST \
  -F "file=@/path/to/test.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert \
  -o output.epub
```

---

## 方案2：使用现有Docker容器（适用于已有容器）

### 步骤

**1. 进入现有容器**

```bash
docker exec -it ebook-ai-workspace sh
```

**2. 在容器内安装依赖**

```bash
# Alpine容器
apk add tesseract-ocr tesseract-ocr-data-chi_sim tesseract-ocr-data-chi_tra

# 安装Python包（避开PyMuPDF）
pip install --break-system-packages \
    pdfplumber==0.10.0 \
    pytesseract==0.3.10 \
    Pillow==10.0.0

# PyMuPDF在Alpine上编译复杂，暂时跳过
# 功能会降级，但基本转换仍可用
```

**3. 修改代码使PyMuPDF可选**

在容器内或本地创建一个配置：

```bash
# 在 backend/src/config.py 添加
USE_PYMUPDF = False  # 如果PyMuPDF不可用
```

---

## 方案3：等待网络恢复后构建完整Docker镜像

### 前置条件
- Docker Hub网络可访问
- 或使用国内镜像源

### 配置Docker镜像源（可选）

```bash
# 编辑 /etc/docker/daemon.json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}

# 重启Docker
sudo systemctl restart docker  # Linux
# 或重启Docker Desktop
```

###构建镜像

```bash
cd /Users/mingchen/workspace/github_repository/EBookAI

# 使用Debian基础镜像（推荐）
docker build -f docker/Dockerfile.amd64 -t ebookai:enhanced-conversion .

# 或使用Alpine（更小但编译复杂）
docker build -f docker/Dockerfile.alpine -t ebookai:enhanced-conversion .
```

### 验证镜像

```bash
# 检查Tesseract
docker run --rm ebookai:enhanced-conversion tesseract --version

# 检查Calibre
docker run --rm ebookai:enhanced-conversion ebook-convert --version

# 检查Python模块
docker run --rm ebookai:enhanced-conversion python -c \
  "import fitz, pdfplumber, pytesseract; print('All modules OK')"
```

---

## 方案4：使用预构建镜像（如果可用）

### 从Docker Registry拉取

```bash
# 如果镜像已推送到仓库
docker pull your-registry/ebookai:enhanced-conversion

# 或从文件加载
docker load < ebookai-enhanced.tar
```

---

## 功能降级策略

如果某些依赖无法安装，系统会自动降级：

### 1. 无PyMuPDF
- **影响**: PDF解析功能受限
- **后备**: 使用pdfplumber或Calibre
- **质量**: 中等，可用于简单PDF

### 2. 无Tesseract
- **影响**: OCR功能不可用
- **后备**: 跳过OCR步骤
- **质量**: 扫描PDF无法转换

### 3. 无Calibre
- **影响**: 后备转换机制不可用
- **后备**: 仅使用自定义管道
- **质量**: 复杂PDF可能失败

### 4. 最小配置
仅需以下依赖即可运行基础转换：

```bash
pip install pdfplumber pytesseract Pillow
```

系统会检测可用组件并自动调整功能。

---

## 当前状态总结

### ✅ 已完成
- 8个核心转换模块实现
- 服务集成完成
- 配置文件更新
- 文档完整
- OpenSpec已归档

### ⚠️ 待解决
- Docker镜像构建（网络问题）
- 完整依赖安装验证

### 🎯 推荐行动

**立即可行**：
1. 使用方案1（本地Python环境）进行功能验证
2. 测试基本转换流程
3. 验证代码质量

**网络恢复后**：
1. 使用方案3构建完整Docker镜像
2. 运行完整测试套件
3. 部署到staging环境

---

## 测试清单

使用任何方案部署后，运行以下测试：

### 基础测试

```bash
# 1. 健康检查
curl http://localhost:8000/api/health/detailed

# 2. 简单PDF转换
curl -X POST \
  -F "file=@simple.pdf" \
  -F "target_format=epub" \
  http://localhost:8000/api/convert -o output.epub

# 3. 验证EPUB
file output.epub  # 应显示: "EPUB document"
```

### 增强功能测试

```bash
# 带中文的PDF
curl -X POST \
  -F "file=@chinese.pdf" \
  -F "target_format=epub" \
  -F "quality_level=standard" \
  http://localhost:8000/api/convert -o chinese.epub

# 扫描PDF（需要Tesseract）
curl -X POST \
  -F "file=@scanned.pdf" \
  -F "target_format=epub" \
  -F "quality_level=high" \
  http://localhost:8000/api/convert -o scanned.epub
```

### 质量验证

```bash
# 使用EPUB检查工具
java -jar epubcheck.jar output.epub

# 在阅读器中打开
open output.epub  # macOS
xdg-open output.epub  # Linux
```

---

## 故障排查

### 问题: ModuleNotFoundError: No module named 'fitz'

**解决**:
```bash
pip install PyMuPDF==1.23.8
# 或降级使用pdfplumber作为替代
```

### 问题: Tesseract not found

**解决**:
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# 验证安装
tesseract --version
```

### 问题: Calibre not found

**解决**:
```bash
# macOS
brew install calibre

# Ubuntu
sudo apt-get install calibre

# 验证安装
ebook-convert --version
```

### 问题: 转换失败with "Unknown error"

**解决**:
1. 检查日志: `docker-compose logs backend`
2. 启用调试: `export DEBUG=true`
3. 使用fast模式测试: `quality_level=fast`
4. 检查PDF是否损坏: `pdfinfo test.pdf`

---

## 性能优化建议

### 1. 使用适当的质量级别

```python
# 快速预览
quality_level="fast"  # < 60s

# 日常使用
quality_level="standard"  # < 180s

# 归档质量
quality_level="high"  # < 300s
```

### 2. 并发控制

```bash
# 限制并发转换数
export MAX_CONCURRENT_CONVERSIONS=3
```

### 3. 内存管理

```bash
# 限制OCR内存使用
export OCR_MAX_MEMORY_MB=500
```

---

## 下一步

1. **选择方案**: 根据环境选择方案1-4
2. **安装依赖**: 按步骤安装
3. **运行测试**: 使用测试清单验证
4. **逐步启用**: 从10%流量开始
5. **监控调优**: 根据实际情况优化

需要帮助？参考：
- `DEPLOYMENT_GUIDE.md` - 完整部署指南
- `TEST_VERIFICATION_CHECKLIST.md` - 测试检查表
- `DEPLOYMENT_STATUS.md` - 当前状态报告

祝部署顺利！
