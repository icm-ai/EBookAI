# 故障排查指南

本指南帮助快速诊断和解决 EBookAI 常见问题。

## 目录

- [快速诊断](#快速诊断)
- [服务启动问题](#服务启动问题)
- [文件转换问题](#文件转换问题)
- [AI 服务问题](#ai-服务问题)
- [批量转换问题](#批量转换问题)
- [性能问题](#性能问题)
- [Docker 相关问题](#docker-相关问题)
- [日志分析](#日志分析)

---

## 快速诊断

### 健康检查

使用健康检查端点快速诊断系统状态：

```bash
# 基础健康检查
curl http://localhost:8000/api/health

# 详细健康检查
curl http://localhost:8000/api/health/detailed | jq

# 查看系统指标
curl http://localhost:8000/api/health/metrics | jq
```

**正常输出示例**：
```json
{
  "status": "healthy",
  "service": "EBookAI",
  "version": "1.0.0"
}
```

### 检查服务可用性

```bash
# 检查后端
curl http://localhost:8000/docs

# 检查前端（如果使用）
curl http://localhost:3000
```

---

## 服务启动问题

### 问题 1: Docker 容器无法启动

**症状**：
```
Error response from daemon: Conflict. The container name "/ebook-ai" is already in use
```

**解决方案**：
```bash
# 停止并删除旧容器
docker stop ebook-ai
docker rm ebook-ai

# 或使用 docker-compose
docker-compose down
docker-compose up -d
```

---

### 问题 2: 端口被占用

**症状**：
```
bind: address already in use
```

**诊断**：
```bash
# 检查端口占用（macOS/Linux）
lsof -i :8000

# 检查端口占用（Windows）
netstat -ano | findstr :8000
```

**解决方案**：

方案 1 - 停止占用端口的进程：
```bash
# macOS/Linux
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

方案 2 - 修改端口：
```bash
# 修改 docker-compose.yml
ports:
  - "8001:8000"  # 使用8001端口
```

---

### 问题 3: Calibre 未安装

**症状**：
```
detail: "Calibre ebook-convert not found"
```

**解决方案**：

macOS:
```bash
brew install calibre
```

Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install calibre
```

Windows:
- 从 https://calibre-ebook.com/download 下载安装
- 确保 `ebook-convert.exe` 在 PATH 中

验证安装：
```bash
ebook-convert --version
```

---

## 文件转换问题

### 问题 1: 转换失败 - 文件格式不支持

**症状**：
```json
{
  "detail": "Unsupported file format: .docx"
}
```

**支持的格式**：
- 输入：EPUB, PDF, MOBI, AZW3, TXT
- 输出：EPUB, PDF, MOBI, AZW3, TXT

**解决方案**：
1. 确认文件格式是否支持
2. 将不支持的格式先转换为支持的格式（使用其他工具）
3. 查看 [格式兼容性](faq.md#支持的格式)

---

### 问题 2: EPUB 转换失败

**症状**：
```
Conversion failed: Invalid EPUB structure
```

**可能原因**：
- EPUB 文件损坏
- EPUB 不符合标准
- 包含不支持的DRM

**解决方案**：

1. 验证 EPUB 文件：
```bash
# 使用 epubcheck 验证（需要安装）
epubcheck book.epub
```

2. 尝试用 Calibre GUI 手动转换：
```bash
# 打开 Calibre，添加书籍并转换
calibre
```

3. 移除 DRM（如果合法）：
- 使用 Calibre DRM Removal 插件
- 注意：仅处理自己购买的合法书籍

---

### 问题 3: PDF 转换质量差

**症状**：
- 转换后文字乱码
- 图片丢失
- 排版混乱

**原因**：
- PDF 是扫描版（图片PDF）
- PDF 包含特殊字体
- 复杂排版

**解决方案**：

1. 检查原始PDF类型：
```bash
pdfinfo book.pdf | grep "Pages"
```

2. 对于扫描版PDF，使用OCR：
```bash
# 需要安装 ocrmypdf
pip install ocrmypdf
ocrmypdf input.pdf output.pdf
```

3. 调整转换参数（通过API）：
```python
# 未来版本将支持高级参数
response = requests.post(
    'http://localhost:8000/api/convert',
    files={'file': f},
    data={
        'target_format': 'epub',
        'preserve_cover': 'true',
        'enable_heuristics': 'true'
    }
)
```

---

### 问题 4: 转换超时

**症状**：
```
Conversion timeout after 5 minutes
```

**原因**：
- 文件过大（>50MB）
- 文件结构复杂
- 系统资源不足

**解决方案**：

1. 检查文件大小：
```bash
ls -lh book.epub
```

2. 分割大文件（使用Calibre）：
```bash
# 在Calibre中编辑书籍，拆分为多个文件
```

3. 增加超时时间（修改配置）：
```python
# backend/src/config/settings.py
CONVERSION_TIMEOUT = 600  # 10分钟
```

4. 增加Docker内存限制：
```yaml
# docker-compose.yml
services:
  ebook-ai:
    deploy:
      resources:
        limits:
          memory: 4G  # 增加到4GB
```

---

## AI 服务问题

### 问题 1: AI API 密钥未配置

**症状**：
```json
{
  "detail": "AI processing failed: deepseek API key not configured"
}
```

**解决方案**：

1. 检查环境变量：
```bash
# 查看当前配置
cat .env | grep API_KEY

# 或在Docker容器中
docker exec ebook-ai env | grep API_KEY
```

2. 配置API密钥：
```bash
# 编辑 .env 文件
nano .env

# 添加或修改
DEEPSEEK_API_KEY=your-api-key-here
OPENAI_API_KEY=your-api-key-here
CLAUDE_API_KEY=your-api-key-here
```

3. 重启服务：
```bash
docker-compose restart
```

4. 验证配置：
```bash
curl http://localhost:8000/api/ai/providers
```

---

### 问题 2: AI 请求超时

**症状**：
```
AI processing failed: API request timed out
```

**原因**：
- 网络连接问题
- AI服务响应慢
- 输入文本过长

**解决方案**：

1. 检查网络连接：
```bash
# 测试API可达性
curl -I https://api.deepseek.com
curl -I https://api.openai.com
```

2. 使用代理（如需要）：
```bash
# 设置代理
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port

# 或在.env中配置
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=http://proxy:port
```

3. 减少输入文本长度：
```python
# 文本自动截断至2000字符
text = text[:2000]
```

4. 切换到更快的提供商：
```bash
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "...",
    "provider": "groq"  # Groq通常更快
  }'
```

---

### 问题 3: AI 返回错误

**症状**：
```
HTTP 401: Invalid API key
HTTP 429: Rate limit exceeded
HTTP 500: Internal server error
```

**解决方案**：

HTTP 401（无效密钥）：
```bash
# 验证API密钥
curl https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer your-api-key"
```

HTTP 429（速率限制）：
```bash
# 等待一段时间后重试
# 或升级API计划
# 或切换到其他提供商
```

HTTP 500（服务器错误）：
```bash
# 检查AI服务商状态页面
# 稍后重试
```

---

## 批量转换问题

### 问题 1: 批量任务卡住

**症状**：
```json
{
  "status": "processing",
  "completed_files": 2,
  "total_files": 10
}
```

**诊断**：

1. 查看详细状态：
```bash
curl http://localhost:8000/api/batch/status/batch-id | jq '.tasks[] | select(.status == "processing" or .status == "failed")'
```

2. 检查日志：
```bash
docker-compose logs -f --tail=100
```

**解决方案**：

1. 检查单个失败任务：
```bash
# 查看失败任务的错误信息
curl http://localhost:8000/api/batch/status/batch-id | jq '.tasks[] | select(.status == "failed")'
```

2. 手动转换失败的文件：
```bash
curl -X POST http://localhost:8000/api/convert \
  -F "file=@failed_file.epub" \
  -F "target_format=pdf"
```

3. 清理卡住的批次：
```bash
curl -X POST http://localhost:8000/api/batch/cleanup
```

---

### 问题 2: 并发转换数量限制

**症状**：
批量转换速度慢，同时只处理3个文件。

**原因**：
默认并发限制为3，防止资源耗尽。

**解决方案**：

修改并发限制（需要修改代码）：
```python
# backend/src/services/batch_conversion_service.py
self.max_concurrent_conversions = 5  # 增加到5
```

注意：
- 增加并发会增加内存和CPU使用
- 建议根据服务器资源调整
- Docker环境需要相应增加资源限制

---

## 性能问题

### 问题 1: 转换速度慢

**诊断**：

1. 检查系统资源：
```bash
# CPU和内存使用
docker stats ebook-ai

# 磁盘I/O
iostat -x 1
```

2. 检查文件大小：
```bash
du -sh uploads/* outputs/*
```

**优化方案**：

1. 增加Docker资源：
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

2. 使用SSD存储：
```yaml
volumes:
  - /path/to/ssd/uploads:/app/uploads
  - /path/to/ssd/outputs:/app/outputs
```

3. 定期清理临时文件：
```bash
curl -X POST http://localhost:8000/api/cleanup/run
```

---

### 问题 2: 内存使用过高

**症状**：
```
OOMKilled: Container killed due to out of memory
```

**解决方案**：

1. 增加Docker内存限制：
```bash
# 检查当前限制
docker inspect ebook-ai | grep Memory

# 修改 docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # 增加到4GB
```

2. 减少并发转换数：
```python
# 从5减少到3
self.max_concurrent_conversions = 3
```

3. 实施文件大小限制：
```python
# 限制上传文件大小
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
```

---

## Docker 相关问题

### 问题 1: 镜像构建失败

**症状**：
```
ERROR: failed to solve: process "/bin/sh -c..." did not complete successfully
```

**解决方案**：

1. 清理Docker缓存：
```bash
docker system prune -a
docker builder prune
```

2. 重新构建：
```bash
docker-compose build --no-cache
docker-compose up -d
```

3. 检查网络连接：
```bash
# 测试能否访问包源
curl -I https://pypi.org
curl -I https://registry.npmjs.org
```

---

### 问题 2: 容器频繁重启

**诊断**：
```bash
# 查看容器状态
docker ps -a

# 查看重启次数
docker inspect ebook-ai | grep RestartCount

# 查看退出代码
docker inspect ebook-ai | grep ExitCode
```

**常见退出代码**：
- 0：正常退出
- 1：应用错误
- 137：内存不足（OOMKilled）
- 139：段错误

**解决方案**：

查看详细日志：
```bash
docker logs ebook-ai --tail=100
docker-compose logs -f
```

---

## 日志分析

### 访问日志

**Docker环境**：
```bash
# 查看所有日志
docker-compose logs

# 实时查看
docker-compose logs -f

# 查看特定服务
docker-compose logs ebook-ai

# 查看最近100行
docker-compose logs --tail=100 ebook-ai
```

**本地开发**：
```bash
# 日志文件位置
ls logs/

# 查看日志
tail -f logs/ebook-ai.log
```

### 日志级别

修改日志级别以获取更多信息：

```bash
# .env 文件
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### 常见日志模式

**成功的转换**：
```
INFO - Conversion completed successfully: book.epub -> book.pdf
```

**文件上传**：
```
INFO - File uploaded: book.epub (size: 2.5MB)
```

**AI请求**：
```
INFO - AI summary generated: provider=deepseek, time=1.23s
```

**错误日志**：
```
ERROR - Conversion failed: Calibre error - Invalid EPUB structure
ERROR - AI processing failed: API key not configured
```

---

## 获取帮助

如果问题仍未解决：

1. **查看详细文档**：
   - [API Reference](../api/reference.md)
   - [部署指南](deployment.md)
   - [AI配置](ai-configuration.md)
   - [常见问题](faq.md)

2. **搜索已知问题**：
   - [GitHub Issues](https://github.com/YOUR_USERNAME/EBookAI/issues)

3. **提交问题**：
   - 使用 Issue 模板提交详细的问题报告
   - 包含日志、配置和重现步骤

4. **社区支持**：
   - GitHub Discussions
   - 相关论坛

---

## 调试技巧

### 启用调试模式

```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### 使用 API 测试工具

**Postman**：
1. 导入 OpenAPI spec: http://localhost:8000/openapi.json
2. 测试所有API端点

**HTTPie**：
```bash
# 更友好的HTTP客户端
pip install httpie

# 使用示例
http POST localhost:8000/api/convert file@book.epub target_format=pdf
```

### Python 调试

```python
# 添加断点
import pdb; pdb.set_trace()

# 或使用 ipython
from IPython import embed; embed()
```

---

**文档更新日期**: 2024-10-13
**版本**: 1.0.0
