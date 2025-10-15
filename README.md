# EBookAI

一个强大的 AI 增强电子书处理工具，支持多种格式转换和智能文本处理。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/react-18-blue.svg)](https://reactjs.org/)
[![GitHub stars](https://img.shields.io/github/stars/icm-ai/EBookAI?style=social)](https://github.com/icm-ai/EBookAI/stargazers)

## 特性

### 核心功能

- 📚 **多格式转换**：支持 EPUB、PDF、MOBI、AZW3、TXT 等主流电子书格式互转
- 🤖 **AI 智能处理**：集成多种 AI 提供商，支持文本摘要、内容优化等功能
- ⚡ **批量处理**：支持批量文件转换，提高工作效率
- 🎨 **现代化界面**：简洁直观的 Web 界面，支持拖拽上传和实时进度显示
- 🐳 **一键部署**：基于 Docker 的容器化部署，开箱即用

### 技术特点

- 🔧 **灵活配置**：支持多种 AI 提供商（OpenAI、Claude、DeepSeek 等）
- 🌐 **实时反馈**：WebSocket 实时推送转换进度
- 🛡️ **健壮性**：完善的错误处理和日志系统
- 📊 **监控**：内置健康检查和性能监控
- 🔒 **安全**：非 root 用户运行，文件自动清理

## 快速开始

### 使用 Docker 部署（推荐）

适合快速体验和生产环境部署。

#### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

#### 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/YOUR_USERNAME/EBookAI.git
cd EBookAI

# 2. 配置环境变量（可选，不配置 AI 功能也能使用格式转换）
cp .env.example .env
nano .env  # 编辑配置文件，添加 AI API 密钥

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

服务启动后访问：

- **Web 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

#### 停止服务

```bash
docker-compose down
```

### 本地开发环境

适合需要修改代码的开发者。

#### 环境要求

- Python 3.11+
- Node.js 18+
- Calibre（电子书转换引擎）

#### 安装 Calibre

```bash
# macOS
brew install calibre

# Ubuntu/Debian
sudo apt-get install calibre

# Windows
# 从 https://calibre-ebook.com/download 下载安装
```

#### 启动步骤

```bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd frontend/web
npm install
cd ../..

# 3. 配置环境变量
cp .env.example .env

# 4. 启动开发服务（使用脚本）
./start_dev.sh

# 或手动启动
# 终端 1 - 后端
cd backend
uvicorn src.main:app --reload --port 8000

# 终端 2 - 前端
cd frontend/web
npm start
```

访问地址：

- **前端**: http://localhost:3000
- **后端**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

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

系统支持自动发现任何符合 `{PROVIDER}_API_KEY` 格式的环境变量。详细配置方法请参考 [AI API配置指南](docs/guides/ai-configuration.md)。

**注意**：AI 功能是可选的，不配置 API 密钥也可以使用格式转换功能。

## 使用说明

### 基础转换

1. 访问 Web 界面 http://localhost:8000
2. 上传电子书文件（支持拖拽）
3. 选择目标格式
4. 点击转换并等待完成
5. 下载转换后的文件

### 批量转换

1. 选择多个文件上传
2. 选择统一的目标格式
3. 系统会自动创建批量任务
4. 可在界面查看每个文件的转换进度
5. 完成后批量下载

### AI 功能

前提：需要配置至少一个 AI 提供商的 API 密钥。

1. 上传或粘贴文本内容
2. 选择 AI 功能（摘要、优化等）
3. 等待 AI 处理完成
4. 查看或下载处理结果

## 支持的格式

| 输入格式 | 输出格式 | 说明 |
|---------|---------|------|
| EPUB | PDF, MOBI, AZW3, TXT | 标准电子书格式 |
| PDF | EPUB, TXT | 可能需要 OCR |
| MOBI | EPUB, PDF, TXT | Kindle 格式 |
| AZW3 | EPUB, PDF, TXT | Kindle 格式 |
| TXT | EPUB, PDF | 纯文本 |

**转换质量说明**：

- EPUB → PDF：高质量，保留排版
- PDF → EPUB：质量取决于源 PDF 类型（扫描版效果较差）
- MOBI/AZW3 → 其他格式：高质量
- TXT → 其他格式：基础排版

## 项目结构

```plaintext
EBookAI/
├── backend/                    # 后端服务
│   ├── src/
│   │   ├── api/               # API 路由
│   │   ├── services/          # 核心业务逻辑
│   │   ├── utils/             # 工具函数
│   │   └── main.py            # 应用入口
│   └── tests/                 # 测试文件
├── frontend/web/              # Web 前端
│   ├── src/
│   │   ├── components/        # React 组件
│   │   └── services/          # API 调用
│   └── public/
├── docker/                    # Docker 配置
├── uploads/                   # 上传文件临时存储
├── outputs/                   # 转换结果存储
└── docs/                      # 项目文档
```

## 故障排查

### 常见问题

**1. Docker 启动失败**

```bash
# 检查 Docker 服务状态
docker ps

# 查看容器日志
docker-compose logs ebook-ai

# 重新构建镜像
docker-compose build --no-cache
```

**2. 转换失败**

- 检查文件格式是否受支持
- 查看后端日志：`docker-compose logs -f`
- 确认 Calibre 是否正常安装
- 检查磁盘空间是否充足

**3. AI 功能不可用**

- 确认已配置 API 密钥
- 检查 API 密钥是否有效
- 查看网络连接（部分地区可能需要代理）
- 检查 API 配额是否用完

**4. 前端无法访问**

- 确认端口 8000 未被占用
- 检查防火墙设置
- 使用 `curl http://localhost:8000/health` 测试后端

### 获取帮助

- 查看 [详细文档](docs/)
- 提交 [Issue](https://github.com/YOUR_USERNAME/EBookAI/issues)
- 查看 [常见问题](docs/guides/faq.md)

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m 'Add some feature'`
4. 推送到分支：`git push origin feature/your-feature`
5. 提交 Pull Request

详细指南请查看 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 开发路线图

- [x] 基础格式转换（EPUB、PDF、MOBI、AZW3）
- [x] AI 文本摘要
- [x] 批量转换
- [x] WebSocket 实时进度
- [x] Docker 部署
- [x] 文件自动清理机制
- [ ] 更多 AI 功能（翻译、校对）
- [ ] 桌面应用版本
- [ ] 高级排版选项
- [ ] 云存储集成

详细的项目状态和规划请查看：[项目管理文档](project-docs/)

## 技术栈

### 后端

- Python 3.11+
- FastAPI - 现代 Web 框架
- Calibre - 电子书转换引擎
- OpenAI/Anthropic API - AI 集成

### 前端

- React 18
- WebSocket - 实时通信
- Axios - HTTP 客户端

### 基础设施

- Docker & Docker Compose
- Debian 12 Slim - 基础镜像

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 致谢

- [Calibre](https://calibre-ebook.com/) - 强大的电子书管理工具
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Web 框架
- [React](https://reactjs.org/) - 用户界面库

---

如果这个项目对您有帮助，欢迎 Star ⭐

## Star History

<a href="https://star-history.com/#icm-ai/EBookAI&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=icm-ai/EBookAI&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=icm-ai/EBookAI&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=icm-ai/EBookAI&type=Date" />
  </picture>
</a>
