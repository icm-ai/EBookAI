# EBookAI

AI增强的电子书处理平台

## 特性

- 🔄 支持EPUB/PDF格式转换
- 🤖 AI驱动的文本摘要生成（支持OpenAI兼容与Anthropic兼容API）
- 🌐 现代化的React界面
- 🐳 基于Docker的开发环境
- 🔧 通用AI提供商支持（自动发现任何兼容API）
- ⚙️ 灵活的配置管理系统

## 快速开始

### 环境要求

- Docker
- Docker Compose

### 启动开发环境

```bash
# 克隆项目
git clone <repository-url>
cd EBookAI

# 配置环境变量
cp .env.example .env
# 编辑.env文件，配置AI API密钥（至少一个）
# 推荐使用DeepSeek（性价比高）

# 启动开发环境
./start_dev.sh
```

服务将在以下地址启动：

- **前端**: <http://localhost:3000>
- **后端API**: <http://localhost:8000>
- **API文档**: <http://localhost:8000/docs>

### AI API配置

支持两种API类型，**至少需要配置一个提供商**：

#### OpenAI兼容API

支持所有使用OpenAI格式的API服务：

| 提供商 | 特点 | 配置变量 |
|-------|------|----------|
| 🌟 **DeepSeek** | 高性价比，中英文优秀 | `DEEPSEEK_API_KEY` |
| 🔥 **OpenAI** | 功能强大，生态完善 | `OPENAI_API_KEY` |
| 🚀 **Moonshot** | 国产优秀模型，长上下文 | `MOONSHOT_API_KEY` |
| ⚡ **Groq** | 超快推理速度 | `GROQ_API_KEY` |

#### Anthropic兼容API

支持所有使用Anthropic格式的API服务：

| 提供商 | 特点 | 配置变量 |
|-------|------|----------|
| 🧠 **Claude** | 长文本处理强 | `CLAUDE_API_KEY` |

系统支持自动发现任何符合 `{PROVIDER}_API_KEY` 格式的环境变量。详细配置方法请参考 [AI API配置指南](docs/ai-configuration.md)。

### 停止服务

```bash
cd docker
docker-compose -f docker-compose.dev.yml down
```

## 项目结构

```plaintext
EBookAI/
├── backend/          # FastAPI后端
├── frontend/         # React前端
├── docker/           # Docker配置文件
├── uploads/          # 文件上传目录
├── outputs/          # 转换结果目录
└── docs/             # 项目文档
```

## 文档

### 📚 用户指南

- [AI API配置指南](docs/ai-configuration.md) - 配置OpenAI、DeepSeek等API
- [开发环境搭建](docs/development-setup.md) - 本地开发环境配置
- [API接口文档](docs/api-reference.md) - 完整API参考
- [环境变量配置](docs/environment-variables.md) - 所有配置选项

### 🔧 技术文档

- [Docker配置说明](docker/README.md) - 容器化部署指南
- [MVP开发规划](ebook_platform_mvp.md) - 最小可行产品计划
- [完整项目规划](ebook_platform_outline.md) - 项目整体架构

### 📖 更多文档

查看 [docs/](docs/) 目录获取完整文档列表。