# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

暂无未发布的变更。

## [0.2.0] - 2024-10-12

### 新增

**文件管理**
- 自动文件清理机制，定期清理临时文件（可配置清理间隔和保留时间）
- 文件清理 API 端点（`/api/cleanup/run` 和 `/api/cleanup/status`）
- 磁盘使用统计和监控功能

**测试**
- 大幅增加测试覆盖率至 65%+
- 新增 38 个测试用例，总计 71+ 个测试
- 文件清理功能完整测试套件（18 个测试）
- 批量转换 API 测试（12 个测试）
- 清理 API 测试（8 个测试）

**开源项目基础设施**
- GitHub Issue 模板（Bug 报告、功能请求、问题咨询）
- GitHub Pull Request 模板
- CI/CD 工作流
  - 代码质量检查（Black、isort、Flake8）
  - 自动化测试（pytest）
  - Docker 镜像自动构建和发布
  - 多架构支持（amd64、arm64）
- 行为准则（CODE_OF_CONDUCT.md）
- 贡献指南（CONTRIBUTING.md）

**文档**
- 完整的部署指南（deployment.md）
- 常见问题文档（faq.md）
- 项目状态报告（PROJECT_STATUS.md）
- 更新日志（CHANGELOG.md）

**前端优化**
- Toast 通知系统（支持 success、error、warning、info）
- 错误边界组件，优雅处理 React 错误
- ToastContainer 全局通知管理

### 改进

**文档增强**
- 大幅增强 README，添加详细的功能说明和使用指南
- 添加支持格式对照表和转换质量说明
- 完善故障排查指南
- 添加开发路线图和技术栈说明

**配置优化**
- 优化环境变量配置示例
- 添加文件清理相关配置项
- 添加日志配置选项

**代码质量**
- 完善错误处理和日志记录
- 改进代码注释和文档字符串
- 统一代码风格

### 技术改进
- 应用启动时自动启动文件清理管理器
- 优雅的服务关闭处理
- 更完善的测试覆盖

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

### [0.2.0] - 开源项目完善版
显著提升项目质量和可维护性：
- 建立完整的开源项目基础设施
- 大幅提升测试覆盖率（40% → 65%）
- 完善文档体系
- 添加自动文件清理机制
- 优化用户体验

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

[Unreleased]: https://github.com/YOUR_USERNAME/EBookAI/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/YOUR_USERNAME/EBookAI/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/YOUR_USERNAME/EBookAI/releases/tag/v0.1.0
