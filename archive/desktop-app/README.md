# EBookAI macOS Desktop App

这是 EBookAI 的原生 macOS 桌面应用程序，支持 Apple Silicon (ARM64) 和 Intel (x64) 架构。

## 🚀 功能特性

- **原生 macOS 体验**：完全集成 macOS 设计语言
- **多架构支持**：原生支持 Apple Silicon (M1/M2/M3) 和 Intel 芯片
- **离线运行**：无需外部依赖，完全独立运行
- **拖拽支持**：直接拖拽文件到应用进行转换
- **菜单栏集成**：标准 macOS 菜单和快捷键支持
- **自动更新**：内置更新检查机制

## 📋 系统要求

- **操作系统**：macOS 10.15 Catalina 或更高版本
- **架构**：Apple Silicon (ARM64) 或 Intel (x64)
- **内存**：至少 4GB RAM
- **存储**：至少 500MB 可用空间

## 🛠 构建说明

### 前置要求

1. **Node.js 18+**
   ```bash
   # 使用 Homebrew 安装
   brew install node

   # 或者从官网下载：https://nodejs.org/
   ```

2. **Python 3.9+**
   ```bash
   # 使用 Homebrew 安装
   brew install python@3.11

   # 或者使用系统自带的 Python 3
   ```

3. **Xcode Command Line Tools**
   ```bash
   xcode-select --install
   ```

### 构建步骤

1. **克隆项目**
   ```bash
   git clone <your-repo-url>
   cd EBookAI/desktop-app
   ```

2. **运行构建脚本**
   ```bash
   # 自动构建（推荐）
   ./scripts/build.sh

   # 或者手动构建
   npm install
   npm run build
   ```

3. **查看构建结果**
   ```bash
   # 构建完成后，在 dist 目录查看：
   ls -la dist/

   # 你会看到：
   # EBookAI-1.0.0-arm64.dmg  (Apple Silicon 版本)
   # EBookAI-1.0.0-x64.dmg    (Intel 版本)
   # EBookAI-1.0.0-universal.dmg (通用版本，如果构建了的话)
   ```

### 构建选项

```bash
# 仅构建 ARM64 版本
npm run package -- --mac --arm64

# 仅构建 x64 版本
npm run package -- --mac --x64

# 构建通用版本（同时支持两种架构）
npm run package-universal

# 开发模式运行
npm run dev
```

## 📦 安装和分发

### 本地安装

1. 双击生成的 `.dmg` 文件
2. 将 EBookAI 拖拽到 Applications 文件夹
3. 首次运行时，在 **系统偏好设置 > 安全性与隐私** 中允许运行

### 代码签名（可选）

如果你有 Apple Developer 账户，可以对应用进行签名：

```bash
# 设置签名身份
export APPLE_ID="your-apple-id@example.com"
export APPLE_ID_PASSWORD="your-app-specific-password"
export CSC_IDENTITY_AUTO_DISCOVERY=true

# 构建并签名
npm run dist
```

### 公证（可选）

对于 App Store 外分发，建议进行公证：

```bash
# 在 package.json 中配置公证信息
{
  "build": {
    "afterSign": "scripts/notarize.js"
  }
}
```

## 🎯 使用说明

### 启动应用

1. 打开 Applications 文件夹
2. 双击 EBookAI 图标
3. 等待应用启动（首次启动可能需要几秒钟）

### 基本操作

- **打开文件**：拖拽文件到窗口，或使用 `⌘+O`
- **批量转换**：切换到 "批量转换" 选项卡
- **查看进度**：实时查看转换进度和状态
- **下载文件**：转换完成后点击下载按钮

### 支持的格式

- **输入格式**：EPUB, PDF, TXT, MOBI, AZW3
- **输出格式**：EPUB, PDF, TXT, MOBI, AZW3
- **最大文件大小**：50MB 每个文件
- **批量限制**：最多 50 个文件

## 🐛 故障排除

### 常见���题

1. **应用无法启动**
   - 检查 macOS 版本是否满足要求
   - 在安全设置中允许运行未签名应用

2. **转换失败**
   - 确认文件格式受支持
   - 检查文件是否损坏
   - 查看应用日志

3. **性能问题**
   - 关闭其他占用 CPU 的应用
   - 确保有足够的可用内存
   - 避免同时转换过多文件

### 日志查看

```bash
# 查看应用日志
tail -f ~/Library/Logs/EBookAI/main.log

# 或者在应用中：视图 > 切换开发者工具
```

### 重置应用

```bash
# 清除应用数据
rm -rf ~/Library/Application\ Support/EBookAI
rm -rf ~/Library/Preferences/com.ebookai.desktop.plist
```

## 📁 项目结构

```
desktop-app/
├── src/
│   └── main.js              # Electron 主进程
├── assets/
│   ├── icon.icns           # macOS 应用图标
│   ├── entitlements.mac.plist # macOS 权限配置
│   └── dmg-background.png   # DMG 背景图片
├── scripts/
│   ├── build.sh            # 构建脚本
│   └── build-backend.spec  # PyInstaller 配置
├── build/                  # 构建临时文件
├── dist/                   # 最终构建产物
└── package.json            # 项目配置
```

## 🤝 开发贡献

### 本地开发

```bash
# 安装依赖
npm install

# 启动开发模式
npm run dev

# 运行代码检查
npm run lint

# 运行测试
npm test
```

### 代码提交

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 📄 许可证

MIT License - 查看 [LICENSE](../LICENSE) 文件了解详情。

## 🙋‍♂️ 支持

- **GitHub Issues**: [报告问题](https://github.com/your-username/EBookAI/issues)
- **讨论区**: [社区讨论](https://github.com/your-username/EBookAI/discussions)
- **邮件**: info@ebookai.com

---

> 🎉 感谢使用 EBookAI！如果这个应用对你有帮助，请考虑给我们一个 ⭐️