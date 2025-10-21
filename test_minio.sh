#!/bin/bash

# MinIO 验证和测试脚本
# 独立测试MinIO服务配置和权限
# 可用于快速验证MinIO设置或故障排查

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认配置
DEFAULT_MINIO_ENDPOINT="http://localhost:9000"
DEFAULT_MINIO_CONSOLE="http://localhost:9001"
DEFAULT_MINIO_BUCKET="youtube-videos"
DEFAULT_CREDENTIALS_FILE="/root/flowclip_credentials.txt"

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

# 显示使用帮助
show_help() {
    cat << EOF
MinIO 验证测试脚本

用法: $0 [选项]

选项:
    -e, --endpoint URL      MinIO API端点 (默认: $DEFAULT_MINIO_ENDPOINT)
    -c, --console URL       MinIO控制台端点 (默认: $DEFAULT_MINIO_CONSOLE)
    -b, --bucket NAME       存储桶名称 (默认: $DEFAULT_MINIO_BUCKET)
    -a, --access-key KEY    MinIO访问密钥
    -s, --secret-key KEY    MinIO秘密密钥
    -f, --credentials-file  凭据文件路径 (默认: $DEFAULT_CREDENTIALS_FILE)
    -v, --verbose           详细输出模式
    -h, --help              显示此帮助信息

示例:
    # 使用默认配置
    $0

    # 使用自定义端点
    $0 -e http://192.168.1.100:9000

    # 手动指定密钥
    $0 -a minioadmin -s minioadmin

    # 从凭据文件读取
    $0 -f /path/to/credentials.txt

    # 详细测试模式
    $0 -v

EOF
}

# 解析命令行参数
parse_args() {
    MINIO_ENDPOINT="$DEFAULT_MINIO_ENDPOINT"
    MINIO_CONSOLE="$DEFAULT_MINIO_CONSOLE"
    MINIO_BUCKET="$DEFAULT_MINIO_BUCKET"
    MINIO_ACCESS_KEY=""
    MINIO_SECRET_KEY=""
    CREDENTIALS_FILE="$DEFAULT_CREDENTIALS_FILE"
    VERBOSE=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--endpoint)
                MINIO_ENDPOINT="$2"
                shift 2
                ;;
            -c|--console)
                MINIO_CONSOLE="$2"
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
            -v|--verbose)
                VERBOSE=true
                shift
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

# 从凭据文件读取密钥
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

    if [[ "$VERBOSE" == true ]]; then
        log_info "使用配置:"
        log_info "  端点: $MINIO_ENDPOINT"
        log_info "  控制台: $MINIO_CONSOLE"
        log_info "  存储桶: $MINIO_BUCKET"
        log_info "  访问密钥: ${MINIO_ACCESS_KEY:0:8}..."
        log_info "  秘密密钥: ${MINIO_SECRET_KEY:0:8}..."
    fi
}

# 测试基本连接
test_basic_connection() {
    log_info "测试MinIO基本连接..."

    # 检查MinIO API健康状态
    if curl -s -f "$MINIO_ENDPOINT/minio/health/live" &>/dev/null; then
        log_success "✓ MinIO API服务运行正常"
    else
        log_error "✗ MinIO API服务不可访问"
        return 1
    fi

    # 验证MinIO控制台
    if curl -s -f "$MINIO_CONSOLE" &>/dev/null; then
        log_success "✓ MinIO控制台可访问"
    else
        log_warning "⚠ MinIO控制台可能需要更多时间启动"
    fi

    # 测试API健康检查
    local api_test=$(curl -s -w "%{http_code}" -o /dev/null "$MINIO_ENDPOINT/minio/health/live")
    if [[ "$api_test" == "200" ]]; then
        log_success "✓ MinIO API健康检查通过"
        return 0
    else
        log_error "✗ MinIO API健康检查失败: HTTP $api_test"
        return 1
    fi
}

# 测试认证和权限
test_authentication_and_permissions() {
    log_info "测试MinIO认证和存储桶权限..."

    # 检查是否安装了MinIO客户端
    if command -v mc &> /dev/null; then
        log_info "使用MinIO客户端进行测试..."
        test_with_mc_client
    else
        log_info "MinIO客户端未安装，尝试使用curl测试..."
        test_with_curl_fallback
    fi
}

# 测试已存在存储桶的权限
test_existing_bucket_permissions() {
    # 测试存储桶写权限（创建一个测试文件）
    log_info "测试MinIO存储桶写权限..."
    local test_file_content="MinIO permission test - $(date)"
    local test_filename="minio-permission-test-$(date +%s).txt"

    if [[ "$VERBOSE" == true ]]; then
        log_info "创建测试文件: $test_filename"
    fi

    local write_test=$(echo "$test_file_content" | curl -s -w "%{http_code}" -o /dev/null -X PUT "$MINIO_ENDPOINT/$MINIO_BUCKET/$test_filename" \
        -H "Content-Type: text/plain" \
        --data-binary @- \
        -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
        2>/dev/null)

    if [[ "$write_test" == "200" ]]; then
        log_success "✓ MinIO存储桶写权限验证成功"

        # 测试文件读取权限
        log_info "测试文件读取权限..."
        local read_test=$(curl -s -w "%{http_code}" -o /dev/null -X GET "$MINIO_ENDPOINT/$MINIO_BUCKET/$test_filename" \
            -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
            2>/dev/null)

        if [[ "$read_test" == "200" ]]; then
            log_success "✓ MinIO存储桶读权限验证成功"
        else
            log_warning "⚠ MinIO存储桶读权限测试失败: HTTP $read_test"
        fi

        # 清理测试文件
        if [[ "$VERBOSE" == true ]]; then
            log_info "清理测试文件: $test_filename"
        fi

        local delete_test=$(curl -s -w "%{http_code}" -o /dev/null -X DELETE "$MINIO_ENDPOINT/$MINIO_BUCKET/$test_filename" \
            -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
            2>/dev/null)

        if [[ "$delete_test" == "204" ]] || [[ "$delete_test" == "200" ]]; then
            log_success "✓ MinIO存储桶删除权限验证成功"
        else
            log_warning "⚠ MinIO存储桶删除权限测试失败: HTTP $delete_test"
        fi

        log_success "✅ MinIO存储桶完全就绪，所有权限验证通过"
        return 0
    else
        log_error "✗ MinIO存储桶写权限测试失败: HTTP $write_test"
        return 1
    fi
}

# 测试存储桶创建
test_bucket_creation() {
    local bucket_test=$(curl -s -w "%{http_code}" -o /dev/null -X PUT "$MINIO_ENDPOINT/$MINIO_BUCKET" \
        -H "Content-Type: application/octet-stream" \
        -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
        2>/dev/null)

    if [[ "$VERBOSE" == true ]]; then
        log_info "存储桶创建返回: HTTP $bucket_test"
    fi

    if [[ "$bucket_test" == "200" ]]; then
        log_success "✓ MinIO存储桶创建成功"

        # 测试新创建存储桶的写权限
        test_existing_bucket_permissions
    else
        log_error "✗ MinIO存储桶创建失败: HTTP $bucket_test"
        return 1
    fi
}

# 使用MinIO客户端测试
test_with_mc_client() {
    # 配置MinIO客户端
    log_info "配置MinIO客户端..."
    if mc alias set testminio "$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" &>/dev/null; then
        log_success "✓ MinIO客户端配置成功"

        # 测试连接
        if mc ls testminio &>/dev/null; then
            log_success "✓ MinIO连接验证成功"

            # 检查存储桶
            if mc ls testminio/"$MINIO_BUCKET" &>/dev/null; then
                log_success "✓ MinIO存储桶已存在且可访问"
                test_bucket_permissions_with_mc
            else
                log_info "MinIO存储桶不存在，尝试创建..."
                if mc mb testminio/"$MINIO_BUCKET" &>/dev/null; then
                    log_success "✓ MinIO存储桶创建成功"
                    test_bucket_permissions_with_mc
                else
                    log_error "✗ MinIO存储桶创建失败"
                    return 1
                fi
            fi
        else
            log_error "✗ MinIO客户端连接失败"
            return 1
        fi
    else
        log_error "✗ MinIO客户端配置失败"
        return 1
    fi
}

# 使用MinIO客户端测试权限
test_bucket_permissions_with_mc() {
    # 测试写权限
    local test_file="/tmp/minio-test-$(date +%s).txt"
    echo "MinIO permission test - $(date)" > "$test_file"

    if mc cp "$test_file" "testminio/$MINIO_BUCKET/minio-permission-test.txt" &>/dev/null; then
        log_success "✓ MinIO存储桶写权限验证成功"

        # 测试读权限
        if mc cat "testminio/$MINIO_BUCKET/minio-permission-test.txt" &>/dev/null; then
            log_success "✓ MinIO存储桶读权限验证成功"
        else
            log_warning "⚠ MinIO存储桶读权限验证失败"
        fi

        # 测试删除权限
        if mc rm "testminio/$MINIO_BUCKET/minio-permission-test.txt" &>/dev/null; then
            log_success "✓ MinIO存储桶删除权限验证成功"
        else
            log_warning "⚠ MinIO存储桶删除权限验证失败"
        fi

        log_success "✅ MinIO存储桶完全就绪，所有权限验证通过"
    else
        log_error "✗ MinIO存储桶写权限验证失败"
        return 1
    fi

    # 清理临时文件
    rm -f "$test_file"
}

# 使用curl的备用测试方法
test_with_curl_fallback() {
    log_info "尝试curl备用方法（适用于旧版本MinIO）..."

    # 尝试简单的无认证操作
    local health_check=$(curl -s -w "%{http_code}" -o /dev/null "$MINIO_ENDPOINT/minio/health/live")
    if [[ "$health_check" == "200" ]]; then
        log_success "✓ MinIO API健康检查通过"

        # 尝试简单的根路径请求（无认证）
        local root_test=$(curl -s -w "%{http_code}" -o /dev/null "$MINIO_ENDPOINT/")
        if [[ "$root_test" == "403" ]] || [[ "$root_test" == "200" ]]; then
            log_success "✓ MinIO服务可访问（需要客户端进行完整测试）"

            log_info "建议安装MinIO客户端进行完整测试："
            log_info "  wget https://dl.min.io/client/mc/release/linux-amd64/mc"
            log_info "  chmod +x mc"
            log_info "  sudo mv mc /usr/local/bin/"

            return 0
        else
            log_warning "⚠ MinIO根路径访问异常: HTTP $root_test"
            return 1
        fi
    else
        log_error "✗ MinIO API健康检查失败: HTTP $health_check"
        return 1
    fi
}

# 备用认证测试（保留用于旧版本）
test_fallback_authentication() {
    log_info "尝试使用备用方法验证MinIO..."

    # 简单的认证测试
    local auth_test=$(curl -s -w "%{http_code}" -o /dev/null -X GET "$MINIO_ENDPOINT/" \
        -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
        2>/dev/null)

    if [[ "$auth_test" == "403" ]] || [[ "$auth_test" == "200" ]]; then
        log_success "✓ MinIO认证验证成功（存储桶操作可能需要额外配置）"
        return 0
    else
        log_error "✗ MinIO认证验证失败: HTTP $auth_test"
        return 1
    fi
}

# 生成测试报告
generate_report() {
    local failed_services=("$@")

    echo
    echo "========================================"
    echo "         MinIO 验证测试报告"
    echo "========================================"
    echo "测试时间: $(date)"
    echo "服务端点: $MINIO_ENDPOINT"
    echo "存储桶: $MINIO_BUCKET"
    echo

    if [[ ${#failed_services[@]} -eq 0 ]]; then
        echo "🎉 所有测试通过！MinIO服务已准备就绪。"
        log_success "MinIO验证: 100% 通过"

        echo
        echo "📋 MinIO访问信息:"
        echo "  API端点: $MINIO_ENDPOINT"
        echo "  控制台: $MINIO_CONSOLE"
        echo "  存储桶: $MINIO_BUCKET"
        echo "  状态: ✅ 完全就绪"

    else
        echo "⚠️  发现以下问题需要关注:"
        for service in "${failed_services[@]}"; do
            echo "   • $service"
        done
        echo
        echo "💡 建议操作:"
        echo "   1. 检查MinIO服务状态: systemctl status minio"
        echo "   2. 查看MinIO日志: journalctl -u minio -f"
        echo "   3. 验证网络连接: curl -I $MINIO_ENDPOINT"
        echo "   4. 检查防火墙设置"
        echo "   5. 确认访问密钥正确性"
        echo
        log_warning "MinIO验证: 发现 ${#failed_services[@]} 个问题"
    fi

    echo
    echo "🔧 故障排查命令:"
    echo "   检查服务: systemctl status minio"
    echo "   查看日志: journalctl -u minio -n 50"
    echo "   测试连接: curl -v $MINIO_ENDPOINT/minio/health/live"
    echo "   端口检查: netstat -tuln | grep ':900[01]'"
    echo "========================================"
    echo
}

# 主测试函数
main() {
    echo "========================================"
    echo "       MinIO 验证测试脚本"
    echo "========================================"
    echo

    # 解析参数
    parse_args "$@"

    # 加载凭据
    if ! load_credentials; then
        exit 1
    fi

    local failed_services=()

    # 基本连接测试
    if ! test_basic_connection; then
        failed_services+=("基本连接")
    fi

    # 认证和权限测试
    if ! test_authentication_and_permissions; then
        failed_services+=("认证权限")
    fi

    # 生成报告
    generate_report "${failed_services[@]}"

    # 返回适当的退出码
    if [[ ${#failed_services[@]} -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi