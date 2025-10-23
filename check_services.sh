#!/bin/bash

# EchoClip 服务状态检查脚本

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
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo "=========================================="
echo "EchoClip 服务状态检查"
echo "=========================================="
echo ""

# 检查 PM2 服务
log_info "检查 PM2 服务状态..."
if pm2 list | grep -q "online"; then
    log_success "PM2 服务运行中"
    pm2 list
else
    log_error "PM2 服务未运行"
fi
echo ""

# 检查系统服务
log_info "检查系统服务状态..."

# MySQL
if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
    log_success "MySQL 服务运行正常"
else
    log_error "MySQL 服务未运行"
fi

# Redis
if systemctl is-active --quiet redis 2>/dev/null || systemctl is-active --quiet redis-server 2>/dev/null; then
    log_success "Redis 服务运行正常"
else
    log_error "Redis 服务未运行"
fi

# MinIO
if pgrep -f "minio server" > /dev/null; then
    log_success "MinIO 服务运行正常"
else
    log_error "MinIO 服务未运行"
fi
echo ""

# 检查端口占用
log_info "检查端口占用情况..."
ports=(
    "3307:MySQL"
    "6379:Redis"
    "9000:MinIO API"
    "9001:MinIO Console"
    "3000:Frontend"
    "8001:Backend API"
    "9090:TUS Callback"
    "8002:MCP Server"
)

for port_info in "${ports[@]}"; do
    port=$(echo $port_info | cut -d':' -f1)
    service=$(echo $port_info | cut -d':' -f2)

    if netstat -tuln | grep -q ":$port "; then
        log_success "端口 $port ($service) 正在监听"
    else
        log_error "端口 $port ($service) 未监听"
    fi
done
echo ""

# 健康检查
log_info "执行健康检查..."

health_check() {
    local url=$1
    local service=$2

    if curl -f -s "$url" > /dev/null 2>&1; then
        log_success "$service 健康检查通过"
        return 0
    else
        log_error "$service 健康检查失败"
        return 1
    fi
}

# 检查各个服务的健康状态
health_check "http://localhost:8001/health" "Backend API"
health_check "http://localhost:3000" "Frontend"
health_check "http://localhost:9090/health" "TUS Callback Server"
health_check "http://localhost:9000/minio/health/live" "MinIO Health"
echo ""

# 检查磁盘空间
log_info "磁盘空间使用情况："
df -h /home/flowclip | tail -1 | awk '{print "已使用: " $3 " / " $2 " (" $5 ")"}'
echo ""

# 检查内存使用
log_info "内存使用情况："
free -h | grep Mem | awk '{print "已使用: " $3 " / " $2 " (" int($3/$2 * 100) "%)"}'
echo ""

# 显示最近的错误日志
log_info "最近的错误日志（最近10行）："
echo "--- Backend 错误日志 ---"
if [ -f "/home/flowclip/.pm2/logs/backend-error.log" ]; then
    tail -10 /home/flowclip/.pm2/logs/backend-error.log || echo "无错误日志"
else
    echo "日志文件不存在"
fi

echo ""
echo "--- Frontend 错误日志 ---"
if [ -f "/home/flowclip/.pm2/logs/frontend-error.log" ]; then
    tail -10 /home/flowclip/.pm2/logs/frontend-error.log || echo "无错误日志"
else
    echo "日志文件不存在"
fi

echo ""
echo "=========================================="
echo "检查完成"
echo "=========================================="

# 如果有任何服务异常，给出建议
if ! pm2 list | grep -q "online" || \
   ! systemctl is-active --quiet mysql 2>/dev/null && ! systemctl is-active --quiet mysqld 2>/dev/null || \
   ! systemctl is-active --quiet redis 2>/dev/null && ! systemctl is-active --quiet redis-server 2>/dev/null; then

    echo ""
    log_warn "检测到服务异常，建议："
    echo "1. 重新部署: ./deploy_pm2.sh"
    echo "2. 快速重启: ./quick_start.sh"
    echo "3. 查看详细日志: pm2 logs"
fi