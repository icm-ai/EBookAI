# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- 自动文件清理机制，定期清理临时文件
- 文件清理 API 端点（`/api/cleanup/run` 和 `/api/cleanup/status`）
- GitHub Issue 和 PR 模板
- CI/CD 工作流（代码质量检查、自动测试、Docker 构建）
- 完善的文档体系（贡献指南、部署指南、FAQ）
- 行为准则（CODE_OF_CONDUCT.md）

### 改进
- 增强 README，添加详细的使用说明和故障排查
- 优化环境变量配置示例

## [0.1.0] - 2024-10-01

### 新增
- 基础格式转换功能
  - 支持 EPUB、PDF、MOBI、AZW3、TXT 格式
  - 基于 Calibre 的高质量转换
- AI 文本处理功能
  - 多 AI 提供商支持（OpenAI、Claude、DeepSeek 等）
  - 文本摘要生成
  - 自动提供商发现机制
- 批量转换功能
  - 多文件同时处理
  - 批量任务管理
  - 任务状态查询
- Web 用户界面
  - 文件上传和下载
  - 实时进度显示（WebSocket）
  - 批量操作支持
- API 接口
  - RESTful API 设计
  - 自动生成的 API 文档（Swagger/OpenAPI）
  - 健康检查端点
- Docker 支持
  - 完整的 Docker 和 Docker Compose 配置
  - 多阶段构建优化镜像大小
  - 健康检查配置
- 监控和日志
  - 结构化日志记录
  - 性能监控中间件
  - 错误追踪
- 测试框架
  - pytest 测试配置
  - 基础单元测试和集成测试

### 文档
- 项目 README
- API 参考文档
- AI 配置指南
- 开发环境搭建指南
- 环境变量配置文档

## 版本说明

### [Unreleased]
正在开发中的功能，尚未发布。

### [0.1.0] - 初始版本
项目的第一个可用版本，包含核心功能和基础文档。

---

## 版本标签说明

- `新增`：新功能
- `改进`：对现有功能的改进
- `修复`：Bug 修复
- `变更`：对现有功能的变更
- `移除`：移除的功能
- `安全`：安全相关的修复
- `废弃`：即将移除的功能

[Unreleased]: https://github.com/YOUR_USERNAME/EBookAI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_USERNAME/EBookAI/releases/tag/v0.1.0
