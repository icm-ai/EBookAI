# 🚀 EBookAI macOS 应用快速开始指南

这份指南将帮助你快速构建和分发 EBookAI 的 macOS 原生应用程序，支持 Apple Silicon (ARM64) 和 Intel (x64) 架构。

## 📋 构建清单

### ✅ 前置要求
- [ ] macOS 10.15+
- [ ] Node.js 18+ (`brew install node`)
- [ ] Python 3.9+ (`brew install python@3.11`)
- [ ] Xcode Command Line Tools (`xcode-select --install`)

### ✅ 可选配置
- [ ] Apple Developer 账户（用于代码签名）
- [ ] App-specific password（用于公证）

## 🎯 一键构建

```bash
# 1. 进入桌面应用目录
cd desktop-app

# 2. 运行自动构建脚本
./scripts/build.sh

# 3. 查看构建结果
ls -la dist/
```

**就这么简单！** 🎉

## 📦 构建产物

成功构建后，你将获得：

```
dist/
├── EBookAI-1.0.0-arm64.dmg        # Apple Silicon 版本 (推荐)
├── EBookAI-1.0.0-x64.dmg          # Intel 版本
└── EBookAI-1.0.0-mac.zip          # 压缩包版本
```

## 🔧 详细步骤（可选）

如果你想了解构建过程或遇到问题：

### 1. 安装依赖

```bash
cd desktop-app
npm install
```

### 2. 构建前端

```bash
cd ../frontend/web
npm install
npm run build
```

### 3. 构建后端

```bash
cd ../../backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller
```

### 4. 打包应用

```bash
cd ../desktop-app

# ARM64 版本（Apple Silicon）
npm run package -- --mac --arm64

# x64 版本（Intel）
npm run package -- --mac --x64

# 通用版本（两种架构）
npm run package-universal
```

## 🎨 自定义配置

### 应用图标

1. 创建 1024x1024 像素的图标
2. 保存为 `desktop-app/assets/icon.icns`
3. 重新构建应用

### DMG 背景

1. 创建 540x380 像素的背景图
2. 保存为 `desktop-app/assets/dmg-background.png`
3. 重新构建应用

### 应用信息

编辑 `desktop-app/package.json` 中的应用信息：

```json
{
  "name": "your-app-name",
  "version": "1.0.0",
  "description": "Your app description",
  "author": {
    "name": "Your Name",
    "email": "your.email@example.com"
  }
}
```

## 🔐 代码签名（推荐）

### 设置环境变量

```bash
export APPLE_ID="your-apple-id@example.com"
export APPLE_ID_PASSWORD="your-app-specific-password"
export CSC_IDENTITY_AUTO_DISCOVERY=true
```

### 构建并签名

```bash
npm run dist
```

## 📱 分发应用

### 方式 1：直接分发 DMG

1. 将 `.dmg` 文件上传到你的网站
2. 用户下载并安装
3. 首次运行需要在 **系统偏好设置 > 安全性与隐私** 中允许

### 方式 2：通过 GitHub Releases

```bash
# 上传到 GitHub Releases
gh release create v1.0.0 dist/*.dmg --title "EBookAI v1.0.0" --notes "Release notes"
```

### 方式 3：App Store（需要额外配置）

- 需要 App Store Connect 账户
- 需要完整的代码签名和公证
- 需要符合 App Store 审核指南

## 🐛 常见问题

### Q: 构建失败，提示权限错误？
A: 确保脚本有执行权限：`chmod +x scripts/build.sh`

### Q: 应用无法启动？
A: 检查 macOS 版本，确保在 **安全性与隐私** 中允许运行

### Q: 想要同时支持两种架构？
A: 使用 `npm run package-universal` 构建通用版本

### Q: 如何减小应用体积？
A: 在 `package.json` 中排除不需要的依赖

### Q: 如何添加自动更新？
A: 应用已集成 `electron-updater`，配置你的更新服务器

## 📚 进阶配置

### 自定义构建脚本

编辑 `scripts/build.sh` 添加你的自定义逻辑：

```bash
# 添加版本号检查
check_version() {
    # 你的版本检查逻辑
}

# 添加测试
run_tests() {
    # 你的测试逻辑
}
```

### 优化应用性能

1. **减小包体积**：排除不必要的依赖
2. **启动优化**：预加载常用模块
3. **内存优化**：合理管理进程生命周期

### 添加更多功能

- **菜单栏应用**：创建状态栏图标
- **文件关联**：关联特定文件类型
- **URL Scheme**：支持自定义 URL 协议
- **通知中心**：集成 macOS 通知

## 🎉 完成！

恭喜！你现在有了一个专业的 macOS 应用程序。用户可以：

- ✨ 双击 DMG 文件安装
- 🖱️ 拖拽文件到应用进行转换
- ⚡ 享受原生性能和体验
- 🔄 自动接收应用更新

## 🤝 需要帮助？

- 📖 查看详细文档：`desktop-app/README.md`
- 🐛 报告问题：GitHub Issues
- 💬 社区讨论：GitHub Discussions
- 📧 联系我们：info@ebookai.com

---

> 💡 **提示**：第一次构建可能需要几分钟下载依赖，后续构建会更快。建议在良好的网络环境下进行构建。