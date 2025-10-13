# 项目结构优化方案

## 当前问题分析

### 根目录问题

1. **文档混乱**：根目录有太多文档文件（12+ 个 .md 文件）
2. **临时目录**：`uploads/`、`outputs/`、`logs/` 不应在根目录
3. **测试/实验代码**：`desktop-app/`、`swift-native-app/`、`swiftui-app/` 未完成的功能
4. **规划文档**：`ebook_platform_mvp.md`、`ebook_platform_outline.md` 应归档
5. **平台特定文档**：`NATIVE_MACOS_ANALYSIS.md`、`QUICK_START_MACOS.md` 应移至 docs

### 需要优化的地方

- ✅ 后端结构（已经很好）
- ✅ 前端结构（已经很好）
- ❌ 根目录过于混乱
- ❌ 文档组织不清晰
- ❌ 临时文件位置不合理

## 优化后的结构

```
EBookAI/
├── .github/                      # GitHub 配置
│   ├── workflows/                # CI/CD 工作流
│   │   ├── ci.yml
│   │   └── docker-publish.yml
│   ├── ISSUE_TEMPLATE/           # Issue 模板
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── question.md
│   └── PULL_REQUEST_TEMPLATE.md
│
├── backend/                      # 后端代码
│   ├── src/                      # 源代码
│   │   ├── api/                  # API 路由
│   │   ├── services/             # 业务逻辑
│   │   ├── utils/                # 工具函数
│   │   ├── config.py             # 配置
│   │   └── main.py               # 应用入口
│   ├── tests/                    # 测试代码
│   └── requirements.txt          # Python 依赖
│
├── frontend/                     # 前端代码
│   └── web/                      # Web 应用
│       ├── src/                  # 源代码
│       │   ├── components/       # React 组件
│       │   ├── services/         # API 服务
│       │   ├── styles/           # 样式文件
│       │   └── utils/            # 工具函数
│       ├── public/               # 静态文件
│       └── package.json          # NPM 依赖
│
├── docs/                         # 文档目录
│   ├── guides/                   # 用户指南
│   │   ├── quick-start.md        # 快速开始
│   │   ├── deployment.md         # 部署指南
│   │   └── ai-configuration.md   # AI 配置
│   ├── development/              # 开发文档
│   │   ├── setup.md              # 环境搭建
│   │   ├── architecture.md       # 架构说明
│   │   └── contributing.md       # 贡献指南 (链接)
│   ├── api/                      # API 文档
│   │   └── reference.md          # API 参考
│   ├── platform/                 # 平台特定文档
│   │   ├── macos.md              # macOS 指南
│   │   └── windows.md            # Windows 指南
│   ├── planning/                 # 规划文档（归档）
│   │   ├── mvp.md                # MVP 规划
│   │   └── outline.md            # 项目大纲
│   ├── faq.md                    # 常见问题
│   └── README.md                 # 文档索引
│
├── docker/                       # Docker 配置
│   ├── docker-compose.yml        # 生产环境
│   ├── docker-compose.dev.yml   # 开发环境
│   └── README.md                 # Docker 说明
│
├── scripts/                      # 脚本文件（新建）
│   ├── start_dev.sh              # 开发启动脚本
│   ├── run_tests.sh              # 测试脚本
│   └── cleanup.sh                # 清理脚本
│
├── config/                       # 配置文件
│   └── .env.example              # 环境变量示例
│
├── data/                         # 数据目录（新建）
│   ├── uploads/                  # 上传文件（临时）
│   ├── outputs/                  # 输出文件（临时）
│   └── logs/                     # 日志文件
│   └── .gitkeep
│
├── archive/                      # 归档目录（新建）
│   ├── desktop-app/              # 桌面应用实验（未完成）
│   ├── swift-native-app/         # Swift 应用实验
│   └── swiftui-app/              # SwiftUI 应用实验
│
├── .gitignore                    # Git 忽略文件
├── .flake8                       # Flake8 配置
├── pyproject.toml                # Python 项目配置
├── Dockerfile                    # Docker 镜像
├── docker-compose.yml            # Docker Compose（快捷方式，链接到 docker/）
├── LICENSE                       # 许可证
├── README.md                     # 项目说明
├── CHANGELOG.md                  # 更新日志
├── CONTRIBUTING.md               # 贡献指南
├── CODE_OF_CONDUCT.md            # 行为准则
├── PROJECT_STATUS.md             # 项目状态
├── RELEASE_NOTES_v0.2.0.md       # 发布说明
├── RELEASE_CHECKLIST.md          # 发布检查清单
└── WORK_SUMMARY.md               # 工作总结
```

## 优化步骤

### 第一步：整理文档

#### 移动规划文档到 docs/planning/
```bash
mkdir -p docs/planning
mv ebook_platform_mvp.md docs/planning/mvp.md
mv ebook_platform_outline.md docs/planning/outline.md
```

#### 移动平台特定文档到 docs/platform/
```bash
mkdir -p docs/platform
mv NATIVE_MACOS_ANALYSIS.md docs/platform/macos-analysis.md
mv QUICK_START_MACOS.md docs/platform/macos-quick-start.md
```

#### 重组 docs 目录
```bash
mkdir -p docs/guides docs/development docs/api

# 移动用户指南
mv docs/deployment.md docs/guides/
mv docs/ai-configuration.md docs/guides/
mv docs/environment-variables.md docs/guides/

# 移动开发文档
mv docs/development-setup.md docs/development/setup.md

# 移动 API 文档
mv docs/api-reference.md docs/api/reference.md
```

### 第二步：整理数据目录

```bash
# 创建数据目录
mkdir -p data/uploads data/outputs data/logs

# 移动现有数据
mv uploads/* data/uploads/ 2>/dev/null || true
mv outputs/* data/outputs/ 2>/dev/null || true
mv logs/* data/logs/ 2>/dev/null || true

# 删除旧目录
rmdir uploads outputs logs 2>/dev/null || true

# 创建 .gitkeep
touch data/uploads/.gitkeep
touch data/outputs/.gitkeep
touch data/logs/.gitkeep
```

### 第三步：整理脚本

```bash
# 创建脚本目录
mkdir -p scripts

# 移动启动脚本
mv start_dev.sh scripts/
chmod +x scripts/start_dev.sh
```

### 第四步：归档未完成功能

```bash
# 创建归档目录
mkdir -p archive

# 移动未完成的应用
mv desktop-app archive/
mv swift-native-app archive/
mv swiftui-app archive/

# 创建归档说明
cat > archive/README.md << 'EOF'
# 归档内容

此目录包含未完成的实验性功能和早期原型。

## 内容

- `desktop-app/` - Electron 桌面应用原型（未完成）
- `swift-native-app/` - Swift 原生应用实验
- `swiftui-app/` - SwiftUI 应用实验

这些代码保留用于未来参考，但不包含在当前 MVP 中。

如需开发桌面应用版本，请参考这些原型代码。
EOF
```

### 第五步：整理配置文件

```bash
# 移动环境变量示例到 config
mkdir -p config
cp .env.example config/

# 创建 config README
cat > config/README.md << 'EOF'
# 配置文件

## 环境变量

复制 `.env.example` 到项目根目录并重命名为 `.env`：

\`\`\`bash
cp config/.env.example .env
\`\`\`

然后编辑 `.env` 文件，配置必要的参数。

详细配置说明请参考：[环境变量配置](../docs/guides/environment-variables.md)
EOF
```

### 第六步：更新 .gitignore

```bash
# 更新 .gitignore
cat >> .gitignore << 'EOF'

# Data directories
data/uploads/*
data/outputs/*
data/logs/*
!data/uploads/.gitkeep
!data/outputs/.gitkeep
!data/logs/.gitkeep

# Environment
.env

# Archive (optional, can be committed)
# archive/
EOF
```

### 第七步：更新引用路径

需要更新以下文件中的路径引用：

1. **backend/src/main.py** - 更新日志和上传目录路径
2. **backend/src/config.py** - 更新默认路径配置
3. **docker-compose.yml** - 更新卷挂载路径
4. **scripts/start_dev.sh** - 更新路径引用
5. **docs/README.md** - 更新文档链接

## 更新后的好处

### 1. 根目录清晰

- 只保留核心文档（6 个必需文档）
- 其他文档分类到 docs/ 下
- 临时文件统一到 data/ 下

### 2. 文档组织合理

- `docs/guides/` - 用户指南
- `docs/development/` - 开发文档
- `docs/api/` - API 文档
- `docs/platform/` - 平台特定
- `docs/planning/` - 规划归档

### 3. 符合业界标准

```
项目根目录：
- README.md (必需)
- LICENSE (必需)
- CHANGELOG.md (必需)
- CONTRIBUTING.md (必需)
- CODE_OF_CONDUCT.md (必需)
- 项目特定文档 (2-3 个)

子目录：
- backend/ (后端代码)
- frontend/ (前端代码)
- docs/ (文档)
- docker/ (容器配置)
- scripts/ (脚本)
- data/ (数据/临时文件)
- archive/ (归档)
```

### 4. 维护便利

- 新贡献者容易找到文档
- 文档分类清晰，便于查找
- 临时文件统一管理
- 归档内容不影响主项目

## 注意事项

### 破坏性变更

以下更改可能影响现有部署：

1. **数据目录路径变更**：
   - `uploads/` → `data/uploads/`
   - `outputs/` → `data/outputs/`
   - `logs/` → `data/logs/`

2. **脚本路径变更**：
   - `./start_dev.sh` → `scripts/start_dev.sh`

### 迁移指南

对于现有用户：

```bash
# 1. 备份数据
cp -r uploads uploads.bak
cp -r outputs outputs.bak
cp -r logs logs.bak

# 2. 拉取新代码
git pull origin main

# 3. 迁移数据
mkdir -p data/{uploads,outputs,logs}
cp -r uploads.bak/* data/uploads/ 2>/dev/null || true
cp -r outputs.bak/* data/outputs/ 2>/dev/null || true
cp -r logs.bak/* data/logs/ 2>/dev/null || true

# 4. 更新环境变量（如果需要）
# 检查 .env 文件，确保路径正确

# 5. 重启服务
docker-compose down
docker-compose up -d
```

### Docker 卷挂载更新

在 `docker-compose.yml` 中：

```yaml
volumes:
  - ./data/uploads:/workspace/data/uploads
  - ./data/outputs:/workspace/data/outputs
  - ./data/logs:/workspace/data/logs
```

## 实施建议

### 方案 A：渐进式重构（推荐）

1. **v0.2.0**: 当前结构（已完成）
2. **v0.2.1**: 移动文档和归档
3. **v0.3.0**: 更新数据目录和脚本路径

好处：
- 降低风险
- 给用户时间适应
- 每次变更都有明确文档

### 方案 B：一次性重构

在 v0.3.0 一次性完成所有重构。

好处：
- 快速到位
- 避免多次迁移

风险：
- 破坏性较大
- 需要充分测试

## 建议采用方案 A

在 v0.2.0 发布后，创建 v0.2.1 进行渐进式重构：

1. **v0.2.1-alpha**: 移动文档和归档（无破坏性）
2. **v0.2.1-beta**: 测试新结构
3. **v0.2.1**: 正式发布

然后在 v0.3.0 进行数据目录迁移。

---

## 执行决策

请确认是否：
1. [ ] 现在立即执行完整重构
2. [ ] 等待 v0.2.0 发布后再执行
3. [ ] 采用渐进式方案

推荐：**选项 2 或 3**，避免影响即将发布的 v0.2.0。
