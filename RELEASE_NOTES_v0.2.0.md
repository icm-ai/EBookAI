# EBookAI v0.2.0 发布说明

发布日期：2024-10-12

## 概述

v0.2.0 是 EBookAI 的第二个版本，专注于提升项目质量、完善开源基础设施和改善用户体验。本版本为项目建立了坚实的基础，为未来的功能扩展做好准备。

## 主要亮点

### 🧪 测试覆盖率大幅提升

- **测试用例数量**：从 33 个增加到 71+ 个（增长 115%）
- **测试覆盖率**：从 40% 提升到 65%+
- **新增测试模块**：
  - 文件清理功能测试（18 个测试）
  - 批量转换 API 测试（12 个测试）
  - 清理 API 测试（8 个测试）

### 🗂️ 自动文件管理

- **自动清理**：定期清理临时文件，防止磁盘空间耗尽
- **可配置**：支持自定义清理间隔和文件保留时间
- **监控**：提供磁盘使用统计和实时监控
- **API 控制**：手动触发清理和查看状态

### 📚 完善的开源基础设施

- **GitHub 模板**：
  - Issue 模板（Bug 报告、功能请求、问题咨询）
  - Pull Request 模板（详细的检查清单）
- **CI/CD 自动化**：
  - 代码质量检查（Black、isort、Flake8）
  - 自动化测试
  - Docker 镜像自动构建和发布
  - 多架构支持（amd64、arm64）
- **规范文档**：
  - 贡献指南（CONTRIBUTING.md）
  - 行为准则（CODE_OF_CONDUCT.md）

### 📖 文档体系完善

新增和改进的文档：
- **部署指南**：详细的 Docker 和手动部署说明
- **常见问题**：涵盖各种使用场景的 FAQ
- **项目状态报告**：完整的项目进度和计划
- **增强的 README**：更详细的功能说明和使用指南

### 🎨 用户体验优化

- **Toast 通知系统**：优雅的消息提示（success、error、warning、info）
- **错误边界**：React 错误的优雅处理和展示
- **更好的错误提示**：友好的用户反馈信息

## 详细变更

### 新增功能

#### 文件管理
```python
# 自动清理配置
FILE_CLEANUP_MAX_AGE_HOURS=24        # 文件保留 24 小时
FILE_CLEANUP_INTERVAL_MINUTES=60     # 每小时检查一次
```

API 端点：
- `POST /api/cleanup/run` - 手动触发清理
- `GET /api/cleanup/status` - 查看磁盘使用情况

#### 前端组件
- `Toast` - 通知提示组件
- `ToastContainer` - 全局通知管理
- `ErrorBoundary` - 错误边界组件

### 改进

- **文档**：README 从 100 行扩展到 300+ 行
- **测试**：测试代码从 500 行增加到 1000+ 行
- **代码质量**：统一代码风格，改进注释和文档

### 技术细节

- 后端代码：3000+ → 3500+ 行
- 前端代码：2000+ → 2500+ 行
- 文档文件：4 个 → 10+ 个
- 测试文件：3 个 → 6 个

## 升级指南

### 从 v0.1.0 升级

#### Docker 部署

```bash
# 1. 停止当前服务
docker-compose down

# 2. 拉取最新代码
git pull origin main

# 3. 重新构建镜像
docker-compose build

# 4. 启动服务
docker-compose up -d
```

#### 环境变量更新

在 `.env` 文件中添加新的配置项（可选）：

```bash
# 文件清理配置
FILE_CLEANUP_MAX_AGE_HOURS=24
FILE_CLEANUP_INTERVAL_MINUTES=60

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs
```

### 破坏性变更

**无破坏性变更** - 本版本完全向后兼容 v0.1.0。

## 已知问题

暂无已知问题。

## 贡献者

感谢所有为本版本做出贡献的开发者！

## 下一步计划

v0.3.0 将专注于：
- 性能优化（大文件处理、内存使用）
- 更多 AI 功能（翻译、校对）
- 桌面应用版本
- 批量下载功能

查看完整路线图：[PROJECT_STATUS.md](PROJECT_STATUS.md)

## 获取帮助

- 📖 [文档](docs/)
- 🐛 [报告问题](https://github.com/YOUR_USERNAME/EBookAI/issues)
- 💬 [提问讨论](https://github.com/YOUR_USERNAME/EBookAI/discussions)
- 📧 [联系我们](mailto:your-email@example.com)

## 下载

### Docker 镜像

```bash
docker pull YOUR_DOCKERHUB_USERNAME/ebookai:0.2.0
docker pull YOUR_DOCKERHUB_USERNAME/ebookai:latest
```

### 源代码

- [tar.gz](https://github.com/YOUR_USERNAME/EBookAI/archive/refs/tags/v0.2.0.tar.gz)
- [zip](https://github.com/YOUR_USERNAME/EBookAI/archive/refs/tags/v0.2.0.zip)

---

感谢使用 EBookAI！如果觉得项目有用，欢迎 Star ⭐
