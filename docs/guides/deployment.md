# 部署指南

本指南提供 EBookAI 在不同环境下的部署方法。

## 目录

- [使用 Docker 部署（推荐）](#使用-docker-部署推荐)
- [手动部署](#手动部署)
- [系统要求](#系统要求)
- [环境配置](#环境配置)
- [生产环境建议](#生产环境建议)
- [故障排查](#故障排查)

## 使用 Docker 部署（推荐）

Docker 部署是最简单的方式，适合快速体验和生产环境。

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

### 快速部署

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/EBookAI.git
cd EBookAI

# 配置环境变量（可选）
cp .env.example .env
nano .env  # 编辑配置

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 验证部署

```bash
# 检查服务状态
curl http://localhost:8000/health

# 查看 API 文档
open http://localhost:8000/docs

# 访问 Web 界面
open http://localhost:8000
```

### 停止服务

```bash
docker-compose down

# 删除数据卷（清除所有数据）
docker-compose down -v
```

## 手动部署

适合需要自定义安装或无法使用 Docker 的场景。

### 前置要求

- Python 3.11+
- Node.js 18+
- Calibre（电子书转换引擎）

### 安装 Calibre

#### macOS
```bash
brew install calibre
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y calibre
```

#### CentOS/RHEL
```bash
sudo yum install -y calibre
```

#### Windows
从 [Calibre 官网](https://calibre-ebook.com/download) 下载安装程序。

### 后端部署

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env

# 创建必要目录
mkdir -p uploads outputs logs

# 启动服务
cd backend
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 前端部署

如果需要单独运行前端（开发模式）：

```bash
cd frontend/web
npm install
npm start
```

生产环境前端已内置在后端中，无需单独部署。

## 系统要求

### 最低配置

- CPU: 1 核
- 内存: 2GB
- 磁盘: 5GB
- 操作系统: Linux/macOS/Windows

### 推荐配置

- CPU: 2 核或以上
- 内存: 4GB 或以上
- 磁盘: 20GB 或以上（取决于文件数量）
- 操作系统: Linux（Ubuntu 22.04+ 或 Debian 12+）

### 端口要求

- 8000: HTTP 服务（可修改）
- 确保防火墙允许所需端口

## 环境配置

### 必需配置

无，项目可以在不配置任何环境变量的情况下运行（仅格式转换功能）。

### 可选配置

#### AI 功能

配置至少一个 AI 提供商以启用 AI 功能：

```bash
# OpenAI 兼容 API
OPENAI_API_KEY=your_key
DEEPSEEK_API_KEY=your_key

# Anthropic 兼容 API
CLAUDE_API_KEY=your_key
```

详见 [AI 配置指南](ai-configuration.md)。

#### 文件清理

```bash
# 文件保留时间（小时）
FILE_CLEANUP_MAX_AGE_HOURS=24

# 清理任务运行间隔（分钟）
FILE_CLEANUP_INTERVAL_MINUTES=60
```

#### 日志

```bash
# 日志级别：DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# 日志目录
LOG_DIR=logs
```

完整配置选项请参考 [环境变量配置](environment-variables.md)。

## 生产环境建议

### 使用反向代理

建议在生产环境使用 Nginx 或 Traefik 作为反向代理：

#### Nginx 示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### HTTPS 配置

使用 Let's Encrypt 获取免费 SSL 证书：

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com
```

### 进程管理

使用 systemd 管理服务：

```ini
# /etc/systemd/system/ebookai.service
[Unit]
Description=EBookAI Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/EBookAI
Environment="PATH=/opt/EBookAI/venv/bin"
ExecStart=/opt/EBookAI/venv/bin/uvicorn backend.src.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable ebookai
sudo systemctl start ebookai
sudo systemctl status ebookai
```

### 监控和日志

#### 日志轮转

```bash
# /etc/logrotate.d/ebookai
/opt/EBookAI/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 www-data www-data
}
```

#### 健康检查

设置定期健康检查：

```bash
# Cron job
*/5 * * * * curl -f http://localhost:8000/health || systemctl restart ebookai
```

### 备份策略

定期备份配置文件：

```bash
# 备份脚本
#!/bin/bash
BACKUP_DIR="/backup/ebookai"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cp -r /opt/EBookAI/.env $BACKUP_DIR/.env.$DATE
tar -czf $BACKUP_DIR/config.$DATE.tar.gz /opt/EBookAI/config
```

### 安全建议

1. **限制文件大小**：在 Nginx 中设置 `client_max_body_size`
2. **使用非 root 用户**：Docker 镜像已配置非 root 用户
3. **定期更新**：保持系统和依赖更新
4. **访问控制**：使用防火墙限制访问
5. **API 密钥保护**：不要在代码中硬编码密钥

### 性能优化

#### 增加并发能力

```bash
# 使用 Gunicorn 部署（多进程）
pip install gunicorn
gunicorn backend.src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 文件系统优化

```bash
# 使用独立的快速磁盘存储临时文件
UPLOAD_DIR=/mnt/fast-disk/uploads
OUTPUT_DIR=/mnt/fast-disk/outputs
```

## 故障排查

### Docker 相关问题

#### 容器无法启动

```bash
# 查看详细日志
docker-compose logs ebook-ai

# 重新构建镜像
docker-compose build --no-cache

# 检查端口占用
lsof -i :8000
```

#### 磁盘空间不足

```bash
# 清理 Docker 缓存
docker system prune -a

# 手动清理临时文件
curl -X POST http://localhost:8000/api/cleanup/run
```

### 转换失败

#### Calibre 问题

```bash
# 测试 Calibre 安装
ebook-convert --version

# 手动测试转换
ebook-convert test.epub test.pdf
```

#### 字体问题（中文支持）

```bash
# 安装中文字体
sudo apt-get install fonts-noto-cjk fonts-wqy-zenhei
```

### AI 功能问题

#### API 连接失败

```bash
# 测试 API 连接
curl -X POST http://localhost:8000/api/ai/providers

# 检查网络和代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

#### API 配额用完

检查 AI 提供商的使用情况和配额限制。

### 性能问题

#### 内存不足

```bash
# 检查内存使用
docker stats

# 限制 Docker 内存
docker-compose up -d --memory=2g
```

#### 转换速度慢

- 检查文件大小
- 升级硬件配置
- 使用 SSD 存储临时文件

### 日志查看

```bash
# Docker 日志
docker-compose logs -f

# 本地日志
tail -f logs/ebook-ai.log

# 按日期查看
ls -lh logs/
```

## 升级指南

### Docker 升级

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose down
docker-compose up -d
```

### 手动升级

```bash
# 停止服务
sudo systemctl stop ebookai

# 拉取最新代码
cd /opt/EBookAI
git pull

# 更新依赖
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 重启服务
sudo systemctl start ebookai
```

## 多实例部署

使用 Docker Compose 部署多个实例进行负载均衡：

```yaml
version: '3.8'

services:
  ebook-ai-1:
    image: ebookai:latest
    ports:
      - "8001:8000"

  ebook-ai-2:
    image: ebookai:latest
    ports:
      - "8002:8000"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

## 获取帮助

- 查看 [常见问题](faq.md)
- 提交 [Issue](https://github.com/YOUR_USERNAME/EBookAI/issues)
- 查看 [API 文档](api-reference.md)
