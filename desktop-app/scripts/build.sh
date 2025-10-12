#!/bin/bash

# EBookAI macOS 应用构建脚本
# 支持 Apple Silicon (ARM64) 和 Intel (x64) 架构

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统架构
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
    log_info "检测到 Apple Silicon (ARM64) 架构"
    TARGET_ARCH="arm64"
elif [[ "$ARCH" == "x86_64" ]]; then
    log_info "检测到 Intel (x64) 架构"
    TARGET_ARCH="x64"
else
    log_error "不支持的架构: $ARCH"
    exit 1
fi

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$PROJECT_ROOT")"

log_info "项目根目录: $PROJECT_ROOT"

# 清理旧的构建文件
log_info "清理旧的构建文件..."
rm -rf "$PROJECT_ROOT/dist"
rm -rf "$PROJECT_ROOT/build"
rm -rf "$PROJECT_ROOT/node_modules"

# 检查依赖
check_dependencies() {
    log_info "检查构建依赖..."

    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js 未安装，请安装 Node.js 18 或更高版本"
        exit 1
    fi

    NODE_VERSION=$(node --version | cut -d'.' -f1 | cut -d'v' -f2)
    if [[ $NODE_VERSION -lt 18 ]]; then
        log_error "Node.js 版本过低，需要 18 或更高版本，当前版本: $(node --version)"
        exit 1
    fi

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi

    # 检查 PyInstaller
    if ! python3 -c "import PyInstaller" &> /dev/null; then
        log_warning "PyInstaller 未安装，正在安装..."
        pip3 install pyinstaller
    fi

    log_success "依赖检查完成"
}

# 安装 Node.js 依赖
install_node_dependencies() {
    log_info "安装 Node.js 依赖..."
    cd "$PROJECT_ROOT"
    npm install
    log_success "Node.js 依赖安装完成"
}

# 构建前端
build_frontend() {
    log_info "构建前端应用..."
    cd "$REPO_ROOT/frontend/web"

    # 安装前端依赖
    if [[ ! -d "node_modules" ]]; then
        npm install
    fi

    # 构建前端
    npm run build

    # 复制构建结果到桌面应用目录
    cp -r build "$PROJECT_ROOT/build/frontend"

    log_success "前端构建完成"
}

# 构建后端
build_backend() {
    log_info "构建后端应用..."
    cd "$REPO_ROOT/backend"

    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi

    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip install -r requirements.txt
    pip install pyinstaller

    # 使用 PyInstaller 构建
    cd "$PROJECT_ROOT"
    mkdir -p build/backend

    pyinstaller \
        --onefile \
        --name ebookai-backend \
        --distpath build/backend \
        --workpath build/temp \
        --specpath build/temp \
        --target-arch $TARGET_ARCH \
        --hidden-import uvicorn.workers \
        --hidden-import uvicorn.workers.uvicorn_worker \
        --hidden-import websockets \
        --hidden-import httpx \
        --hidden-import multipart \
        --hidden-import aiofiles \
        --add-data "$REPO_ROOT/backend/src:src" \
        "$REPO_ROOT/backend/src/main.py"

    log_success "后端构建完成"
}

# 构建 Electron 应用
build_electron() {
    log_info "构建 Electron 应用..."
    cd "$PROJECT_ROOT"

    # 根据架构选择目标
    if [[ "$TARGET_ARCH" == "arm64" ]]; then
        npm run package -- --mac --arm64
    else
        npm run package -- --mac --x64
    fi

    log_success "Electron 应用构建完成"
}

# 创建 DMG 安装包
create_dmg() {
    log_info "创建 DMG 安装包..."
    cd "$PROJECT_ROOT"

    # 使用 electron-builder 创建 DMG
    npx electron-builder --mac --$TARGET_ARCH --publish=never

    log_success "DMG 安装包创建完成"
}

# 显示构建结果
show_results() {
    log_success "构建完成！"
    echo ""
    log_info "构建产物位置:"

    if [[ -d "$PROJECT_ROOT/dist" ]]; then
        find "$PROJECT_ROOT/dist" -name "*.dmg" -o -name "*.app" | while read -r file; do
            echo "  • $(basename "$file")"
            echo "    路径: $file"
            echo "    大小: $(du -h "$file" | cut -f1)"
            echo ""
        done
    else
        log_warning "未找到构建产物"
    fi
}

# 主构建流程
main() {
    log_info "开始构建 EBookAI macOS 应用 ($TARGET_ARCH)"
    echo ""

    check_dependencies
    install_node_dependencies

    mkdir -p "$PROJECT_ROOT/build"

    build_frontend
    build_backend
    build_electron
    create_dmg

    show_results

    log_success "构建流程完成！"
}

# 错误处理
trap 'log_error "构建过程中发生错误"; exit 1' ERR

# 运行主流程
main "$@"