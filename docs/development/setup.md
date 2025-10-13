# 开发环境搭建指南

本指南将帮助您搭建EBookAI项目的本地开发环境。

## 系统要求

### 必需软件

- **Docker**: 20.10.0+
- **Docker Compose**: 2.0.0+
- **Git**: 2.0.0+

### 操作系统支持

- macOS 10.15+
- Ubuntu 20.04+
- Windows 10+ (推荐使用WSL2)

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd EBookAI
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量文件
nano .env
```

最少需要配置一个AI提供商：

```bash
# 推荐使用DeepSeek（性价比高）
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEFAULT_AI_PROVIDER=deepseek

# 或者使用OpenAI
OPENAI_API_KEY=your_openai_api_key_here
DEFAULT_AI_PROVIDER=openai
```

### 3. 启动开发环境

```bash
# 使用启动脚本（推荐）
./start_dev.sh

# 或者手动启动
cd docker
docker-compose -f docker-compose.dev.yml up --build -d
```

### 4. 验证安装

访问以下地址确认服务正常运行：

- **前端应用**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 详细安装步骤

### Docker 安装

#### macOS

```bash
# 使用Homebrew安装
brew install --cask docker

# 或下载Docker Desktop
# https://www.docker.com/products/docker-desktop
```

#### Ubuntu

```bash
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 将用户添加到docker组
sudo usermod -aG docker $USER
```

#### Windows (WSL2)

```bash
# 安装Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop

# 在WSL2中验证安装
docker --version
docker-compose --version
```

### 代理配置（可选）

如果您在中国大陆或需要使用代理：

```bash
# 在.env文件中配置
HTTP_PROXY=http://127.0.0.1:7878
HTTPS_PROXY=http://127.0.0.1:7878
```

### API密钥配置

#### 获取DeepSeek API密钥

1. 访问 [DeepSeek官网](https://platform.deepseek.com/)
2. 注册并登录账户
3. 在控制台创建API密钥
4. 将密钥添加到 `.env` 文件

#### 获取OpenAI API密钥

1. 访问 [OpenAI平台](https://platform.openai.com/)
2. 注册并登录账户
3. 进入API Keys页面创建新密钥
4. 将密钥添加到 `.env` 文件

## 开发工作流

### 1. 启动开发环境

```bash
# 启动所有服务
./start_dev.sh

# 查看服务状态
docker ps
```

### 2. 查看日志

```bash
# 查看所有服务日志
cd docker
docker-compose -f docker-compose.dev.yml logs -f

# 查看特定服务日志
docker logs ebook-ai-workspace -f
```

### 3. 进入开发容器

```bash
# 进入容器进行调试
docker exec -it ebook-ai-workspace bash

# 查看Python环境
source venv/bin/activate
python --version
pip list
```

### 4. 代码修改

由于项目目录已挂载到容器中，您可以直接在本地编辑代码：

- **后端代码**: `backend/` 目录
- **前端代码**: `frontend/web/` 目录

代码修改后会自动重新加载（热重载）。

### 5. 安装新依赖

#### Python依赖

```bash
# 进入容器
docker exec -it ebook-ai-workspace bash

# 激活虚拟环境
source venv/bin/activate

# 安装新包
pip install package-name

# 更新requirements.txt
pip freeze > requirements.txt
```

#### Node.js依赖

```bash
# 进入容器
docker exec -it ebook-ai-workspace bash

# 进入前端目录
cd frontend/web

# 安装新包
npm install package-name

# 或者在本地安装（如果有Node.js环境）
npm install package-name
```

### 6. 数据库操作（未来功能）

当添加数据库支持时：

```bash
# 运行数据库迁移
docker exec ebook-ai-workspace python manage.py migrate

# 创建超级用户
docker exec -it ebook-ai-workspace python manage.py createsuperuser
```

## 测试

### 后端测试

```bash
# 进入容器
docker exec -it ebook-ai-workspace bash

# 激活虚拟环境
source venv/bin/activate

# 运行测试
cd backend
python -m pytest tests/
```

### 前端测试

```bash
# 进入容器
docker exec -it ebook-ai-workspace bash

# 进入前端目录
cd frontend/web

# 运行测试
npm test
```

### API测试

```bash
# 测试健康检查
curl http://localhost:8000/health

# 测试AI提供商
curl http://localhost:8000/api/ai/providers

# 测试特定提供商
curl http://localhost:8000/api/ai/providers/deepseek/test
```

## 停止开发环境

```bash
# 停止所有服务
cd docker
docker-compose -f docker-compose.dev.yml down

# 停止并删除数据卷
docker-compose -f docker-compose.dev.yml down -v

# 清理未使用的Docker资源
docker system prune
```

## 故障排除

### 常见问题

#### 1. 端口被占用

```bash
# 查看端口占用
lsof -i :3000
lsof -i :8000

# 停止占用进程
kill -9 <PID>
```

#### 2. Docker权限问题

```bash
# Linux用户需要加入docker组
sudo usermod -aG docker $USER

# 重新登录或运行
newgrp docker
```

#### 3. 容器构建失败

```bash
# 清理Docker缓存
docker builder prune

# 强制重新构建
docker-compose -f docker-compose.dev.yml build --no-cache
```

#### 4. 网络连接问题

```bash
# 检查代理设置
env | grep -i proxy

# 测试网络连接
docker run --rm alpine ping -c 3 google.com
```

#### 5. 文件权限问题

```bash
# 修复文件权限
sudo chown -R $USER:$USER .

# 或在容器内修复
docker exec -it ebook-ai-workspace chown -R 1000:1000 /workspace
```

### 调试技巧

#### 1. 查看详细日志

```bash
# 查看构建日志
docker-compose -f docker-compose.dev.yml build --progress=plain

# 查看运行时日志
docker logs ebook-ai-workspace --details
```

#### 2. 检查容器状态

```bash
# 查看容器状态
docker ps -a

# 检查容器配置
docker inspect ebook-ai-workspace
```

#### 3. 进入容器调试

```bash
# 使用bash进入容器
docker exec -it ebook-ai-workspace bash

# 检查环境变量
env | sort

# 检查网络连接
wget -qO- http://localhost:8000/health
```

## IDE 配置建议

### VS Code

推荐安装以下扩展：

- **Docker**: 管理Docker容器
- **Python**: Python语言支持
- **ES7+ React**: React开发支持
- **REST Client**: API测试

### PyCharm

配置Docker解释器：

1. Settings → Project → Python Interpreter
2. Add → Docker Compose
3. 选择 `docker-compose.dev.yml`
4. 选择 `ebook-ai-dev` 服务

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 本地开发和测试
4. 提交PR

详见项目根目录的 `CONTRIBUTING.md`（如果存在）。
