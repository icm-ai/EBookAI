# AI API 配置指南

EBookAI 支持两种类型的AI API：OpenAI兼容API和Anthropic兼容API。系统可以自动发现环境变量中配置的任何兼容提供商。

## 支持的API类型

### 1. OpenAI兼容API

支持OpenAI格式的API接口，包括但不限于：

| 提供商 | 特点 | 推荐指数 | 官网 |
|-------|------|----------|------|
| 🌟 **DeepSeek** | 高性价比，中英文能力优秀 | ⭐⭐⭐⭐⭐ | [deepseek.com](https://platform.deepseek.com/) |
| 🔥 **OpenAI** | 功能强大，生态完善 | ⭐⭐⭐⭐ | [openai.com](https://platform.openai.com/) |
| 🚀 **Moonshot** | 国产优秀模型，长上下文 | ⭐⭐⭐⭐ | [moonshot.cn](https://platform.moonshot.cn/) |
| ⚡ **Groq** | 超快推理速度 | ⭐⭐⭐ | [groq.com](https://console.groq.com/) |
| 🤝 **Together** | 开源模型集合 | ⭐⭐⭐ | [together.ai](https://api.together.xyz/) |

### 2. Anthropic兼容API

支持Anthropic格式的API接口：

| 提供商 | 特点 | 推荐指数 | 官网 |
|-------|------|----------|------|
| 🧠 **Claude** | 长文本处理能力强 | ⭐⭐⭐⭐ | [anthropic.com](https://console.anthropic.com/) |

## 配置方法

### 方法一：环境变量配置（推荐）

#### 内置提供商配置

**OpenAI**
```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
```

**DeepSeek**
```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

**Claude**
```bash
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_BASE_URL=https://api.anthropic.com
CLAUDE_MODEL=claude-3-sonnet-20240229
```

#### 自动发现提供商配置

系统会自动发现以 `{PROVIDER}_API_KEY` 格式命名的环境变量：

**Moonshot**
```bash
MOONSHOT_API_KEY=your_moonshot_api_key_here
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
MOONSHOT_MODEL=moonshot-v1-8k
# 可选：MOONSHOT_API_TYPE=openai（默认值）
```

**Groq**
```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama3-8b-8192
```

**Together**
```bash
TOGETHER_API_KEY=your_together_api_key_here
TOGETHER_BASE_URL=https://api.together.xyz/v1
TOGETHER_MODEL=meta-llama/Llama-3-8b-chat-hf
```

**自定义Claude代理**
```bash
CUSTOM_CLAUDE_API_KEY=your_custom_claude_api_key_here
CUSTOM_CLAUDE_BASE_URL=https://your-claude-proxy.com
CUSTOM_CLAUDE_MODEL=claude-3-sonnet-20240229
CUSTOM_CLAUDE_API_TYPE=anthropic
```

### 方法二：配置文件

创建 `config/ai_config.json` 文件：

```json
{
  "providers": {
    "moonshot": {
      "api_key": "your_moonshot_api_key_here",
      "base_url": "https://api.moonshot.cn/v1",
      "model": "moonshot-v1-8k",
      "api_type": "openai"
    },
    "groq": {
      "api_key": "your_groq_api_key_here",
      "base_url": "https://api.groq.com/openai/v1",
      "model": "llama3-8b-8192",
      "api_type": "openai"
    }
  }
}
```

### 方法三：动态添加提供商

在代码中动态添加：

```python
from config import ai_config

ai_config.add_provider(
    name="custom_provider",
    api_key="your_api_key",
    base_url="https://api.example.com/v1",
    model="custom-model",
    api_type="openai"  # 或 "anthropic"
)
```

## API密钥获取指南

### DeepSeek

1. 访问 [DeepSeek平台](https://platform.deepseek.com/)
2. 注册并登录账户
3. 进入控制台创建API密钥
4. 复制密钥并设置环境变量

**配置示例：**
```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
DEFAULT_AI_PROVIDER=deepseek
```

### OpenAI

1. 访问 [OpenAI平台](https://platform.openai.com/)
2. 注册并登录账户
3. 进入 [API Keys页面](https://platform.openai.com/api-keys)
4. 点击 "Create new secret key"
5. 复制生成的API密钥

**配置示例：**
```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-3.5-turbo
```

### Moonshot

1. 访问 [Moonshot平台](https://platform.moonshot.cn/)
2. 注册并登录账户
3. 在控制台创建API密钥
4. 复制密钥

**配置示例：**
```bash
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
MOONSHOT_MODEL=moonshot-v1-8k
```

### Groq

1. 访问 [Groq控制台](https://console.groq.com/)
2. 注册并登录账户
3. 创建API密钥
4. 复制密钥

**配置示例：**
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama3-8b-8192
```

### Claude

1. 访问 [Anthropic控制台](https://console.anthropic.com/)
2. 注册并登录账户
3. 创建API密钥
4. 复制密钥

**配置示例：**
```bash
CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
CLAUDE_MODEL=claude-3-sonnet-20240229
```

## 配置优先级

配置按以下优先级加载：

1. **环境变量**（最高优先级）
2. **配置文件** (`config/ai_config.json`)
3. **默认值**（最低优先级）

## 使用说明

### 设置默认提供商

```bash
DEFAULT_AI_PROVIDER=deepseek
```

### 测试配置

启动应用后，可以通过以下API测试配置：

```bash
# 获取可用提供商
curl http://localhost:8000/api/ai/providers

# 测试特定提供商
curl http://localhost:8000/api/ai/providers/deepseek/test
```

### 在API中指定提供商

```bash
curl -X POST "http://localhost:8000/api/ai/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "要生成摘要的文本",
    "provider": "moonshot"
  }'
```

## 注意事项

1. **API密钥安全**: 绝对不要将API密钥提交到代码仓库
2. **环境变量格式**: 提供商名称必须与 `_API_KEY` 后缀配合使用
3. **API类型**: 只支持 `openai` 和 `anthropic` 两种API类型
4. **必需参数**: 自动发现的提供商必须同时设置 `BASE_URL` 和 `MODEL`
5. **代理设置**: 如需使用代理，请在Docker环境中配置 `HTTP_PROXY` 和 `HTTPS_PROXY`

## 故障排除

### 常见错误

1. **API密钥无效**: 检查密钥格式和有效性
2. **网络连接问题**: 检查网络连接和代理设置
3. **模型不支持**: 确认模型名称正确
4. **配置未生效**: 重启应用以加载新配置

### 调试命令

```bash
# 检查环境变量
docker exec ebook-ai-workspace env | grep -E "_API_KEY|_BASE_URL|_MODEL"

# 测试API连接
curl http://localhost:8000/api/ai/providers
```