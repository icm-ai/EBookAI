# API 接口文档

EBookAI 提供RESTful API接口，支持电子书格式转换和AI文本处理功能。

## 基础信息

- **基础URL**: `http://localhost:8000`
- **API版本**: v1
- **数据格式**: JSON
- **字符编码**: UTF-8

## 认证

当前版本无需认证，所有接口均可直接访问。

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

## 接口列表

### 1. 系统接口

#### 1.1 健康检查
检查服务运行状态。

**请求**
```
GET /health
```

**响应**
```json
{
  "status": "healthy"
}
```

#### 1.2 根路径
获取API基本信息。

**请求**
```
GET /
```

**响应**
```json
{
  "message": "Welcome to EBookAI API"
}
```

### 2. 文件转换接口

#### 2.1 文件转换
将上传的电子书文件转换为指定格式。

**请求**
```
POST /api/convert
Content-Type: multipart/form-data
```

**参数**
- `file` (file, required): 要转换的文件
- `target_format` (string, optional): 目标格式，默认为"pdf"

**支持的格式**
- 输入: `epub`, `pdf`
- 输出: `epub`, `pdf`

**响应**
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "output_file": "converted_filename.pdf",
  "message": "Conversion completed successfully"
}
```

**示例**
```bash
curl -X POST "http://localhost:8000/api/convert" \
  -F "file=@book.epub" \
  -F "target_format=pdf"
```

#### 2.2 文件下载
下载转换后的文件。

**请求**
```
GET /api/download/{filename}
```

**参数**
- `filename` (string, required): 文件名

**响应**
- 文件二进制流

**示例**
```bash
curl -O "http://localhost:8000/api/download/converted_file.pdf"
```

#### 2.3 转换状态查询
查询转换任务状态（当前为简化实现）。

**请求**
```
GET /api/status/{task_id}
```

**参数**
- `task_id` (string, required): 任务ID

**响应**
```json
{
  "task_id": "uuid-string",
  "status": "completed"
}
```

### 3. AI 服务接口

#### 3.1 文本摘要生成
使用AI生成文本摘要。

**请求**
```
POST /api/ai/summary
Content-Type: application/json
```

**请求体**
```json
{
  "text": "要生成摘要的文本内容",
  "max_length": 300,
  "provider": "deepseek"
}
```

**参数**
- `text` (string, required): 输入文本
- `max_length` (integer, optional): 摘要最大长度，默认300
- `provider` (string, optional): AI提供商，支持任何已配置的OpenAI兼容或Anthropic兼容提供商

**响应**
```json
{
  "summary": "生成的摘要内容",
  "original_length": 1500,
  "summary_length": 280,
  "provider": "deepseek"
}
```

**示例**
```bash
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是一篇很长的文章内容...",
    "max_length": 200,
    "provider": "deepseek"
  }'
```

#### 3.2 获取可用AI提供商
获取已配置且可用的AI服务提供商列表。

**请求**
```
GET /api/ai/providers
```

**响应**
```json
{
  "providers": ["deepseek", "openai", "moonshot", "claude"],
  "default": "deepseek"
}
```

注：返回的提供商列表包括所有已配置API密钥的OpenAI兼容和Anthropic兼容提供商。

#### 3.3 测试AI提供商
测试指定AI提供商的连接状态。

**请求**
```
GET /api/ai/providers/{provider}/test
```

**参数**
- `provider` (string, required): AI提供商名称

**响应（成功）**
```json
{
  "provider": "deepseek",
  "status": "working",
  "test_summary": "测试摘要内容"
}
```

**响应（失败）**
```json
{
  "provider": "openai",
  "status": "error",
  "error": "API key not configured"
}
```

## 错误代码

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 常见错误示例

#### 文件格式不支持
```json
{
  "detail": "Unsupported file format"
}
```

#### AI API密钥未配置
```json
{
  "detail": "AI processing failed: openai API key not configured"
}
```

#### 文件未找到
```json
{
  "detail": "File not found"
}
```

## 使用限制

- 最大文件大小: 50MB
- 文本长度限制: 2000字符（AI处理）
- 支持的文件格式: EPUB, PDF
- 超时时间: 5分钟（转换）, 30秒（AI请求）

## SDK 示例

### Python
```python
import requests

# 文件转换
with open('book.epub', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/convert',
        files={'file': f},
        data={'target_format': 'pdf'}
    )
result = response.json()

# AI摘要
response = requests.post(
    'http://localhost:8000/api/ai/summary',
    json={
        'text': '长文本内容...',
        'provider': 'deepseek'
    }
)
summary = response.json()
```

### JavaScript
```javascript
// 文件转换
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('target_format', 'pdf');

const response = await fetch('/api/convert', {
  method: 'POST',
  body: formData
});
const result = await response.json();

// AI摘要
const summaryResponse = await fetch('/api/ai/summary', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    text: '长文本内容...',
    provider: 'deepseek'
  })
});
const summary = await summaryResponse.json();
```

### cURL
```bash
# 文件转换
curl -X POST "http://localhost:8000/api/convert" \
  -F "file=@book.epub" \
  -F "target_format=pdf"

# AI摘要（使用DeepSeek）
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{"text":"长文本内容...","provider":"deepseek"}'

# AI摘要（使用Moonshot）
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{"text":"长文本内容...","provider":"moonshot"}'

# 获取可用提供商
curl "http://localhost:8000/api/ai/providers"

# 测试OpenAI兼容提供商
curl "http://localhost:8000/api/ai/providers/deepseek/test"

# 测试Anthropic兼容提供商
curl "http://localhost:8000/api/ai/providers/claude/test"
```

## 开发工具

### Swagger UI
访问 `http://localhost:8000/docs` 查看交互式API文档。

### ReDoc
访问 `http://localhost:8000/redoc` 查看ReDoc格式的API文档。

## 版本历史

- **v1.0.0**: 初始版本，支持基础转换和AI摘要功能
- 支持OpenAI兼容和Anthropic兼容API
- 自动发现任何符合标准格式的AI提供商
- 文件格式转换（EPUB ↔ PDF）