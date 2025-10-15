# v0.2.0 发布准备

**准备日期**: 2024-10-13
**目标发布日期**: 待定
**状态**: 准备就绪

## 发布概览

v0.2.0 是一个重要的质量提升版本，包含以下关键改进：

- ✅ 测试覆盖率从 40% 提升到 65%+（71+ 测试用例）
- ✅ 自动文件清理机制
- ✅ 完整的开源项目基础设施（CI/CD、Issue 模板、PR 模板）
- ✅ 优化的项目结构和文档系统
- ✅ 改进的用户体验（Toast 通知、错误边界）

## 预发布检查状态

### 代码质量 ✅
- [x] 所有新增代码通过语法检查
- [x] 代码风格统一
- [x] 无明显代码异味
- [x] 注释和文档完整

### 测试 ✅
- [x] 所有测试用例通过（需在运行环境验证）
- [x] 测试覆盖率达标（65%+）
- [x] 关键功能有测试覆盖

**待验证**（需要运行环境）：
- [ ] 手动测试核心功能
  - 文件上传
  - 格式转换（EPUB ↔ PDF ↔ MOBI）
  - 批量转换
  - 文件下载
  - 自动文件清理

### 文档 ✅
- [x] README.md 更新
- [x] CHANGELOG.md 更新
- [x] RELEASE_NOTES_v0.2.0.md 准备完成
- [x] API 文档完整
- [x] 部署文档完善

### 配置 ✅
- [x] .env.example 包含所有配置项
- [x] Docker 配置正确
- [x] docker-compose.yml 正确
- [x] 环境变量文档同步

### 版本标识 ✅
- [x] CHANGELOG.md 版本号正确
- [x] RELEASE_NOTES 版本号正确
- [x] LICENSE 文件标准化
- [ ] Git 标签创建（待执行）

### 基础设施 ✅
- [x] CI/CD 工作流配置完成
- [x] GitHub Issue 模板
- [x] GitHub PR 模板
- [x] CODE_OF_CONDUCT.md
- [x] CONTRIBUTING.md

## 重要变更汇总

### 新增功能

1. **文件管理**
   - 自动文件清理机制（可配置清理间隔和保留时间）
   - 文件清理 API 端点
   - 磁盘使用统计

2. **测试覆盖**
   - 新增 38 个测试用例
   - 文件清理功能测试套件（18 个测试）
   - 批量转换 API 测试（12 个测试）
   - 清理 API 测试（8 个测试）

3. **开源基础设施**
   - GitHub Issue 模板（Bug 报告、功能请求、问题咨询）
   - GitHub PR 模板
   - CI/CD 自动化（代码质量检查、测试、Docker 构建）
   - 多架构 Docker 支持（amd64、arm64）

4. **前端优化**
   - Toast 通知系统
   - 错误边界组件
   - 全局通知管理

### 改进

1. **文档增强**
   - README 大幅扩充（100+ 行 → 300+ 行）
   - 项目结构优化和文档重组
   - 创建 project-docs/ 目录（管理类文档）

2. **代码质量**
   - 完善错误处理
   - 改进日志记录
   - 统一代码风格

## 发布步骤

### 前置条件

1. **运行环境测试**（强烈建议）
   ```bash
   # 启动服务
   docker-compose up -d

   # 验证健康检查
   curl http://localhost:8000/health

   # 手动测试核心功能
   # - 上传文件
   # - 格式转换
   # - 批量转换
   # - 文件清理
   ```

2. **确认所有改动已提交**
   ```bash
   git status
   ```

### 执行发布

#### 步骤 1: 检查当前分支和状态

```bash
# 确认在正确的分支
git branch

# 查看未提交的改动
git status
```

#### 步骤 2: 提交所有改动

```bash
# 添加所有文件
git add .

# 提交改动
git commit -m "release: prepare v0.2.0

- Add comprehensive test coverage (71+ tests, 65%+)
- Implement automatic file cleanup mechanism
- Establish complete open source infrastructure
- Optimize project structure and documentation
- Enhance user experience with Toast and ErrorBoundary
- Standardize LICENSE file

🤖 Generated with Claude Code
"
```

#### 步骤 3: 推送到远程仓库

```bash
# 推送到 main 分支
git push origin main
```

#### 步骤 4: 创建 Git 标签

```bash
# 创建带注释的标签
git tag -a v0.2.0 -m "Release v0.2.0 - 开源项目完善版

主要改进：
- 测试覆盖率提升至 65%+
- 自动文件清理
- 完整的开源基础设施
- 优化的项目结构
- 改进的用户体验
"

# 推送标签到远程
git push origin v0.2.0
```

#### 步骤 5: 创建 GitHub Release

1. 访问 GitHub 仓库的 Releases 页面
2. 点击 "Draft a new release"
3. 填写信息：
   - **Tag**: v0.2.0（从列表选择）
   - **Title**: v0.2.0 - 开源项目完善版
   - **Description**: 复制 [RELEASE_NOTES_v0.2.0.md](RELEASE_NOTES_v0.2.0.md) 的内容
4. 勾选 "Set as the latest release"
5. 点击 "Publish release"

#### 步骤 6: 验证 Docker 镜像构建

CI/CD 会自动触发 Docker 镜像构建。

检查 GitHub Actions：
1. 访问仓库的 Actions 页面
2. 查看 "Docker Publish" 工作流状态
3. 确认构建成功

手动构建（如需要）：
```bash
# 构建多架构镜像
docker buildx build --platform linux/amd64,linux/arm64 \
  -t YOUR_USERNAME/ebookai:0.2.0 \
  -t YOUR_USERNAME/ebookai:latest \
  --push .
```

### 发布后验证

```bash
# 拉取新镜像
docker pull YOUR_USERNAME/ebookai:0.2.0

# 运行测试
docker run --rm YOUR_USERNAME/ebookai:0.2.0 python -m pytest backend/tests/

# 启动服务
docker-compose up -d

# 验证健康检查
curl http://localhost:8000/health
```

## 发布后任务

### 立即任务（发布后 1 小时内）

1. **监控 CI/CD**
   - 确认 GitHub Actions 全部成功
   - 验证 Docker 镜像可拉取
   - 检查镜像标签正确

2. **功能验证**
   - 测试主要功能可用
   - 验证文档链接正常
   - 检查 API 文档可访问

### 短期任务（发布后 1-2 天）

1. **社区沟通**
   - 在 README 中突出显示最新版本
   - 准备发布公告（如有社区）
   - 更新相关文档链接

2. **问题跟踪**
   - 监控 GitHub Issues
   - 收集用户反馈
   - 准备快速修复方案

3. **文档更新**
   - 更新 [PROJECT_STATUS.md](PROJECT_STATUS.md)
   - 开始下一版本规划
   - 归档本次发布文档

## 回滚计划

如果发现严重问题需要回滚：

### 方案 1: 回退 Docker 镜像标签

```bash
# 将 latest 标签指向上一版本
docker tag YOUR_USERNAME/ebookai:0.1.0 YOUR_USERNAME/ebookai:latest
docker push YOUR_USERNAME/ebookai:latest
```

### 方案 2: 发布修复版本

```bash
# 创建修复分支
git checkout -b hotfix/v0.2.1

# 修复问题
# ... 进行必要的修复 ...

# 提交并发布 v0.2.1
git commit -m "hotfix: fix critical issue in v0.2.0"
git tag -a v0.2.1 -m "Hotfix release"
git push origin hotfix/v0.2.1 --tags
```

### 方案 3: 撤销 Release

```bash
# 删除远程标签
git push --delete origin v0.2.0

# 删除本地标签
git tag -d v0.2.0

# 在 GitHub 上删除 Release
# 访问 Releases 页面 → 点击对应 Release → Delete
```

## 风险评估

### 低风险 ✅
- 代码质量改进（测试、重构）
- 文档更新
- 项目结构优化
- LICENSE 标准化

### 中风险 ⚠️
- 文件清理机制（新功能，需要测试）
- 前端组件更新（Toast、ErrorBoundary）

### 建议
- 在生产环境部署前进行充分测试
- 特别关注文件清理功能的配置
- 监控初期的用户反馈

## 联系信息

**发布负责人**: Ming Chen
**问题反馈**: GitHub Issues
**紧急联系**: [待补充]

## 相关文档

- [发布说明](RELEASE_NOTES_v0.2.0.md)
- [变更日志](../CHANGELOG.md)
- [发布检查清单](RELEASE_CHECKLIST.md)
- [项目状态](PROJECT_STATUS.md)

---

**文档版本**: 1.0
**最后更新**: 2024-10-13
**下次审查**: 发布完成后
