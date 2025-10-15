# API 接口文档

EBookAI 提供完整的 RESTful API 接口，支持电子书格式转换、批量处理、AI 文本处理和系统监控功能。

## 基础信息

- **基础URL**: `http://localhost:8000`
- **API前缀**: `/api`
- **API版本**: v1
- **数据格式**: JSON
- **字符编码**: UTF-8
- **交互式文档**: http://localhost:8000/docs

## 认证

当前版本无需认证，所有接口均可直接访问。适合本地部署和私有环境使用。

## 通用响应格式

### 成功响应
```json
{
  "status": "success",
  "data": {
    // 响应数据
  }
}
```

### 错误响应
```json
{
  "detail": "错误描述信息"
}
```

## 目录

- [1. 健康检查接口](#1-健康检查接口)
- [2. 文件转换接口](#2-文件转换接口)
- [3. 批量转换接口](#3-批量转换接口)
- [4. AI 服务接口](#4-ai-服务接口)
- [5. 文件清理接口](#5-文件清理接口)
- [6. 错误代码](#错误代码)
- [7. SDK 示例](#sdk-示例)

---

## 1. 健康检查接口

### 1.1 基础健康检查

检查服务基本运行状态。

**请求**
```http
GET /api/health
```

**响应**
```json
{
  "status": "healthy",
  "timestamp": "2024-10-13T12:00:00Z",
  "service": "EBookAI",
  "version": "1.0.0"
}
```

**示例**
```bash
curl http://localhost:8000/api/health
```

---

### 1.2 详细健康检查

检查所有服务组件的健康状态。

**请求**
```http
GET /api/health/detailed
```

**响应**
```json
{
  "status": "healthy",
  "timestamp": "2024-10-13T12:00:00Z",
  "service": "EBookAI",
  "version": "1.0.0",
  "components": {
    "conversion_service": {
      "status": "healthy",
      "message": "Conversion service is operational"
    },
    "batch_conversion_service": {
      "status": "healthy",
      "message": "Batch conversion service is operational",
      "active_batches": 2
    },
    "ai_service": {
      "status": "healthy",
      "message": "AI service configured",
      "available_providers": ["deepseek", "openai"],
      "default_provider": "deepseek"
    }
  },
  "check_duration": 0.123
}
```

**状态说明**
- `healthy`: 服务正常运行
- `degraded`: 部分功能不可用
- `unhealthy`: 服务存在严重问题

**示例**
```bash
curl http://localhost:8000/api/health/detailed
```

---

### 1.3 系统指标

获取系统运行指标和统计信息。

**请求**
```http
GET /api/health/metrics
```

**响应**
```json
{
  "timestamp": "2024-10-13T12:00:00Z",
  "batch_conversion": {
    "active_batches": 3,
    "total_batches_processed": 150,
    "average_processing_time": 45.2
  },
  "ai_service": {
    "configured_providers": 2,
    "default_provider": "deepseek",
    "total_requests": 1000,
    "success_rate": 98.5
  },
  "system": {
    "uptime": "24h 30m",
    "memory_usage": "512MB",
    "cpu_usage": "15%"
  }
}
```

**示例**
```bash
curl http://localhost:8000/api/health/metrics
```

---

### 1.4 就绪检查

检查服务是否准备好接收请求（Kubernetes Readiness Probe）。

**请求**
```http
GET /api/health/readiness
```

**响应**
```json
{
  "status": "ready",
  "timestamp": "2024-10-13T12:00:00Z",
  "message": "Service is ready to accept requests"
}
```

**示例**
```bash
curl http://localhost:8000/api/health/readiness
```

---

### 1.5 存活检查

检查服务进程是否仍在运行（Kubernetes Liveness Probe）。

**请求**
```http
GET /api/health/liveness
```

**响应**
```json
{
  "status": "alive",
  "timestamp": "2024-10-13T12:00:00Z",
  "message": "Service is alive"
}
```

**示例**
```bash
curl http://localhost:8000/api/health/liveness
```

---

## 2. 文件转换接口

### 2.1 单文件转换

将上传的电子书文件转换为指定格式。

**请求**
```http
POST /api/convert
Content-Type: multipart/form-data
```

**参数**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| file | file | 是 | 要转换的文件 |
| target_format | string | 是 | 目标格式（pdf/epub/mobi/azw3/txt） |

**支持的格式转换**
| 输入格式 | 输出格式 |
|---------|---------|
| EPUB | PDF, MOBI, AZW3, TXT |
| PDF | EPUB, TXT |
| MOBI | EPUB, PDF, TXT |
| AZW3 | EPUB, PDF, TXT |
| TXT | EPUB, PDF |

**响应**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "output_file": "converted_book_550e8400.pdf",
  "target_format": "pdf",
  "original_filename": "book.epub",
  "conversion_time": 3.45,
  "message": "Conversion completed successfully"
}
```

**示例**
```bash
curl -X POST "http://localhost:8000/api/convert" \
  -F "file=@book.epub" \
  -F "target_format=pdf"
```

**Python示例**
```python
import requests

with open('book.epub', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/convert',
        files={'file': f},
        data={'target_format': 'pdf'}
    )

result = response.json()
print(f"转换完成: {result['output_file']}")
```

---

### 2.2 文件下载

下载转换后的文件。

**请求**
```http
GET /api/download/{filename}
```

**参数**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| filename | string | 是 | 文件名（从转换响应获取） |

**响应**
- Content-Type: application/octet-stream
- 文件二进制流

**示例**
```bash
# 下载文件
curl -O "http://localhost:8000/api/download/converted_book_550e8400.pdf"

# 指定输出文件名
curl -o "my_book.pdf" "http://localhost:8000/api/download/converted_book_550e8400.pdf"
```

---

## 3. 批量转换接口

### 3.1 创建批量转换任务

批量转换多个文件为相同格式。

**请求**
```http
POST /api/batch/convert
Content-Type: multipart/form-data
```

**参数**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| files | file[] | 是 | 要转换的文件列表 |
| target_format | string | 是 | 目标格式 |

**响应**
```json
{
  "batch_id": "batch-123e4567",
  "total_files": 5,
  "status": "pending",
  "tasks": [
    {
      "task_id": "task-001",
      "file_path": "/uploads/book1.epub",
      "target_format": "pdf",
      "status": "pending"
    },
    {
      "task_id": "task-002",
      "file_path": "/uploads/book2.epub",
      "target_format": "pdf",
      "status": "pending"
    }
  ],
  "created_at": 1697234567.89
}
```

**示例**
```bash
curl -X POST "http://localhost:8000/api/batch/convert" \
  -F "files=@book1.epub" \
  -F "files=@book2.epub" \
  -F "files=@book3.epub" \
  -F "target_format=pdf"
```

**Python示例**
```python
import requests

files = [
    ('files', open('book1.epub', 'rb')),
    ('files', open('book2.epub', 'rb')),
    ('files', open('book3.epub', 'rb'))
]

response = requests.post(
    'http://localhost:8000/api/batch/convert',
    files=files,
    data={'target_format': 'pdf'}
)

batch = response.json()
print(f"批量任务ID: {batch['batch_id']}")
```

---

### 3.2 查询批量任务状态

查询批量转换任务的执行状态。

**请求**
```http
GET /api/batch/status/{batch_id}
```

**参数**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| batch_id | string | 是 | 批量任务ID |

**响应**
```json
{
  "batch_id": "batch-123e4567",
  "total_files": 5,
  "completed_files": 3,
  "failed_files": 1,
  "status": "processing",
  "tasks": [
    {
      "task_id": "task-001",
      "status": "completed",
      "output_file": "/outputs/book1.pdf"
    },
    {
      "task_id": "task-002",
      "status": "failed",
      "error_message": "Unsupported format"
    },
    {
      "task_id": "task-003",
      "status": "processing"
    }
  ],
  "created_at": 1697234567.89,
  "completed_at": 0
}
```

**任务状态**
- `pending`: 等待处理
- `processing`: 正在处理
- `completed`: 已完成
- `failed`: 失败

**示例**
```bash
curl http://localhost:8000/api/batch/status/batch-123e4567
```

---

### 3.3 列出所有批量任务

获取所有活跃的批量转换任务列表。

**请求**
```http
GET /api/batch/list
```

**响应**
```json
[
  {
    "batch_id": "batch-123e4567",
    "total_files": 5,
    "completed_files": 5,
    "failed_files": 0,
    "status": "completed",
    "created_at": 1697234567.89
  },
  {
    "batch_id": "batch-789abcde",
    "total_files": 3,
    "completed_files": 1,
    "failed_files": 0,
    "status": "processing",
    "created_at": 1697234600.12
  }
]
```

**示例**
```bash
curl http://localhost:8000/api/batch/list
```

---

### 3.4 清理已完成的批量任务

清理已完成的批量转换任务，释放内存。

**请求**
```http
POST /api/batch/cleanup
```

**响应**
```json
{
  "message": "Cleanup completed",
  "removed_batches": 3
}
```

**示例**
```bash
curl -X POST http://localhost:8000/api/batch/cleanup
```

---

## 4. AI 服务接口

### 4.1 文本摘要生成

使用 AI 生成文本摘要。

**请求**
```http
POST /api/ai/summary
Content-Type: application/json
```

**请求体**
```json
{
  "text": "要生成摘要的文本内容...",
  "max_length": 300,
  "provider": "deepseek"
}
```

**参数**
| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| text | string | 是 | - | 输入文本（最多2000字符） |
| max_length | integer | 否 | 300 | 摘要最大长度 |
| provider | string | 否 | 默认提供商 | AI提供商名称 |

**响应**
```json
{
  "summary": "这是生成的摘要内容...",
  "original_length": 1500,
  "summary_length": 280,
  "provider": "deepseek",
  "model": "deepseek-chat",
  "processing_time": 1.23,
  "token_usage": {
    "prompt_tokens": 500,
    "completion_tokens": 100,
    "total_tokens": 600
  }
}
```

**示例**
```bash
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是一篇很长的文章内容，需要生成简洁的摘要...",
    "max_length": 200,
    "provider": "deepseek"
  }'
```

---

### 4.2 获取可用 AI 提供商

获取已配置且可用的 AI 服务提供商列表。

**请求**
```http
GET /api/ai/providers
```

**响应**
```json
{
  "providers": ["deepseek", "openai", "moonshot", "claude"],
  "default": "deepseek",
  "providers_info": {
    "deepseek": {
      "api_type": "openai",
      "model": "deepseek-chat"
    },
    "claude": {
      "api_type": "anthropic",
      "model": "claude-3-sonnet"
    }
  }
}
```

**支持的提供商**
- **OpenAI 兼容**: DeepSeek, OpenAI, Moonshot, Groq
- **Anthropic 兼容**: Claude

**示例**
```bash
curl http://localhost:8000/api/ai/providers
```

---

### 4.3 获取增强类型列表

获取支持的文本增强类型。

**请求**
```http
GET /api/ai/enhancement-types
```

**响应**
```json
{
  "types": [
    "improve_readability",
    "fix_grammar",
    "translate_to_chinese",
    "translate_to_english",
    "format_content"
  ]
}
```

**示例**
```bash
curl http://localhost:8000/api/ai/enhancement-types
```

---

## 5. 文件清理接口

### 5.1 获取清理状态

获取磁盘使用情况和文件统计信息。

**请求**
```http
GET /api/cleanup/status
```

**响应**
```json
{
  "disk_usage": {
    "uploads": {
      "total_files": 45,
      "total_size_mb": 234.5,
      "oldest_file_age_hours": 72.3
    },
    "outputs": {
      "total_files": 38,
      "total_size_mb": 189.2,
      "oldest_file_age_hours": 48.1
    }
  },
  "cleanup_config": {
    "max_age_hours": 24,
    "cleanup_interval_minutes": 60
  }
}
```

**示例**
```bash
curl http://localhost:8000/api/cleanup/status
```

---

### 5.2 手动执行清理

手动触发文件清理操作。

**请求**
```http
POST /api/cleanup/run
```

**响应**
```json
{
  "success": true,
  "files_removed": 15,
  "space_freed_mb": 87.3,
  "cleanup_time": 0.45,
  "details": {
    "uploads": {
      "files_removed": 8,
      "size_freed_mb": 45.2
    },
    "outputs": {
      "files_removed": 7,
      "size_freed_mb": 42.1
    }
  }
}
```

**示例**
```bash
curl -X POST http://localhost:8000/api/cleanup/run
```

---

## 错误代码

### HTTP 状态码

| 状态码 | 说明 | 常见原因 |
|--------|------|----------|
| 200 | 请求成功 | - |
| 400 | 请求参数错误 | 缺少必需参数、参数格式错误 |
| 404 | 资源不存在 | 文件未找到、批次ID不存在 |
| 422 | 验证错误 | 数据验证失败 |
| 500 | 服务器内部错误 | 转换失败、AI服务错误 |
| 503 | 服务不可用 | 服务暂时无法处理请求 |

### 常见错误示例

#### 1. 文件格式不支持
```json
{
  "detail": "Unsupported file format: .docx"
}
```

#### 2. AI API 密钥未配置
```json
{
  "detail": "AI processing failed: openai API key not configured"
}
```

#### 3. 文件未找到
```json
{
  "detail": "File not found: /outputs/nonexistent.pdf"
}
```

#### 4. 批次不存在
```json
{
  "detail": "Batch not found: invalid-batch-id"
}
```

#### 5. 文件过大
```json
{
  "detail": "File size exceeds maximum limit of 50MB"
}
```

#### 6. 转换失败
```json
{
  "detail": "Conversion failed: Calibre error - Invalid EPUB structure"
}
```

---

## 使用限制

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 最大文件大小 | 50MB | 单个文件上传限制 |
| AI 文本长度 | 2000 字符 | 摘要生成输入限制 |
| 批量文件数 | 无限制 | 但受并发转换限制 |
| 并发转换数 | 3 | 同时处理的转换任务数 |
| 转换超时 | 5 分钟 | 单个转换任务超时 |
| AI 请求超时 | 60 秒 | AI API 调用超时 |
| 文件保留时间 | 24 小时 | 默认自动清理时间 |

---

## SDK 示例

### Python

```python
import requests
from pathlib import Path

class EBookAIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def convert_file(self, file_path, target_format="pdf"):
        """转换单个文件"""
        with open(file_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/convert",
                files={'file': f},
                data={'target_format': target_format}
            )
        return response.json()

    def batch_convert(self, file_paths, target_format="pdf"):
        """批量转换文件"""
        files = [('files', open(fp, 'rb')) for fp in file_paths]
        response = self.session.post(
            f"{self.base_url}/api/batch/convert",
            files=files,
            data={'target_format': target_format}
        )
        return response.json()

    def get_batch_status(self, batch_id):
        """查询批量任务状态"""
        response = self.session.get(
            f"{self.base_url}/api/batch/status/{batch_id}"
        )
        return response.json()

    def generate_summary(self, text, max_length=300, provider=None):
        """生成AI摘要"""
        payload = {
            'text': text,
            'max_length': max_length
        }
        if provider:
            payload['provider'] = provider

        response = self.session.post(
            f"{self.base_url}/api/ai/summary",
            json=payload
        )
        return response.json()

    def health_check(self):
        """健康检查"""
        response = self.session.get(f"{self.base_url}/api/health")
        return response.json()

# 使用示例
client = EBookAIClient()

# 健康检查
health = client.health_check()
print(f"服务状态: {health['status']}")

# 单文件转换
result = client.convert_file('book.epub', 'pdf')
print(f"转换完成: {result['output_file']}")

# 批量转换
batch = client.batch_convert(
    ['book1.epub', 'book2.epub', 'book3.epub'],
    'pdf'
)
print(f"批量任务ID: {batch['batch_id']}")

# AI摘要
summary = client.generate_summary(
    "这是一篇很长的文章内容...",
    max_length=200,
    provider='deepseek'
)
print(f"摘要: {summary['summary']}")
```

### JavaScript/TypeScript

```javascript
class EBookAIClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async convertFile(file, targetFormat = 'pdf') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_format', targetFormat);

    const response = await fetch(`${this.baseUrl}/api/convert`, {
      method: 'POST',
      body: formData
    });
    return await response.json();
  }

  async batchConvert(files, targetFormat = 'pdf') {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('target_format', targetFormat);

    const response = await fetch(`${this.baseUrl}/api/batch/convert`, {
      method: 'POST',
      body: formData
    });
    return await response.json();
  }

  async getBatchStatus(batchId) {
    const response = await fetch(
      `${this.baseUrl}/api/batch/status/${batchId}`
    );
    return await response.json();
  }

  async generateSummary(text, maxLength = 300, provider = null) {
    const payload = { text, max_length: maxLength };
    if (provider) payload.provider = provider;

    const response = await fetch(`${this.baseUrl}/api/ai/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return await response.json();
  }

  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/api/health`);
    return await response.json();
  }
}

// 使用示例
const client = new EBookAIClient();

// 单文件转换
const fileInput = document.querySelector('#fileInput');
const result = await client.convertFile(fileInput.files[0], 'pdf');
console.log(`转换完成: ${result.output_file}`);

// 批量转换
const batch = await client.batchConvert(
  Array.from(fileInput.files),
  'pdf'
);
console.log(`批量任务ID: ${batch.batch_id}`);

// AI摘要
const summary = await client.generateSummary(
  '这是一篇很长的文章内容...',
  200,
  'deepseek'
);
console.log(`摘要: ${summary.summary}`);
```

### cURL 完整示例

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

# 健康检查
echo "=== 健康检查 ==="
curl "${BASE_URL}/api/health"

# 详细健康检查
echo "\n=== 详细健康检查 ==="
curl "${BASE_URL}/api/health/detailed"

# 单文件转换
echo "\n=== 单文件转换 ==="
curl -X POST "${BASE_URL}/api/convert" \
  -F "file=@book.epub" \
  -F "target_format=pdf"

# 批量转换
echo "\n=== 批量转换 ==="
curl -X POST "${BASE_URL}/api/batch/convert" \
  -F "files=@book1.epub" \
  -F "files=@book2.epub" \
  -F "files=@book3.epub" \
  -F "target_format=pdf"

# 查询批量状态
echo "\n=== 批量任务状态 ==="
BATCH_ID="batch-123e4567"
curl "${BASE_URL}/api/batch/status/${BATCH_ID}"

# AI摘要生成
echo "\n=== AI摘要 ==="
curl -X POST "${BASE_URL}/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是一篇很长的文章内容...",
    "max_length": 200,
    "provider": "deepseek"
  }'

# 获取可用AI提供商
echo "\n=== AI提供商列表 ==="
curl "${BASE_URL}/api/ai/providers"

# 文件清理状态
echo "\n=== 清理状态 ==="
curl "${BASE_URL}/api/cleanup/status"

# 执行清理
echo "\n=== 执行清理 ==="
curl -X POST "${BASE_URL}/api/cleanup/run"
```

---

## 开发工具

### Swagger UI
访问 http://localhost:8000/docs 查看交互式 API 文档，可以直接在浏览器中测试 API。

### ReDoc
访问 http://localhost:8000/redoc 查看 ReDoc 格式的 API 文档，提供更友好的阅读体验。

### OpenAPI 规范
访问 http://localhost:8000/openapi.json 获取 OpenAPI 3.0 规范文件，可用于生成客户端SDK。

---

## WebSocket 接口

### 实时进度推送

用于获取转换任务的实时进度更新。

**连接**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/progress/{task_id}');

ws.onmessage = function(event) {
  const progress = JSON.parse(event.data);
  console.log(`进度: ${progress.percentage}%`);
};
```

**消息格式**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "percentage": 45,
  "message": "Converting page 45 of 100"
}
```

---

## 最佳实践

### 1. 错误处理
始终检查响应状态码并处理错误：

```python
try:
    result = client.convert_file('book.epub', 'pdf')
except requests.HTTPError as e:
    if e.response.status_code == 400:
        print("请求参数错误")
    elif e.response.status_code == 500:
        print("服务器错误，请稍后重试")
```

### 2. 批量操作优化
对于大量文件，使用批量转换而非多次单文件转换：

```python
# 推荐
batch = client.batch_convert(file_list, 'pdf')

# 不推荐
for file in file_list:
    client.convert_file(file, 'pdf')  # 效率低
```

### 3. 轮询状态
查询批量任务状态时使用合理的轮询间隔：

```python
import time

batch_id = batch['batch_id']
while True:
    status = client.get_batch_status(batch_id)
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(5)  # 5秒轮询间隔
```

### 4. 文件清理
定期检查并清理不需要的文件：

```python
# 获取清理状态
status = requests.get(f"{base_url}/api/cleanup/status").json()
if status['disk_usage']['total_size_mb'] > 1000:  # 超过1GB
    requests.post(f"{base_url}/api/cleanup/run")
```

---

## 版本历史

### v1.0.0 (2024-10-13)
- 初始版本发布
- 支持 EPUB、PDF、MOBI、AZW3、TXT 格式转换
- AI 文本摘要功能
- 批量转换支持
- 自动文件清理
- 完整的健康检查接口
- OpenAI 和 Anthropic 兼容 API 支持
- WebSocket 实时进度推送

---

## 技术支持

- **GitHub Issues**: https://github.com/YOUR_USERNAME/EBookAI/issues
- **常见问题**: [FAQ](../guides/faq.md)
- **部署指南**: [Deployment Guide](../guides/deployment.md)
- **AI 配置**: [AI Configuration](../guides/ai-configuration.md)

---

**文档更新日期**: 2024-10-13
**API 版本**: v1.0.0
