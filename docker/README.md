# Docker 配置说明

本目录包含EBookAI项目的Docker开发环境配置。

## 文件说明

- `Dockerfile.dev` - Alpine Linux基础的轻量级开发环境
- `Dockerfile.amd64` - Ubuntu/Debian基础的AMD64/x86_64开发环境
- `docker-compose.dev.yml` - 开发环境编排配置

## 支持的架构

### Alpine Linux (默认)
- **文件**: `Dockerfile.dev`
- **基础镜像**: `node:22-alpine`
- **特点**: 轻量级，适合大部分开发场景
- **架构**: 支持多架构（ARM64/AMD64）

### AMD64/x86_64 专用
- **文件**: `Dockerfile.amd64`
- **基础镜像**: `node:22-bullseye`
- **特点**: 基于Debian，兼容性更好
- **架构**: 仅支持AMD64/x86_64

## 使用方法

### 启动默认开发环境（Alpine）
```bash
cd docker
docker-compose -f docker-compose.dev.yml up -d
```

### 启动AMD64专用环境
```bash
cd docker
docker-compose -f docker-compose.dev.yml --profile amd64 up -d ebook-ai-amd64
```

### 同时运行两个环境
```bash
cd docker
docker-compose -f docker-compose.dev.yml --profile amd64 up -d
```

## 端口分配

### 默认环境 (ebook-ai-dev)
- **前端**: http://localhost:3000
- **后端**: http://localhost:8000

### AMD64环境 (ebook-ai-amd64)
- **前端**: http://localhost:3001
- **后端**: http://localhost:8001

## 环境变量

支持以下AI提供商环境变量：

```bash
# 内置提供商
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
CLAUDE_API_KEY=your_claude_api_key

# 自动发现提供商
MOONSHOT_API_KEY=your_moonshot_api_key
GROQ_API_KEY=your_groq_api_key
TOGETHER_API_KEY=your_together_api_key

# 默认提供商
DEFAULT_AI_PROVIDER=deepseek
```

## 已安装依赖

### Python依赖
- FastAPI 0.104.1
- Uvicorn 0.24.0
- Python-multipart 0.0.6
- OpenAI 1.3.0
- httpx 0.25.2

### Node.js依赖
- React 18.2.0
- React-DOM 18.2.0
- React-Scripts 5.0.1
- Axios 1.6.0
- React-Dropzone 14.2.3

### 系统工具
- Git
- Python 3
- Node.js 22
- Bash
- 构建工具链

## 开发工作流

### 进入容器
```bash
# 默认环境
docker exec -it ebook-ai-workspace bash

# AMD64环境
docker exec -it ebook-ai-workspace-amd64 bash
```

### 启动服务
```bash
# 在容器内启动后端
cd /workspace
source venv/bin/activate
export PYTHONPATH=/workspace/backend/src
python backend/src/main.py

# 在容器内启动前端（新终端）
cd /workspace/frontend/web
PORT=3000 npm start
```

### 查看日志
```bash
# 查看所有服务日志
docker-compose -f docker-compose.dev.yml logs -f

# 查看特定服务日志
docker logs ebook-ai-workspace -f
```

### 停止服务
```bash
# 停止默认环境
docker-compose -f docker-compose.dev.yml down

# 停止AMD64环境
docker-compose -f docker-compose.dev.yml --profile amd64 down

# 停止所有服务
docker-compose -f docker-compose.dev.yml --profile amd64 down
```

## 故障排除

### 依赖安装失败
```bash
# 重新构建镜像
docker-compose -f docker-compose.dev.yml build --no-cache

# 清理并重建
docker system prune
docker-compose -f docker-compose.dev.yml build --no-cache
```

### 端口冲突
```bash
# 检查端口占用
lsof -i :3000
lsof -i :8000

# 停止占用进程
kill -9 <PID>
```

### 权限问题
```bash
# 修复文件权限
sudo chown -R $USER:$USER ../

# 或在容器内修复
docker exec -it ebook-ai-workspace chown -R 1000:1000 /workspace
```

## 网络配置

### 代理设置
如果需要使用代理，已预配置：
- HTTP_PROXY=http://host.docker.internal:7878
- HTTPS_PROXY=http://host.docker.internal:7878

### 主机网络访问
容器可以通过 `host.docker.internal` 访问主机服务。

## 性能优化

### Volume挂载优化
- 使用 `node_modules` 匿名卷避免跨平台兼容性问题
- 源代码实时同步，支持热重载

### 镜像大小优化
- Alpine版本：约500MB
- AMD64版本：约800MB
- 多阶段构建减少最终镜像大小

## 建议

1. **开发推荐**: 使用Alpine版本（默认）
2. **兼容性要求**: 使用AMD64版本
3. **生产部署**: 另行配置生产环境镜像
4. **调试需要**: 两个环境可以并行运行对比测试