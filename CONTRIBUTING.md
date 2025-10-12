# 贡献指南

感谢对 EBookAI 项目的关注！本文档将帮助您了解如何为项目做出贡献。

## 行为准则

参与本项目即表示您同意遵守我们的[行为准则](CODE_OF_CONDUCT.md)。

## 如何贡献

### 报告问题

如果发现 bug 或有功能建议：

1. 先搜索[现有 Issues](https://github.com/YOUR_USERNAME/EBookAI/issues)，避免重复
2. 使用相应的 Issue 模板创建新 Issue
3. 提供详细的描述和复现步骤

### 提交代码

#### 开发环境设置

1. Fork 本仓库到个人账户
2. 克隆 Fork 的仓库：
```bash
git clone https://github.com/YOUR_USERNAME/EBookAI.git
cd EBookAI
```

3. 安装依赖：
```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd frontend/web
npm install
```

4. 配置环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，配置必要的 API 密钥
```

5. 启动开发环境：
```bash
# 使用 Docker（推荐）
./start_dev.sh

# 或手动启动
# 后端
cd backend
uvicorn src.main:app --reload --port 8000

# 前端
cd frontend/web
npm start
```

#### 开发流程

1. 创建新分支：
```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

2. 进行开发并提交：
```bash
git add .
git commit -m "描述性的提交信息"
```

3. 推送到 Fork 的仓库：
```bash
git push origin feature/your-feature-name
```

4. 创建 Pull Request

#### 代码规范

**Python 代码：**
- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化：
```bash
black backend/
```

- 使用 isort 排序导入：
```bash
isort backend/
```

- 运行 Flake8 检查：
```bash
flake8 backend/
```

**JavaScript/React 代码：**
- 使用 ESLint 规范
- 遵循 React 最佳实践
- 组件命名使用 PascalCase
- 函数命名使用 camelCase

#### 测试要求

提交 PR 前必须确保：

1. 所有现有测试通过：
```bash
pytest backend/tests/
```

2. 新功能需要添加对应的测试用例
3. 测试覆盖率不低于当前水平

运行测试并查看覆盖率：
```bash
pytest backend/tests/ --cov=backend/src --cov-report=html
```

#### 提交信息规范

使用清晰的提交信息，建议遵循以下格式：

```
<类型>: <简短描述>

<详细描述>（可选）

<相关 Issue>（可选）
```

类型包括：
- `feat`: 新功能
- `fix`: bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

示例：
```
feat: 添加 MOBI 格式转换支持

实现了 MOBI 到 PDF 的转换功能，使用 Calibre 作为转换引擎。

Closes #123
```

### Pull Request 流程

1. **确保 PR 符合要求：**
   - 代码通过所有测试
   - 遵循代码规范
   - 包含必要的文档更新
   - PR 描述清晰，说明改动内容和原因

2. **PR 标题格式：**
   - 使用与提交信息相同的格式
   - 例如：`feat: 添加批量转换功能`

3. **填写 PR 模板：**
   - 描述改动内容
   - 列出相关 Issue
   - 说明测试方法

4. **代码审查：**
   - 维护者会审查 PR 并提供反馈
   - 根据反馈进行必要的修改
   - 通过审查后会被合并

## 项目结构

```
EBookAI/
├── backend/                    # 后端服务
│   ├── src/
│   │   ├── api/               # API 路由
│   │   ├── services/          # 业务逻辑
│   │   ├── utils/             # 工具函数
│   │   └── main.py            # 应用入口
│   └── tests/                 # 测试文件
├── frontend/web/              # Web 前端
│   ├── src/
│   │   ├── components/        # React 组件
│   │   └── services/          # API 调用
│   └── public/
├── docker/                    # Docker 配置
├── docs/                      # 文档
└── .github/                   # GitHub 配置
```

## 开发指南

### 添加新的转换格式

1. 在 [backend/src/services/conversion_service.py](backend/src/services/conversion_service.py) 中添加转换逻辑
2. 更新支持的格式列表
3. 添加相应的测试用例
4. 更新文档说明

### 集成新的 AI 提供商

1. 在 [backend/src/services/ai_service.py](backend/src/services/ai_service.py) 中添加提供商配置
2. 遵循现有的提供商接口规范
3. 在 `.env.example` 中添加配置示例
4. 更新 AI 配置文档

### 添加新的 API 端点

1. 在 `backend/src/api/` 相应模块中添加路由
2. 实现业务逻辑
3. 添加 API 测试
4. FastAPI 会自动更新 Swagger 文档

## 获取帮助

- 查看[文档](docs/)
- 搜索[现有 Issues](https://github.com/YOUR_USERNAME/EBookAI/issues)
- 在 Discussions 中提问
- 加入社区交流群（如果有）

## 许可证

贡献的代码将遵循项目的 [MIT License](LICENSE)。
