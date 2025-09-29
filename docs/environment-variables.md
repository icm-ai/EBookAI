# 环境变量配置

本文档列出了EBookAI项目中所有可用的环境变量及其说明。

## AI服务配置

### OpenAI

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `OPENAI_API_KEY` | 否* | "" | OpenAI API密钥 |
| `OPENAI_BASE_URL` | 否 | "https://api.openai.com/v1" | OpenAI API基础URL |
| `OPENAI_MODEL` | 否 | "gpt-3.5-turbo" | 默认使用的OpenAI模型 |

### DeepSeek

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEEPSEEK_API_KEY` | 否* | "" | DeepSeek API密钥 |
| `DEEPSEEK_BASE_URL` | 否 | "https://api.deepseek.com/v1" | DeepSeek API基础URL |
| `DEEPSEEK_MODEL` | 否 | "deepseek-chat" | 默认使用的DeepSeek模型 |

### Claude (Anthropic)

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `CLAUDE_API_KEY` | 否* | "" | Claude API密钥 |

*注：至少需要配置一个AI提供商的API密钥

### AI提供商选择

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEFAULT_AI_PROVIDER` | 否 | "openai" | 默认AI服务提供商 (openai/deepseek/claude) |

## 应用配置

### 开发环境

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `NODE_ENV` | 否 | "development" | Node.js环境模式 |
| `PYTHONPATH` | 否 | "/workspace/backend/src" | Python模块搜索路径 |

### 网络代理

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `HTTP_PROXY` | 否 | "" | HTTP代理地址 |
| `HTTPS_PROXY` | 否 | "" | HTTPS代理地址 |
| `http_proxy` | 否 | "" | HTTP代理地址（小写） |
| `https_proxy` | 否 | "" | HTTPS代理地址（小写） |

## 配置示例

### 完整的 .env 文件示例

```bash
# AI服务配置
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
OPENAI_MODEL="gpt-3.5-turbo"

DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
DEEPSEEK_MODEL="deepseek-chat"

CLAUDE_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 默认AI提供商
DEFAULT_AI_PROVIDER="deepseek"

# 开发环境配置
NODE_ENV="development"
PYTHONPATH="/workspace/backend/src"

# 代理配置（如果需要）
HTTP_PROXY="http://127.0.0.1:7878"
HTTPS_PROXY="http://127.0.0.1:7878"
```

### Docker开发环境配置

在 `docker-compose.dev.yml` 中：

```yaml
environment:
  # 从宿主机环境变量读取
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
  - CLAUDE_API_KEY=${CLAUDE_API_KEY}
  - DEFAULT_AI_PROVIDER=${DEFAULT_AI_PROVIDER:-deepseek}

  # 容器内配置
  - PYTHONPATH=/workspace/backend/src
  - NODE_ENV=development

  # 代理配置
  - HTTP_PROXY=http://host.docker.internal:7878
  - HTTPS_PROXY=http://host.docker.internal:7878
```

## 配置验证

### 检查环境变量

在容器中检查当前环境变量：

```bash
# 进入容器
docker exec -it ebook-ai-workspace bash

# 查看AI相关配置
env | grep -E "(OPENAI|DEEPSEEK|CLAUDE|DEFAULT_AI)"

# 查看完整环境变量
env | sort
```

### 配置文件检查

检查配置文件是否正确加载：

```bash
# 在容器中
python3 -c "
from config import ai_config
print('Available providers:', ai_config.get_available_providers())
print('Default provider:', ai_config.DEFAULT_AI_PROVIDER)
"
```

## 安全最佳实践

### 1. 使用 .env 文件

```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env 文件（不要提交到Git）
nano .env
```

### 2. Git忽略配置

确保 `.gitignore` 包含：

```gitignore
.env
.env.local
.env.*.local
config/ai_config.json
```

### 3. 生产环境配置

在生产环境中，建议使用：

- 容器编排工具的secrets管理
- 云服务商的密钥管理服务
- 专门的配置管理工具

### 4. 环境变量检查脚本

创建检查脚本 `scripts/check_env.py`：

```python
#!/usr/bin/env python3
import os

required_vars = {
    'AI_KEYS': ['OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'CLAUDE_API_KEY']
}

def check_environment():
    # 检查至少有一个AI API密钥
    ai_keys = [os.getenv(key) for key in required_vars['AI_KEYS']]
    if not any(ai_keys):
        print("❌ 错误: 至少需要配置一个AI API密钥")
        return False

    # 检查配置的密钥
    for key in required_vars['AI_KEYS']:
        value = os.getenv(key)
        if value:
            print(f"✅ {key}: {'*' * (len(value)-4)}{value[-4:]}")

    return True

if __name__ == "__main__":
    check_environment()
```

## 故障排除

### 常见问题

1. **环境变量未生效**
   - 检查 `.env` 文件是否在正确位置
   - 重启Docker容器
   - 检查变量名拼写

2. **API密钥无效**
   - 验证密钥格式
   - 检查账户状态
   - 确认密钥权限

3. **代理配置问题**
   - 检查代理地址格式
   - 确认代理服务可用
   - 验证网络连接

### 调试命令

```bash
# 查看容器环境变量
docker exec ebook-ai-workspace env

# 测试API连接
docker exec ebook-ai-workspace curl -s http://localhost:8000/api/ai/providers

# 查看应用日志
docker logs ebook-ai-workspace -f
```