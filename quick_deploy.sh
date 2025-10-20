#!/bin/bash

# Flowclip 快速部署脚本
# 一键完成从系统初始化到服务启动的完整部署流程

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目配置
PROJECT_NAME="flowclip"
SERVICE_USER="flowclip"
PROJECT_DIR="/home/$SERVICE_USER/EchoClip"
CURRENT_DIR="$(pwd)"

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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

log_command() {
    echo -e "${CYAN}[COMMAND]${NC} $1"
}

# 显示欢迎信息
show_welcome() {
    echo
    echo "========================================"
    echo "    Flowclip 快速部署脚本"
    echo "========================================"
    echo
    echo "本脚本将自动完成以下操作："
    echo "1. 系统级组件安装 (MySQL, Redis, MinIO, Node.js)"
    echo "2. 创建专用用户和目录结构"
    echo "3. 安装应用依赖和配置环境"
    echo "4. 启动所有服务"
    echo
    echo "预计耗时: 15-30分钟"
    echo "硬件要求: 4核CPU, 8GB内存, 100GB存储"
    echo
    read -p "是否继续? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "部署已取消"
        exit 0
    fi
}

# 检查部署前置条件
check_prerequisites() {
    log_step "检查部署前置条件..."

    # 检查是否为root用户
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo bash quick_deploy.sh"
        exit 1
    fi

    # 检查网络连接
    if ! ping -c 1 google.com &> /dev/null; then
        log_warning "网络连接可能有问题，建议检查网络设置"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # 检查磁盘空间
    available_space=$(df / | awk 'NR==2 {print $4}')
    required_space=104857600  # 100GB in KB

    if [[ $available_space -lt $required_space ]]; then
        log_error "磁盘空间不足，需要至少100GB可用空间"
        exit 1
    fi

    # 检查内存
    available_mem=$(free -m | awk 'NR==2{print $7}')
    if [[ $available_mem -lt 4096 ]]; then
        log_warning "可用内存不足4GB，可能影响部署和运行性能"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    log_success "前置条件检查通过"
}

# 执行系统级安装
run_system_installation() {
    log_step "执行系统级组件安装..."

    log_command "bash install_root.sh"
    if bash "$CURRENT_DIR/install_root.sh"; then
        log_success "系统级组件安装完成"
    else
        log_error "系统级组件安装失败"
        exit 1
    fi
}

# 复制项目文件
copy_project_files() {
    log_step "复制项目文件..."

    # 确保目标目录存在
    mkdir -p "$PROJECT_DIR"

    # 复制项目文件（排除不需要的文件）
    log_command "rsync -av --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='.DS_Store' --exclude='*.log' \"$CURRENT_DIR/\" \"$PROJECT_DIR/\""

    if rsync -av --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='.DS_Store' --exclude='*.log' "$CURRENT_DIR/" "$PROJECT_DIR/"; then
        log_success "项目文件复制完成"
    else
        log_error "项目文件复制失败"
        exit 1
    fi

    # 设置权限
    chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_DIR"
}

# 执行用户级配置
run_user_configuration() {
    log_step "执行用户级环境配置..."

    # 以flowclip用户身份运行配置脚本
    log_command "su - $SERVICE_USER -c 'cd EchoClip && bash install_user.sh'"

    if su - "$SERVICE_USER" -c "cd EchoClip && bash install_user.sh"; then
        log_success "用户级环境配置完成"
    else
        log_error "用户级环境配置失败"
        exit 1
    fi
}

# 启动服务
start_services() {
    log_step "启动Flowclip服务..."

    # 以flowclip用户身份启动服务
    log_command "su - $SERVICE_USER -c 'cd EchoClip && ./start_services.sh'"

    if su - "$SERVICE_USER" -c "cd EchoClip && ./start_services.sh"; then
        log_success "服务启动完成"
    else
        log_error "服务启动失败"
        exit 1
    fi

    # 等待服务启动
    log_info "等待服务启动完成..."
    sleep 10
}

# 验证部署
verify_deployment() {
    log_step "验证部署结果..."

    local failed_services=()

    # 检查MySQL
    if mysql -uyoutube_user -pyoutube_password -e "SELECT 1;" &>/dev/null; then
        log_success "✓ MySQL服务正常"
    else
        log_error "✗ MySQL服务异常"
        failed_services+=("MySQL")
    fi

    # 检查Redis
    if redis-cli ping &>/dev/null; then
        log_success "✓ Redis服务正常"
    else
        log_error "✗ Redis服务异常"
        failed_services+=("Redis")
    fi

    # 检查MinIO
    if curl -s http://localhost:9000/minio/health/live &>/dev/null; then
        log_success "✓ MinIO服务正常"
    else
        log_error "✗ MinIO服务异常"
        failed_services+=("MinIO")
    fi

    # 检查后端API
    if curl -s http://localhost:8001/health &>/dev/null; then
        log_success "✓ 后端API服务正常"
    else
        log_warning "? 后端API服务可能还在启动中"
    fi

    # 检查前端
    if curl -s http://localhost:3000 &>/dev/null; then
        log_success "✓ 前端服务正常"
    else
        log_warning "? 前端服务可能还在启动中"
    fi

    # 检查PM2状态
    if su - "$SERVICE_USER" -c "cd EchoClip && pm2 status" &>/dev/null; then
        log_success "✓ PM2进程管理器正常"
    else
        log_error "✗ PM2进程管理器异常"
        failed_services+=("PM2")
    fi

    if [[ ${#failed_services[@]} -gt 0 ]]; then
        log_warning "部分服务存在问题: ${failed_services[*]}"
        log_info "请查看相关日志进行故障排除"
    else
        log_success "所有服务验证通过！"
    fi
}

# 显示部署完成信息
show_completion_info() {
    local server_ip=$(hostname -I | awk '{print $1}')

    echo
    echo "========================================"
    echo "🎉 Flowclip 部署完成！"
    echo "========================================"
    echo
    echo "服务访问地址："
    echo "  🌐 前端应用: http://$server_ip:3000"
    echo "  🔧 后端API: http://$server_ip:8001"
    echo "  📚 API文档: http://$server_ip:8001/docs"
    echo "  💾 MinIO控制台: http://$server_ip:9001"
    echo
    echo "服务管理命令："
    echo "  切换用户: sudo su - $SERVICE_USER"
    echo "  查看状态: cd EchoClip && pm2 status"
    echo "  查看日志: cd EchoClip && pm2 logs"
    echo "  重启服务: cd EchoClip && ./restart_services.sh"
    echo "  停止服务: cd EchoClip && ./stop_services.sh"
    echo
    echo "重要配置信息："
    echo "  项目目录: $PROJECT_DIR"
    echo "  专用用户: $SERVICE_USER"
    echo "  数据库: youtube_slicer / youtube_user / youtube_password"
    echo "  MinIO: i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0= / TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k="
    echo
    echo "📖 详细文档: 请参考 DEPLOYMENT_GUIDE.md"
    echo
    echo "⚠️  安全提醒："
    echo "  - 请修改默认密码和密钥"
    echo "  - 配置防火墙规则"
    echo "  - 定期备份数据"
    echo
}

# 错误处理函数
handle_error() {
    local exit_code=$?
    local line_number=$1

    log_error "脚本在第 $line_number 行执行失败，退出码: $exit_code"
    log_info "请检查错误日志并修复问题后重新运行"

    # 清理可能的残留文件
    log_info "清理临时文件..."
    rm -rf /tmp/flowclip_* &>/dev/null || true

    exit $exit_code
}

# 主函数
main() {
    # 设置错误处理
    trap 'handle_error $LINENO' ERR

    # 显示欢迎信息
    show_welcome

    # 检查前置条件
    check_prerequisites

    # 执行系统级安装
    run_system_installation

    # 复制项目文件
    copy_project_files

    # 执行用户级配置
    run_user_configuration

    # 启动服务
    start_services

    # 验证部署
    verify_deployment

    # 显示完成信息
    show_completion_info
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi