# EBookAI 文档

欢迎来到 EBookAI 项目文档中心！这里提供完整的用户指南、开发文档和 API 参考。

## 📚 快速导航

### 用户指南

新用户从这里开始：

- **[部署指南](guides/deployment.md)** - 详细的 Docker 和手动部署说明
- **[AI 配置](guides/ai-configuration.md)** - 配置 OpenAI、Claude、DeepSeek 等 AI 服务
- **[环境变量](guides/environment-variables.md)** - 完整的配置选项说明
- **[常见问题](guides/faq.md)** - 使用过程中的常见问题解答

### 开发文档

贡献者和开发者参考：

- **[开发环境搭建](development/setup.md)** - 本地开发环境配置
- **[贡献指南](../CONTRIBUTING.md)** - 如何为项目做贡献
- **[项目架构](development/architecture.md)** - 技术架构说明（待添加）

### API 文档

- **[API 参考](api/reference.md)** - 完整的 REST API 文档
- **交互式文档** - 运行服务后访问 http://localhost:8000/docs

### 平台特定

- **[macOS 指南](platform/macos-quick-start.md)** - macOS 用户快速开始
- **[macOS 分析](platform/macos-analysis.md)** - macOS 原生应用分析

### 项目规划

历史规划文档（归档）：

- **[MVP 规划](planning/mvp.md)** - 最小可行产品计划
- **[项目大纲](planning/outline.md)** - 完整项目规划

## 🚀 快速开始

### 5 分钟快速部署

```bash
# 1. 克隆项目
git clone https://github.com/YOUR_USERNAME/EBookAI.git
cd EBookAI

# 2. 配置环境变量（可选）
cp .env.example .env

# 3. 使用 Docker 启动
docker-compose up -d

# 4. 访问应用
open http://localhost:8000
```

详细步骤请查看：[部署指南](guides/deployment.md)

## 📖 文档结构

```
docs/
├── guides/              # 用户指南
│   ├── deployment.md
│   ├── ai-configuration.md
│   ├── environment-variables.md
│   └── faq.md
├── development/         # 开发文档
│   └── setup.md
├── api/                 # API 文档
│   └── reference.md
├── platform/            # 平台特定
│   ├── macos-quick-start.md
│   └── macos-analysis.md
├── planning/            # 规划文档（归档）
│   ├── mvp.md
│   └── outline.md
└── README.md            # 本文件
```

## 🔗 外部链接

- **项目主页**: [GitHub Repository](https://github.com/YOUR_USERNAME/EBookAI)
- **问题追踪**: [GitHub Issues](https://github.com/YOUR_USERNAME/EBookAI/issues)
- **发布说明**: [Releases](https://github.com/YOUR_USERNAME/EBookAI/releases)
- **更新日志**: [CHANGELOG.md](../CHANGELOG.md)

## 📊 项目状态

查看项目当前进展和路线图：[PROJECT_STATUS.md](../PROJECT_STATUS.md)

## 💡 获取帮助

1. **查看文档** - 先浏览相关文档，大多数问题都有解答
2. **搜索 Issues** - 查看是否有人遇到过类似问题
3. **提问** - 在 [GitHub Discussions](https://github.com/YOUR_USERNAME/EBookAI/discussions) 提问
4. **报告 Bug** - 使用 [Issue 模板](https://github.com/YOUR_USERNAME/EBookAI/issues/new/choose)

## 🤝 贡献文档

发现文档错误或想要改进？

1. Fork 项目
2. 编辑 `docs/` 目录下的相关文件
3. 提交 Pull Request

查看完整指南：[CONTRIBUTING.md](../CONTRIBUTING.md)

---

**文档版本**: v0.2.0
**最后更新**: 2024-10-13
**维护者**: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
