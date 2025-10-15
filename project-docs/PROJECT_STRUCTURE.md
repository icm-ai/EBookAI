# 项目结构说明

本文档描述 EBookAI 项目的目录结构和组织方式。

## 目录结构

```
EBookAI/
├── .github/                      # GitHub 配置
│   ├── workflows/                # CI/CD 工作流
│   │   ├── ci.yml               # 代码质量检查和测试
│   │   └── docker-publish.yml   # Docker 镜像自动发布
│   ├── ISSUE_TEMPLATE/           # Issue 模板
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── question.md
│   └── PULL_REQUEST_TEMPLATE.md  # PR 模板
│
├── backend/                      # 后端代码
│   ├── src/                      # 源代码
│   │   ├── api/                  # API 路由
│   │   │   ├── ai.py             # AI 相关接口
│   │   │   ├── batch.py          # 批量转换接口
│   │   │   ├── cleanup.py        # 清理管理接口
│   │   │   ├── conversion.py    # 转换接口
│   │   │   ├── health.py         # 健康检查
│   │   │   ├── monitoring.py    # 监控接口
│   │   │   ├── progress.py       # 进度查询
│   │   │   └── websocket.py      # WebSocket
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── ai_service.py           # AI 服务
│   │   │   ├── batch_conversion_service.py  # 批量转换
│   │   │   └── conversion_service.py   # 格式转换
│   │   ├── utils/                # 工具函数
│   │   │   ├── error_handler.py       # 错误处理
│   │   │   ├── exceptions.py          # 自定义异常
│   │   │   ├── file_cleanup.py        # 文件清理
│   │   │   ├── logging_config.py      # 日志配置
│   │   │   ├── monitoring.py          # 性能监控
│   │   │   ├── progress_tracker.py    # 进度追踪
│   │   │   └── user_messages.py       # 用户消息
│   │   ├── config.py             # 配置管理
│   │   └── main.py               # 应用入口
│   ├── tests/                    # 测试代码
│   │   ├── test_api.py           # API 测试
│   │   ├── test_batch_api.py     # 批量接口测试
│   │   ├── test_cleanup_api.py   # 清理接口测试
│   │   ├── test_config.py        # 配置测试
│   │   ├── test_conversion_service.py  # 转换服务测试
│   │   └── test_file_cleanup.py  # 文件清理测试
│   └── requirements.txt          # Python 依赖
│
├── frontend/                     # 前端代码
│   └── web/                      # Web 应用
│       ├── src/                  # 源代码
│       │   ├── components/       # React 组件
│       │   │   ├── BatchUpload.js       # 批量上传
│       │   │   ├── ConversionHistory.js # 转换历史
│       │   │   ├── ConversionPanel.js   # 转换面板
│       │   │   ├── ErrorBoundary.js     # 错误边界
│       │   │   ├── FeatureIntro.js      # 功能介绍
│       │   │   ├── FileUpload.js        # 文件上传
│       │   │   ├── Toast.js             # 通知组件
│       │   │   └── ToastContainer.js    # 通知管理
│       │   ├── services/         # API 服务
│       │   │   ├── api.js        # API 客户端
│       │   │   └── websocket.js  # WebSocket 客户端
│       │   ├── styles/           # 样式文件
│       │   │   ├── ErrorBoundary.css
│       │   │   ├── Toast.css
│       │   │   └── index.css
│       │   ├── utils/            # 工具函数
│       │   ├── App.js            # 应用主组件
│       │   └── index.js          # 入口文件
│       ├── public/               # 静态文件
│       └── package.json          # NPM 依赖
│
├── docs/                         # 文档目录
│   ├── guides/                   # 用户指南
│   │   ├── ai-configuration.md  # AI 配置
│   │   ├── deployment.md         # 部署指南
│   │   ├── environment-variables.md  # 环境变量
│   │   └── faq.md                # 常见问题
│   ├── development/              # 开发文档
│   │   └── setup.md              # 环境搭建
│   ├── api/                      # API 文档
│   │   └── reference.md          # API 参考
│   ├── platform/                 # 平台特定文档
│   │   ├── macos-quick-start.md  # macOS 快速开始
│   │   └── macos-analysis.md     # macOS 分析
│   ├── planning/                 # 规划文档（归档）
│   │   ├── mvp.md                # MVP 规划
│   │   ├── outline.md            # 项目大纲
│   │   └── README.md             # 规划说明
│   └── README.md                 # 文档索引
│
├── docker/                       # Docker 配置
│   ├── docker-compose.yml        # 生产环境配置
│   ├── docker-compose.dev.yml   # 开发环境配置
│   └── README.md                 # Docker 说明
│
├── archive/                      # 归档目录
│   ├── desktop-app/              # Electron 应用（未完成）
│   ├── swift-native-app/         # Swift 应用实验
│   ├── swiftui-app/              # SwiftUI 应用实验
│   └── README.md                 # 归档说明
│
├── config/                       # 配置文件（未创建，规划中）
│   └── .env.example              # 环境变量示例
│
├── uploads/                      # 上传文件（临时，忽略）
├── outputs/                      # 输出文件（临时，忽略）
├── logs/                         # 日志文件（临时，忽略）
│
├── .github/                      # （见上）
├── .gitignore                    # Git 忽略文件
├── .flake8                       # Flake8 配置
├── .env.example                  # 环境变量示例
├── pyproject.toml                # Python 项目配置
├── Dockerfile                    # Docker 镜像定义
├── docker-compose.yml            # Docker Compose 配置
├── requirements.txt              # Python 依赖（根目录）
├── start_dev.sh                  # 开发启动脚本
│
├── LICENSE                       # MIT 许可证
├── README.md                     # 项目说明
├── CHANGELOG.md                  # 更新日志
├── CONTRIBUTING.md               # 贡献指南
├── CODE_OF_CONDUCT.md            # 行为准则
├── PROJECT_STATUS.md             # 项目状态
├── PROJECT_STRUCTURE.md          # 本文件
├── PROJECT_STRUCTURE_OPTIMIZATION.md  # 结构优化方案
├── RELEASE_NOTES_v0.2.0.md       # 发布说明
├── RELEASE_CHECKLIST.md          # 发布检查清单
└── WORK_SUMMARY.md               # 工作总结
```

## 目录说明

### 核心代码

#### backend/
后端 Python 代码，基于 FastAPI 框架。

- **src/api/** - RESTful API 端点定义
- **src/services/** - 核心业务逻辑（格式转换、AI 处理）
- **src/utils/** - 通用工具函数
- **tests/** - 单元测试和集成测试

#### frontend/
前端 React 代码。

- **src/components/** - React 组件
- **src/services/** - API 调用和 WebSocket 通信
- **src/styles/** - CSS 样式

### 配置和部署

#### docker/
Docker 相关配置。

- **docker-compose.yml** - 生产环境
- **docker-compose.dev.yml** - 开发环境（包含热重载）

#### .github/
GitHub 平台配置。

- **workflows/** - CI/CD 自动化工作流
- **ISSUE_TEMPLATE/** - Issue 报告模板
- **PULL_REQUEST_TEMPLATE.md** - PR 模板

### 文档

#### docs/
项目文档，按类型组织：

- **guides/** - 用户指南（部署、配置、FAQ）
- **development/** - 开发文档（环境搭建、架构）
- **api/** - API 文档
- **platform/** - 平台特定文档
- **planning/** - 历史规划文档（归档）

### 临时文件

以下目录包含运行时生成的临时文件，已在 .gitignore 中忽略：

- **uploads/** - 用户上传的文件
- **outputs/** - 转换生成的文件
- **logs/** - 应用日志

### 归档

#### archive/
未完成或已废弃的实验性代码：

- **desktop-app/** - Electron 桌面应用原型
- **swift-native-app/** - Swift 原生应用实验
- **swiftui-app/** - SwiftUI 应用实验

这些代码保留供未来参考，但不在当前版本中维护。

## 文件命名约定

### Python 文件
- 模块：`snake_case.py`
- 类：`PascalCase`
- 函数和变量：`snake_case`
- 常量：`UPPER_CASE`

### JavaScript 文件
- 组件文件：`PascalCase.js`
- 服务文件：`camelCase.js`
- 工具文件：`camelCase.js`
- 组件：`PascalCase`
- 函数和变量：`camelCase`
- 常量：`UPPER_CASE`

### 文档文件
- 普通文档：`kebab-case.md`
- 特殊文档：`UPPER_CASE.md`（如 README.md, CHANGELOG.md）

## 导入路径约定

### Python
```python
# 项目内导入（相对路径）
from api import conversion
from utils.logging_config import get_logger
from services.conversion_service import ConversionService
```

### JavaScript
```javascript
// 组件导入
import FileUpload from './components/FileUpload';

// 服务导入
import api from './services/api';

// 样式导入
import './styles/index.css';
```

## 测试组织

### Python 测试
- 位置：`backend/tests/`
- 命名：`test_*.py`
- 运行：`pytest backend/tests/`

### JavaScript 测试（规划中）
- 位置：`frontend/web/src/components/__tests__/`
- 命名：`*.test.js`
- 运行：`npm test`

## 数据流

```
用户上传 → uploads/ → 后端处理 → outputs/ → 用户下载
                ↓
            AI 处理（可选）
                ↓
            定期清理（24h）
```

## 配置优先级

1. 环境变量（.env）
2. Docker 环境变量
3. 默认配置（config.py）

## 日志位置

- 开发环境：`logs/` 目录
- Docker 环境：容器日志（docker logs）
- 生产环境：配置日志收集服务

## 端口使用

- **8000** - 后端 API（默认）
- **3000** - 前端开发服务器（仅开发环境）

## 扩展指南

### 添加新的 API 端点

1. 在 `backend/src/api/` 创建或修改路由文件
2. 在 `backend/src/main.py` 注册路由
3. 添加相应的测试
4. 更新 API 文档

### 添加新的 React 组件

1. 在 `frontend/web/src/components/` 创建组件文件
2. 创建对应的样式文件（如需要）
3. 在父组件中导入使用
4. 添加组件测试（推荐）

### 添加新的文档

1. 确定文档类型（用户指南、开发文档、API 文档）
2. 在 `docs/` 相应子目录创建文档
3. 更新 `docs/README.md` 索引
4. 在主 README 中添加链接（如需要）

## 版本控制

### Git 工作流

- **main** 分支：稳定版本
- **develop** 分支：开发版本
- **feature/** 分支：新功能开发
- **hotfix/** 分支：紧急修复

### 提交消息格式

```
<type>: <subject>

<body>

<footer>
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档
- `style`: 格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

## 未来规划

### 短期（v0.3.0）
- 创建 `scripts/` 目录统一管理脚本
- 创建 `data/` 目录统一临时文件
- 完善前端测试

### 长期（v1.0.0+）
- 多语言支持（i18n）
- 插件系统
- 微服务架构（可选）

---

**文档版本**: v0.2.0
**最后更新**: 2024-10-13
**维护者**: [@YOUR_USERNAME](https://github.com/YOUR_USERNAME)
