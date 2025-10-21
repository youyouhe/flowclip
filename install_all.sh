#!/bin/bash

# Flowclip 完整一键安装脚本
# 自动完成从系统依赖到应用部署的所有步骤

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

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
    echo -e "${CYAN}${BOLD}[STEP]${NC} $1"
}

# 显示横幅
show_banner() {
    echo -e "${CYAN}${BOLD}"
    cat << 'EOF'
 ______ _ _     _     _                             _
|  ____(_) |   | |   | |                           | |
| |__   _| | __| | __| | ___  _ __ _   _ _ __   ___| |_ ___
|  __| | | |/ _` |/ _` |/ _ \| '__| | | | '_ \ / __| __/ __|
| |    | | | (_| | (_| | (_) | |  | |_| | | | | (__| |_\__ \
|_|    |_|\__,_|\__,_|\___/|_|   \__,_|_| |_|\___|\__|___/

                    一键安装脚本 v1.0
EOF
    echo -e "${NC}"
}

# 检查运行权限
check_permissions() {
    log_step "检查运行权限..."

    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo bash install_all.sh"
        exit 1
    fi

    log_success "Root权限检查通过"
}

# 检查系统环境
check_system() {
    log_step "检查系统环境..."

    # 检查操作系统
    if [[ ! -f /etc/os-release ]]; then
        log_error "无法检测操作系统版本"
        exit 1
    fi

    . /etc/os-release
    log_info "操作系统: $PRETTY_NAME"
    log_info "内核版本: $(uname -r)"
    log_info "CPU核心: $(nproc)"
    log_info "内存总量: $(free -h | awk 'NR==2{print $2}')"
    log_info "可用磁盘: $(df -h / | awk 'NR==2{print $4}')"

    log_success "系统环境检查完成"
}

# 安装系统依赖（第一阶段）
install_system_deps() {
    log_step "安装系统依赖（第一阶段）..."

    # 获取当前目录
    local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local INSTALL_ROOT_SCRIPT="$SCRIPT_DIR/install_root.sh"

    if [[ ! -f "$INSTALL_ROOT_SCRIPT" ]]; then
        log_info "下载install_root.sh脚本..."
        curl -fsSL https://raw.githubusercontent.com/youyouhe/flowclip/main/install_root.sh -o "$INSTALL_ROOT_SCRIPT"
        chmod +x "$INSTALL_ROOT_SCRIPT"
    fi

    log_info "运行系统级安装脚本..."
    if bash "$INSTALL_ROOT_SCRIPT"; then
        log_success "系统依赖安装完成"
    else
        log_error "系统依赖安装失败"
        exit 1
    fi
}

# 创建用户并切换
setup_user() {
    log_step "配置用户环境..."

    local SERVICE_USER="flowclip"
    local PROJECT_DIR="/home/$SERVICE_USER/EchoClip"

    # 确保用户存在
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_error "专用用户 $SERVICE_USER 不存在"
        log_info "请先运行系统安装脚本"
        exit 1
    fi

    # 切换到用户目录
    cd "/home/$SERVICE_USER"

    log_success "用户环境配置完成"
}

# 安装应用（第二阶段）
install_app() {
    log_step "安装应用依赖..."

    local SERVICE_USER="flowclip"
    local PROJECT_DIR="/home/$SERVICE_USER/EchoClip"

    # 检查脚本是否已经在用户目录
    if [[ ! -f "/home/$SERVICE_USER/install_user.sh" ]]; then
        # 获取当前脚本所在目录
        local SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        local INSTALL_USER_SCRIPT="$SCRIPT_DIR/install_user.sh"

        if [[ ! -f "$INSTALL_USER_SCRIPT" ]]; then
            log_info "下载install_user.sh脚本..."
            curl -fsSL https://raw.githubusercontent.com/youyouhe/flowclip/main/install_user.sh -o "/home/$SERVICE_USER/install_user.sh"
        else
            log_info "复制install_user.sh脚本到用户目录..."
            cp "$INSTALL_USER_SCRIPT" "/home/$SERVICE_USER/install_user.sh"
        fi

        chmod +x "/home/$SERVICE_USER/install_user.sh"
        chown "$SERVICE_USER:$SERVICE_USER" "/home/$SERVICE_USER/install_user.sh"
    else
        log_info "install_user.sh脚本已存在，跳过复制"
    fi

    # 切换到用户并运行安装
    log_info "切换到专用用户并安装应用..."
    su - "$SERVICE_USER" -c "cd /home/$SERVICE_USER && bash install_user.sh"

    if [[ $? -eq 0 ]]; then
        log_success "应用安装完成"
    else
        log_error "应用安装失败"
        exit 1
    fi
}

# 启动服务
start_services() {
    log_step "启动应用服务..."

    local SERVICE_USER="flowclip"
    local PROJECT_DIR="/home/$SERVICE_USER/EchoClip"

    # 切换到用户并启动服务
    su - "$SERVICE_USER" -c "cd $PROJECT_DIR && bash start_services.sh"

    if [[ $? -eq 0 ]]; then
        log_success "服务启动完成"
    else
        log_warning "服务启动可能存在问题，请检查日志"
    fi
}

# 显示完成信息
show_completion() {
    log_step "安装完成！"

    local SERVICE_USER="flowclip"
    local CREDENTIALS_FILE="/root/flowclip_credentials.txt"

    echo
    echo -e "${GREEN}${BOLD}🎉 Flowclip 安装完成！${NC}"
    echo
    echo "========================================"
    echo "           安装总结"
    echo "========================================"
    echo

    echo "✅ 系统依赖: MySQL 8.0, Redis, MinIO, Node.js, Python 3.11"
    echo "✅ 项目代码: 已克隆到 /home/flowclip/EchoClip"
    echo "✅ Python环境: 虚拟环境和依赖已安装"
    echo "✅ 前端构建: Node.js依赖已安装"
    echo "✅ 数据库: 已配置并运行迁移"
    echo "✅ PM2配置: 已创建并启动服务"
    echo

    # 显示访问信息
    if [[ -f "$CREDENTIALS_FILE" ]]; then
        local minio_access=$(grep "访问密钥:" "$CREDENTIALS_FILE" | awk '{print $3}')
        local minio_secret=$(grep "秘密密钥:" "$CREDENTIALS_FILE" | awk '{print $3}')
        local server_ip=$(hostname -I | awk '{print $1}')

        echo "========================================"
        echo "           访问信息"
        echo "========================================"
        echo
        echo "🌐 应用访问地址："
        echo "   前端界面: http://$server_ip:3000"
        echo "   后端API:  http://$server_ip:8001"
        echo "   API文档:  http://$server_ip:8001/docs"
        echo
        echo "🗄️  服务管理界面："
        echo "   MinIO控制台: http://$server_ip:9001"
        echo "   用户名: $minio_access"
        echo "   密码: $minio_secret"
        echo
        echo "📋 管理命令："
        echo "   查看服务状态: sudo -u flowclip pm2 status"
        echo "   查看日志: sudo -u flowclip pm2 logs"
        echo "   重启服务: sudo -u flowclip pm2 restart all"
        echo "   停止服务: sudo -u flowclip pm2 stop all"
        echo
    fi

    echo "🔐 凭据文件位置："
    echo "   系统凭据: $CREDENTIALS_FILE"
    echo "   用户凭据: /home/flowclip/EchoClip/credentials.txt"
    echo
    echo "⚠️  安全提醒："
    echo "   1. 请妥善保管凭据文件"
    echo "   2. 生产环境请修改默认密码"
    echo "   3. 定期备份数据库和配置"
    echo

    echo "========================================"
    echo "           开始使用"
    echo "========================================"
    echo
    echo "现在可以开始使用 Flowclip 了！"
    echo "访问 http://$(hostname -I | awk '{print $1}'):3000 开始使用"
    echo
}

# 错误处理
handle_error() {
    local line_number=$1
    log_error "脚本在第 $line_number 行发生错误"
    log_error "安装失败，请检查错误信息并重试"
    exit 1
}

# 主函数
main() {
    # 设置错误处理
    set -eE
    trap 'handle_error $LINENO' ERR

    # 显示横幅
    show_banner

    echo -e "${CYAN}${BOLD}开始 Flowclip 完整安装...${NC}"
    echo

    # 检查权限
    check_permissions

    # 检查系统
    check_system

    # 安装系统依赖
    install_system_deps

    # 配置用户环境
    setup_user

    # 安装应用
    install_app

    # 启动服务
    start_services

    # 显示完成信息
    show_completion
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi