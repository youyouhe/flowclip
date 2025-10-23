#!/bin/bash

# EchoClip 快速启动脚本 (PM2 模式)
# 简化版部署脚本，用于快速启动和更新

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以 flowclip 用户运行
if [ "$(whoami)" != "flowclip" ]; then
    log_error "请以 flowclip 用户运行此脚本"
    exit 1
fi

PROJECT_DIR="/home/flowclip/EchoClip"
cd $PROJECT_DIR

log_info "EchoClip 快速启动..."

# 检查 PM2 配置文件
if [ ! -f "ecosystem.config.js" ]; then
    log_error "ecosystem.config.js 不存在，请先运行 ./deploy_pm2.sh"
    exit 1
fi

# 停止现有服务
log_info "停止现有服务..."
pm2 stop all || true
pm2 delete all || true

# 拉取最新代码
log_info "更新代码..."
git pull origin main

# 更新后端依赖
log_info "更新后端依赖..."
cd backend
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-audio.txt

# 更新前端依赖并构建
log_info "更新前端..."
cd ../frontend
npm install --legacy-peer-deps
npm run build

# 启动服务
log_info "启动服务..."
cd $PROJECT_DIR
pm2 start ecosystem.config.js --env production

# 保存配置
pm2 save

# 等待服务启动
sleep 5

# 显示状态
pm2 status

log_success "快速启动完成！"
echo ""
echo "访问地址："
echo "  前端: http://107.173.223.214:3000"
echo "  后端: http://107.173.223.214:8001"
echo ""
echo "管理命令："
echo "  查看日志: pm2 logs"
echo "  重启服务: pm2 restart all"