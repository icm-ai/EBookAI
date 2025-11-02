# Docker 网络问题解决方案

## 问题诊断

**当前症状**:
```
ERROR: failed to fetch oauth token: Post "https://auth.docker.io/token":
dial tcp [2a03:2880:f136:83:face:b00c:0:25de]:443: i/o timeout
```

**原因**: Docker Hub连接超时，可能是DNS、网络配置或防火墙问题。

---

## 解决方案（按推荐顺序）

### 方案1: 配置国内镜像源 ⭐⭐⭐⭐⭐

这是最有效的解决方案，使用国内镜像加速器。

#### macOS (Docker Desktop)

**步骤1**: 打开Docker Desktop设置
```bash
# 点击Docker图标 → Preferences → Docker Engine
```

**步骤2**: 编辑配置，添加镜像源
```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://registry.docker-cn.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

**步骤3**: 点击 "Apply & Restart"

**步骤4**: 验证配置
```bash
docker info | grep -A 10 "Registry Mirrors"
```

#### Linux

**步骤1**: 编辑配置文件
```bash
sudo mkdir -p /etc/docker
sudo nano /etc/docker/daemon.json
```

**步骤2**: 添加以下内容
```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://registry.docker-cn.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

**步骤3**: 重启Docker
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

**步骤4**: 验证
```bash
docker info | grep -A 10 "Registry Mirrors"
```

---

### 方案2: 修复DNS配置 ⭐⭐⭐⭐

Docker可能使用了不可达的DNS服务器。

#### macOS

**方法A: 在Docker Desktop中配置**
```json
{
  "dns": ["8.8.8.8", "114.114.114.114", "223.5.5.5"]
}
```

**方法B: 使用系统命令**
```bash
# 检查当前DNS
scutil --dns

# 如果需要，添加DNS
networksetup -setdnsservers Wi-Fi 8.8.8.8 114.114.114.114
```

#### Linux

编辑 `/etc/docker/daemon.json`:
```json
{
  "dns": ["8.8.8.8", "114.114.114.114", "223.5.5.5"]
}
```

重启Docker:
```bash
sudo systemctl restart docker
```

---

### 方案3: 检查和配置代理 ⭐⭐⭐

如果您使用代理上网，需要配置Docker代理。

#### macOS (Docker Desktop)

**步骤1**: Preferences → Resources → Proxies

**步骤2**: 配置HTTP/HTTPS代理
```
HTTP Proxy: http://your-proxy:port
HTTPS Proxy: http://your-proxy:port
```

**或手动配置**:
```bash
# 编辑 ~/.docker/config.json
{
  "proxies": {
    "default": {
      "httpProxy": "http://proxy.example.com:8080",
      "httpsProxy": "http://proxy.example.com:8080",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
```

#### Linux

**创建systemd配置**:
```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/http-proxy.conf
```

**添加内容**:
```ini
[Service]
Environment="HTTP_PROXY=http://proxy.example.com:8080"
Environment="HTTPS_PROXY=http://proxy.example.com:8080"
Environment="NO_PROXY=localhost,127.0.0.1"
```

**重启**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

---

### 方案4: 使用本地已有镜像 ⭐⭐⭐⭐

避免从网络拉取，直接使用本地镜像。

```bash
# 检查本地可用镜像
docker images

# 如果有node:22-alpine，修改Dockerfile
FROM node:22-alpine  # 使用本地已有的

# 如果没有node:22-bullseye但有其他版本
FROM node:18-bullseye  # 使用可用的版本
FROM node:20-alpine
```

**修改Dockerfile.amd64**:
```dockerfile
# 原来
FROM --platform=linux/amd64 node:22-bullseye

# 改为使用本地已有的
FROM node:22-alpine  # 您本地有这个镜像
```

---

### 方案5: 临时禁用IPv6 ⭐⭐⭐

错误信息显示尝试连接IPv6地址，可能是IPv6配置问题。

#### macOS

**临时禁用IPv6**:
```bash
# 查看网络接口
networksetup -listallnetworkservices

# 禁用Wi-Fi的IPv6
networksetup -setv6off Wi-Fi

# 禁用Ethernet的IPv6
networksetup -setv6off Ethernet
```

**重启Docker Desktop**

**测试后恢复**:
```bash
networksetup -setv6automatic Wi-Fi
```

#### Linux

**编辑 `/etc/docker/daemon.json`**:
```json
{
  "ipv6": false
}
```

**或临时禁用系统IPv6**:
```bash
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
```

---

### 方案6: 使用离线构建 ⭐⭐

完全离线构建，不依赖网络。

#### 步骤1: 准备基础镜像

```bash
# 在有网络的机器上
docker pull node:22-bullseye
docker save node:22-bullseye > node-22-bullseye.tar

# 传输到目标机器
scp node-22-bullseye.tar user@target:/tmp/

# 在目标机器上加载
docker load < /tmp/node-22-bullseye.tar
```

#### 步骤2: 准备所有依赖包

在有网络的机器上下载所有包：
```bash
# 下载Python包
pip download PyMuPDF pdfplumber pytesseract Pillow -d ./python-packages

# 打包
tar czf python-packages.tar.gz python-packages/

# 传输和解压
scp python-packages.tar.gz user@target:/tmp/
tar xzf /tmp/python-packages.tar.gz
```

#### 步骤3: 修改Dockerfile使用本地包

```dockerfile
# 复制本地包到镜像
COPY python-packages /tmp/python-packages

# 使用本地包安装
RUN pip install --no-index --find-links=/tmp/python-packages \
    PyMuPDF pdfplumber pytesseract Pillow
```

---

## 快速测试方案

### 测试1: 使用已有的Alpine镜像

```bash
cd /Users/mingchen/workspace/github_repository/EBookAI

# 修改Dockerfile使用本地镜像
cat > docker/Dockerfile.local <<'EOF'
FROM node:22-alpine

# 只安装不需要编译的包
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    tesseract-ocr \
    tesseract-ocr-data-chi_sim \
    tesseract-ocr-data-chi_tra \
    poppler-utils

RUN pip install --break-system-packages \
    pdfplumber==0.10.0 \
    pytesseract==0.3.10 \
    Pillow==10.0.0

# 跳过PyMuPDF（需要编译）

WORKDIR /workspace
COPY . .

EXPOSE 8000 3000
CMD ["tail", "-f", "/dev/null"]
EOF

# 构建（无需网络）
docker build -f docker/Dockerfile.local -t ebookai:test .
```

### 测试2: 验证镜像源

```bash
# 测试国内镜像
docker pull registry.cn-hangzhou.aliyuncs.com/google_containers/pause:3.2

# 如果成功，说明镜像源配置正确
```

---

## 推荐执行顺序

### 第一优先级：配置镜像源（最有效）

```bash
# macOS
# 1. 打开Docker Desktop → Preferences → Docker Engine
# 2. 添加镜像源配置（见方案1）
# 3. Apply & Restart
# 4. 验证
docker info | grep "Registry Mirrors"

# 5. 重新构建
cd /Users/mingchen/workspace/github_repository/EBookAI
docker build -f docker/Dockerfile.amd64 -t ebookai:enhanced-conversion .
```

### 第二优先级：使用本地镜像

```bash
# 修改Dockerfile使用已有的node:22-alpine
# 然后构建
docker build -f docker/Dockerfile.alpine -t ebookai:enhanced-conversion .
```

### 第三优先级：完全离线方案

```bash
# 使用方案1的本地Python环境
cd backend
python3 -m venv venv-enhanced
source venv-enhanced/bin/activate
pip install -r requirements.txt
pip install PyMuPDF pdfplumber pytesseract Pillow
```

---

## 验证修复

### 检查1: 网络连接

```bash
# 测试Docker Hub
ping -c 3 docker.io
ping -c 3 registry-1.docker.io

# 测试DNS
nslookup docker.io
nslookup docker.io 8.8.8.8
```

### 检查2: Docker配置

```bash
# 查看Docker信息
docker info

# 查看镜像源配置
docker info | grep -A 10 "Registry Mirrors"

# 查看DNS配置
docker info | grep DNS
```

### 检查3: 拉取测试

```bash
# 测试小镜像
docker pull alpine:latest

# 测试Node镜像
docker pull node:22-alpine
```

---

## 常见问题解答

### Q: 配置了镜像源但还是超时？

**A**: 尝试以下步骤：
1. 完全重启Docker Desktop
2. 清除Docker缓存: `docker system prune -a`
3. 检查防火墙设置
4. 尝试不同的镜像源

### Q: macOS上如何彻底重启Docker？

**A**:
```bash
# 方法1: 使用命令
killall Docker && open /Applications/Docker.app

# 方法2: 使用菜单
# Docker图标 → Quit Docker Desktop
# 然后重新打开
```

### Q: 如何验证镜像源是否生效？

**A**:
```bash
# 查看配置
docker info | grep "Registry Mirrors"

# 应该看到类似输出:
# Registry Mirrors:
#  https://docker.mirrors.ustc.edu.cn/
#  https://hub-mirror.c.163.com/
```

### Q: 所有方案都失败了怎么办？

**A**: 使用完全离线的本地Python环境方案（见`QUICK_START.md`方案1）

---

## 推荐的完整流程

```bash
# 1. 配置镜像源（Docker Desktop图形界面）
# 见方案1

# 2. 重启Docker
# Docker Desktop → Quit → 重新打开

# 3. 验证配置
docker info | grep "Registry Mirrors"

# 4. 测试拉取
docker pull alpine:latest

# 5. 如果成功，重新构建
cd /Users/mingchen/workspace/github_repository/EBookAI
docker build -f docker/Dockerfile.amd64 -t ebookai:enhanced-conversion .

# 6. 如果还是失败，使用本地镜像方案
docker images  # 查看可用镜像
# 修改Dockerfile使用本地镜像
docker build -f docker/Dockerfile.alpine -t ebookai:enhanced-conversion .
```

---

## 需要帮助？

如果以上方案都无法解决问题，可以：

1. **检查系统日志**:
   ```bash
   # macOS
   tail -f ~/Library/Containers/com.docker.docker/Data/log/vm/dockerd.log
   ```

2. **使用Docker诊断工具**:
   ```bash
   # Docker Desktop → Troubleshoot → Run diagnostics
   ```

3. **使用完全离线方案**: 参考 `QUICK_START.md` 方案1（本地Python环境）

---

**最后更新**: 2025-11-02
**适用版本**: Docker Desktop for Mac
**测试状态**: 待验证
