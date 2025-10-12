# EBookAI Native macOS App

这是 EBookAI 的原生 macOS 应用实现，采用 SwiftUI + WebView 混合架构，提供出色的原生体验。

## 🏗️ 架构设计

```
SwiftUI 原生界面
    ├── 主窗口和导航 (ContentView)
    ├── 文件选择器 (原生)
    ├── 进度显示 (原生)
    ├── 偏好设置 (PreferencesView)
    └── WKWebView 容器
            └── React 转换界面 (复用现有)

FastAPI 后端 (独立进程)
    ├── 文件转换服务
    ├── WebSocket 通信
    └── REST API
```

## 🚀 快速开始

### 开发环境要求

- macOS 12.0+ (Monterey)
- Xcode 14.0+
- Swift 5.7+
- Node.js 18+ (用于前端开发服务器)
- Python 3.11+ (用于后端服务)

### 开发模式运行

1. **启动后端服务**
   ```bash
   cd ../backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python src/main.py
   ```

2. **启动前端开发服务器**
   ```bash
   cd ../frontend/web
   npm install
   npm start
   ```

3. **运行 SwiftUI 应用**
   ```bash
   # 使用 Swift Package Manager
   swift run

   # 或在 Xcode 中打开项目
   open EBookAI.xcodeproj
   ```

## 📁 项目结构

```
swiftui-app/
├── Package.swift              # Swift 包管理配置
├── README.md                  # 项目说明
├── Sources/                   # 源代码目录
│   ├── App.swift             # 应用入口点
│   ├── AppState.swift        # 应用状态管理
│   ├── ContentView.swift     # 主界面
│   ├── WebViewRepresentable.swift  # WebView 集成
│   ├── PreferencesView.swift # 偏好设置
│   └── Resources/            # 资源文件
├── Tests/                    # 测试文件
└── dist/                     # 构建产物 (生成)
```

## 🔧 主要功能

### 原生界面组件

- **主窗口**: 原生 SwiftUI 窗口和导航
- **文件选择**: 原生 macOS 文件选择器
- **拖拽支持**: 支持拖拽文件到应用
- **进度显示**: 原生进度条和状态显示
- **菜单栏**: 完整的 macOS 菜单栏集成
- **偏好设置**: 原生设置界面

### WebView 集成

- **JavaScript Bridge**: 双向通信机制
- **文件传递**: 原生到 Web 的文件传递
- **进度同步**: 实时进度更新
- **错误处理**: 统一的错误处理机制

### 后端服务管理

- **自动启动**: 应用启动时自动启动后端服务
- **进程管理**: 完整的后端进程生命周期管理
- **健康检查**: 实时连接状态监控
- **端口配置**: 灵活的端口配置

## 🎯 JavaScript Bridge API

### 从 Web 调用原生功能

```javascript
// 选择文件
window.nativeInterface.selectFile();

// 报告进度
window.nativeInterface.reportProgress({
    percentage: 50,
    message: "正在转换..."
});

// 报告错误
window.nativeInterface.reportError("转换失败");

// 报告完成
window.nativeInterface.reportComplete();
```

### 从原生发送到 Web

```swift
// 发送文件列表
webViewCoordinator.sendMessage("filesAdded", data: fileData)

// 发送配置更新
webViewCoordinator.sendMessage("configUpdated", data: config)
```

### Web 端接收原生消息

```javascript
window.receiveNativeMessage = function(message) {
    const { type, data } = message;

    switch (type) {
        case 'filesAdded':
            handleFilesAdded(data);
            break;
        case 'configUpdated':
            handleConfigUpdate(data);
            break;
    }
};
```

## ⚙️ 配置和设置

### 应用配置

在 `AppState.swift` 中配置应用行为：

```swift
// 端口配置
private let backendPort = 8000
private let frontendPort = 3000

// 最近文件数量
private let maxRecentFiles = 10
```

### 偏好设置

应用包含完整的偏好设置界面：

- **通用设置**: 启动行为、窗口配置
- **转换设置**: 默认格式、并发数量
- **AI配置**: API 密钥、服务提供商
- **文件管理**: 下载位置、文件组织

## 🔨 构建和打包

### 开发构建

```bash
swift build
```

### 发布构建

```bash
swift build -c release
```

### 创建应用包

```bash
# 创建 .app 包
./scripts/create-app-bundle.sh

# 创建 DMG 安装包
./scripts/create-dmg.sh
```

## 🧪 测试

### 运行单元测试

```bash
swift test
```

### UI 测试

```bash
swift test --filter EBookAIUITests
```

## 📋 开发计划

### 已完成 ✅

- [x] 基础 SwiftUI 应用架构
- [x] WebView 集成和 JavaScript Bridge
- [x] 后端服务进程管理
- [x] 文件拖拽和选择功能
- [x] 原生进度显示
- [x] 偏好设置界面
- [x] 菜单栏集成

### 下一步 🚧

- [ ] 代码签名和公证配置
- [ ] 自动更新机制
- [ ] 应用图标和资源优化
- [ ] 性能优化和内存管理
- [ ] 更多原生集成功能

## 🐛 故障排除

### 常见问题

1. **后端服务启动失败**
   - 检查 Python 环境是否正确安装
   - 确认端口 8000 未被占用
   - 查看控制台日志获取详细错误信息

2. **WebView 无法加载**
   - 确认前端开发服务器正在运行
   - 检查端口 3000 是否可访问
   - 在 Safari 中测试 `http://localhost:3000`

3. **文件拖拽不工作**
   - 确认文件格式受支持
   - 检查应用权限设置
   - 查看系统安全设置

### 调试技巧

- 在开发模式下启用 WebView 调试
- 使用 Xcode 调试器查看原生代码执行
- 检查控制台输出获取详细日志

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](../LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📞 支持

- 📖 [文档](../docs/)
- 🐛 [Issue 报告](../../issues)
- 💬 [讨论区](../../discussions)
- 📧 [邮箱支持](mailto:support@ebookai.com)