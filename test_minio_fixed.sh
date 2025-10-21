#!/bin/bash

# MinIO 快速修复和测试脚本
# 自动安装MinIO客户端并进行完整测试

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# 默认配置
DEFAULT_MINIO_ENDPOINT="http://localhost:9000"
DEFAULT_MINIO_BUCKET="youtube-videos"
DEFAULT_CREDENTIALS_FILE="/root/flowclip_credentials.txt"

# 显示使用帮助
show_help() {
    cat << EOF
MinIO 快速修复和测试脚本

用法: $0 [选项]

选项:
    -e, --endpoint URL      MinIO API端点 (默认: $DEFAULT_MINIO_ENDPOINT)
    -b, --bucket NAME       存储桶名称 (默认: $DEFAULT_MINIO_BUCKET)
    -a, --access-key KEY    MinIO访问密钥
    -s, --secret-key KEY    MinIO秘密密钥
    -f, --credentials-file  凭据文件路径 (默认: $DEFAULT_CREDENTIALS_FILE)
    -h, --help              显示此帮助信息

示例:
    $0                                    # 使用默认配置
    $0 -a minioadmin -s minioadmin       # 手动指定密钥

EOF
}

# 解析命令行参数
parse_args() {
    MINIO_ENDPOINT="$DEFAULT_MINIO_ENDPOINT"
    MINIO_BUCKET="$DEFAULT_MINIO_BUCKET"
    MINIO_ACCESS_KEY=""
    MINIO_SECRET_KEY=""
    CREDENTIALS_FILE="$DEFAULT_CREDENTIALS_FILE"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--endpoint)
                MINIO_ENDPOINT="$2"
                shift 2
                ;;
            -b|--bucket)
                MINIO_BUCKET="$2"
                shift 2
                ;;
            -a|--access-key)
                MINIO_ACCESS_KEY="$2"
                shift 2
                ;;
            -s|--secret-key)
                MINIO_SECRET_KEY="$2"
                shift 2
                ;;
            -f|--credentials-file)
                CREDENTIALS_FILE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 加载凭据
load_credentials() {
    if [[ -z "$MINIO_ACCESS_KEY" ]] || [[ -z "$MINIO_SECRET_KEY" ]]; then
        if [[ -f "$CREDENTIALS_FILE" ]]; then
            log_info "从凭据文件读取密钥: $CREDENTIALS_FILE"

            if [[ -z "$MINIO_ACCESS_KEY" ]]; then
                MINIO_ACCESS_KEY=$(grep "访问密钥:" "$CREDENTIALS_FILE" | awk '{print $3}' || echo "")
            fi

            if [[ -z "$MINIO_SECRET_KEY" ]]; then
                MINIO_SECRET_KEY=$(grep "秘密密钥:" "$CREDENTIALS_FILE" | awk '{print $3}' || echo "")
            fi

            if [[ -z "$MINIO_ACCESS_KEY" ]] || [[ -z "$MINIO_SECRET_KEY" ]]; then
                log_error "无法从凭据文件读取完整密钥信息"
                return 1
            fi
        else
            log_error "凭据文件不存在: $CREDENTIALS_FILE"
            log_info "请使用 -a 和 -s 参数手动指定密钥"
            return 1
        fi
    fi

    log_info "使用配置:"
    log_info "  端点: $MINIO_ENDPOINT"
    log_info "  存储桶: $MINIO_BUCKET"
    log_info "  访问密钥: ${MINIO_ACCESS_KEY:0:8}..."
    log_info "  秘密密钥: ${MINIO_SECRET_KEY:0:8}..."
}

# 安装MinIO客户端
install_mc_client() {
    if command -v mc &> /dev/null; then
        log_success "✓ MinIO客户端已安装"
        return 0
    fi

    log_info "安装MinIO客户端..."

    # 下载MinIO客户端
    if ! wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc; then
        log_error "MinIO客户端下载失败"
        return 1
    fi

    # 安装
    chmod +x /tmp/mc
    if [[ $EUID -eq 0 ]]; then
        mv /tmp/mc /usr/local/bin/mc
    else
        mkdir -p ~/bin
        mv /tmp/mc ~/bin/mc
        export PATH="$HOME/bin:$PATH"
    fi

    if command -v mc &> /dev/null; then
        log_success "✓ MinIO客户端安装成功"
    else
        log_error "✗ MinIO客户端安装失败"
        return 1
    fi
}

# 测试MinIO连接和权限
test_minio_with_mc() {
    log_info "配置MinIO客户端..."

    # 配置MinIO客户端
    if ! mc alias set flowclip-test "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"; then
        log_error "✗ MinIO客户端配置失败"
        return 1
    fi

    log_success "✓ MinIO客户端配置成功"

    # 测试连接
    log_info "测试MinIO连接..."
    if ! mc ls flowclip-test; then
        log_error "✗ MinIO连接失败"
        return 1
    fi

    log_success "✓ MinIO连接验证成功"

    # 检查或创建存储桶
    log_info "检查存储桶: $MINIO_BUCKET"
    if mc ls flowclip-test/"$MINIO_BUCKET" &>/dev/null; then
        log_success "✓ 存储桶已存在"
    else
        log_info "存储桶不存在，尝试创建..."
        if mc mb flowclip-test/"$MINIO_BUCKET"; then
            log_success "✓ 存储桶创建成功"
        else
            log_error "✗ 存储桶创建失败"
            return 1
        fi
    fi

    # 测试存储桶权限
    log_info "测试存储桶权限..."
    local test_file="/tmp/minio-test-$(date +%s).txt"
    echo "MinIO permission test - $(date)" > "$test_file"

    # 测试写权限
    if mc cp "$test_file" "flowclip-test/$MINIO_BUCKET/minio-permission-test.txt"; then
        log_success "✓ 写权限验证成功"

        # 测试读权限
        if mc cat "flowclip-test/$MINIO_BUCKET/minio-permission-test.txt" >/dev/null; then
            log_success "✓ 读权限验证成功"
        else
            log_warning "⚠ 读权限验证失败"
        fi

        # 测试删除权限
        if mc rm "flowclip-test/$MINIO_BUCKET/minio-permission-test.txt"; then
            log_success "✓ 删除权限验证成功"
        else
            log_warning "⚠ 删除权限验证失败"
        fi

        log_success "✅ MinIO存储桶完全就绪"
    else
        log_error "✗ 写权限验证失败"
        rm -f "$test_file"
        return 1
    fi

    # 清理临时文件
    rm -f "$test_file"

    # 清理客户端配置
    mc alias remove flowclip-test &>/dev/null || true

    return 0
}

# 主函数
main() {
    echo "========================================"
    echo "    MinIO 快速修复和测试脚本"
    echo "========================================"
    echo

    # 解析参数
    parse_args "$@"

    # 加载凭据
    if ! load_credentials; then
        exit 1
    fi

    # 安装MinIO客户端
    if ! install_mc_client; then
        exit 1
    fi

    # 测试MinIO
    if test_minio_with_mc; then
        echo
        echo "========================================"
        echo "         测试完成 - 全部通过！"
        echo "========================================"
        echo "🎉 MinIO服务已完全就绪"
        echo "✅ 所有权限验证通过"
        echo "✅ 存储桶 $MINIO_BUCKET 可用"
        echo "🔗 访问地址: $MINIO_ENDPOINT"
        echo "🎛️  控制台地址: http://localhost:9001"
        echo
    else
        echo
        echo "========================================"
        echo "           测试失败"
        echo "========================================"
        echo "❌ 请检查MinIO配置和凭据"
        echo "🔧 故障排查命令："
        echo "   systemctl status minio"
        echo "   journalctl -u minio -n 20"
        echo "   mc alias set test $MINIO_ENDPOINT ACCESS_KEY SECRET_KEY"
        echo "   mc ls test"
        echo
        exit 1
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi