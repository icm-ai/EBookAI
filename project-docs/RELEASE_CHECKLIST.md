# 发布检查清单

用于确保每次发布的质量和一致性。

## 发布前检查

### 代码质量

- [x] 所有新增代码通过语法检查
- [x] 代码风格统一（Python/JavaScript）
- [x] 无明显的代码异味
- [x] 注释和文档字符串完整

### 测试

- [x] 所有测试用例通过
- [x] 测试覆盖率达到目标（65%+）
- [x] 关键功能有测试覆盖
- [ ] 手动测试核心功能（需要在运行环境中测试）
  - [ ] 文件上传
  - [ ] 格式转换
  - [ ] 批量转换
  - [ ] 文件下载
  - [ ] 文件清理

### 文档

- [x] README.md 更新
- [x] CHANGELOG.md 更新
- [x] 发布说明准备完成
- [x] API 文档检查
- [x] 部署文档更新

### 配置

- [x] .env.example 包含所有必需的配置项
- [x] Docker 配置正确
- [x] docker-compose.yml 更新
- [x] 环境变量文档同步

### 版本号

- [x] CHANGELOG.md 中版本号正确
- [x] 发布说明中版本号正确
- [ ] Git 标签创建（待提交后）
- [ ] package.json 版本号更新（如需要）

## 发布流程

### 1. 代码准备

```bash
# 确认所有改动
git status

# 查看变更
git diff

# 添加所有文件
git add .

# 提交改动
git commit -m "release: prepare v0.2.0

- Add comprehensive test coverage (71+ tests)
- Implement automatic file cleanup
- Establish open source infrastructure
- Complete documentation system
- Optimize user experience
"
```

### 2. 推送到仓库

```bash
# 推送到远程仓库
git push origin main

# 创建标签
git tag -a v0.2.0 -m "Release v0.2.0"

# 推送标签
git push origin v0.2.0
```

### 3. GitHub Release

1. 访问 GitHub 仓库
2. 点击 "Releases" → "Create a new release"
3. 选择标签 `v0.2.0`
4. 填写发布标题：`v0.2.0 - 开源项目完善版`
5. 复制 RELEASE_NOTES_v0.2.0.md 的内容到描述框
6. 勾选 "Set as the latest release"
7. 点击 "Publish release"

### 4. Docker Hub

CI/CD 会自动构建和发布 Docker 镜像。

手动发布（如需要）：

```bash
# 构建镜像
docker build -t YOUR_USERNAME/ebookai:0.2.0 .
docker tag YOUR_USERNAME/ebookai:0.2.0 YOUR_USERNAME/ebookai:latest

# 登录 Docker Hub
docker login

# 推送镜像
docker push YOUR_USERNAME/ebookai:0.2.0
docker push YOUR_USERNAME/ebookai:latest
```

### 5. 发布后验证

- [ ] GitHub Release 页面正确显示
- [ ] Docker 镜像可以正常拉取
- [ ] CI/CD 工作流运行成功
- [ ] 文档链接正常工作
- [ ] 下载链接可用

### 6. 社区通知（可选）

- [ ] 发布公告（如有社区渠道）
- [ ] 更新项目主页
- [ ] 社交媒体分享
- [ ] 相关论坛发布

## 发布后任务

### 立即任务

- [ ] 监控 GitHub Issues 中的问题报告
- [ ] 检查 CI/CD 构建状态
- [ ] 验证 Docker 镜像可用性

### 短期任务（1-2 天）

- [ ] 收集用户反馈
- [ ] 修复发现的紧急问题
- [ ] 更新 PROJECT_STATUS.md
- [ ] 开始下一个版本规划

### 回滚计划

如果发现严重问题：

```bash
# 1. 回退到上一版本标签
git checkout v0.1.0

# 2. 创建修复分支
git checkout -b hotfix/v0.2.1

# 3. 修复问题后发布补丁版本
```

## 版本号规范

遵循语义化版本（Semantic Versioning）：

- **MAJOR（主版本号）**：不兼容的 API 变更
- **MINOR（次版本号）**：向后兼容的功能性新增
- **PATCH（修订号）**：向后兼容的问题修正

示例：
- 1.0.0 → 1.1.0：新增功能（向后兼容）
- 1.1.0 → 1.1.1：Bug 修复
- 1.0.0 → 2.0.0：破坏性变更

## 注意事项

1. **永远不要**直接在 main 分支上修改历史提交
2. **确保**所有 GitHub Secrets 配置正确（Docker Hub 凭证）
3. **测试**Docker 镜像在本地可以正常运行
4. **备份**重要数据和配置
5. **沟通**破坏性变更给用户

## 常见问题

### Q: 如果 CI 构建失败怎么办？
A: 检查 GitHub Actions 日志，修复问题后重新推送。

### Q: 如何撤销已发布的 Release？
A: 在 GitHub Release 页面删除，然后删除对应的 git 标签。

### Q: Docker 镜像推送失败？
A: 检查 Docker Hub 凭证，确认仓库名称正确。

---

最后更新：2024-10-12
维护者：@YOUR_USERNAME
