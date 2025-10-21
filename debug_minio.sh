#!/bin/bash

# MinIO 调试脚本
# 用于诊断MinIO配置和认证问题

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

echo "========================================"
echo "       MinIO 调试诊断脚本"
echo "========================================"
echo

# 1. 检查凭据文件
log_info "1. 检查凭据文件..."
CREDENTIALS_FILE="/root/flowclip_credentials.txt"

if [[ -f "$CREDENTIALS_FILE" ]]; then
    log_success "✓ 凭据文件存在: $CREDENTIALS_FILE"
    echo "文件内容："
    echo "----------------------------------------"
    cat "$CREDENTIALS_FILE"
    echo "----------------------------------------"
    echo

    # 解析凭据
    MINIO_ACCESS_KEY=$(grep "访问密钥:" "$CREDENTIALS_FILE" | awk '{print $3}' || echo "")
    MINIO_SECRET_KEY=$(grep "秘密密钥:" "$CREDENTIALS_FILE" | awk '{print $3}' || echo "")

    if [[ -n "$MINIO_ACCESS_KEY" ]] && [[ -n "$MINIO_SECRET_KEY" ]]; then
        log_success "✓ 凭据解析成功"
        log_info "访问密钥: ${MINIO_ACCESS_KEY:0:8}..."
        log_info "秘密密钥: ${MINIO_SECRET_KEY:0:8}..."
    else
        log_error "✗ 凭据解析失败"
        log_info "访问密钥长度: ${#MINIO_ACCESS_KEY}"
        log_info "秘密密钥长度: ${#MINIO_SECRET_KEY}"
        exit 1
    fi
else
    log_error "✗ 凭据文件不存在: $CREDENTIALS_FILE"
    exit 1
fi

# 2. 检查MinIO服务状态
log_info "2. 检查MinIO服务状态..."
if systemctl is-active --quiet minio; then
    log_success "✓ MinIO服务正在运行"
    systemctl status minio --no-pager -l
else
    log_error "✗ MinIO服务未运行"
    exit 1
fi

echo

# 3. 检查MinIO配置
log_info "3. 检查MinIO配置..."
if [[ -f "/etc/default/minio" ]]; then
    log_success "✓ MinIO配置文件存在"
    echo "配置内容："
    echo "----------------------------------------"
    cat /etc/default/minio
    echo "----------------------------------------"
    echo
else
    log_error "✗ MinIO配置文件不存在"
fi

# 4. 检查网络监听
log_info "4. 检查网络监听..."
echo "端口监听状态："
netstat -tuln | grep ':900[01]' || echo "未找到9000/9001端口监听"
echo

# 5. 基础连接测试
log_info "5. 基础连接测试..."
echo "测试1: 无认证健康检查"
curl -v -w "\n状态码: %{http_code}\n" http://localhost:9000/minio/health/live 2>&1
echo

echo "测试2: MinIO根路径访问"
curl -v -w "\n状态码: %{http_code}\n" http://localhost:9000/ 2>&1
echo

# 6. 认证测试
log_info "6. 认证测试..."
echo "测试3: 带认证的根路径访问"
curl -v -w "\n状态码: %{http_code}\n" \
    -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
    http://localhost:9000/ 2>&1
echo

echo "测试4: 列出存储桶"
curl -v -w "\n状态码: %{http_code}\n" \
    -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
    http://localhost:9000/ 2>&1
echo

# 7. 存储桶操作测试
log_info "7. 存储桶操作测试..."
echo "测试5: 检查存储桶是否存在 (HEAD)"
response_code=$(curl -s -w "%{http_code}" -o /dev/null -X HEAD \
    -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
    http://localhost:9000/youtube-videos 2>/dev/null)
echo "HEAD请求状态码: $response_code"

if [[ "$response_code" == "200" ]]; then
    log_success "✓ 存储桶存在"
elif [[ "$response_code" == "404" ]]; then
    log_info "存储桶不存在，尝试创建..."
    echo "测试6: 创建存储桶 (PUT)"
    create_response=$(curl -v -w "\n状态码: %{http_code}\n" -X PUT \
        -u "$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY" \
        http://localhost:9000/youtube-videos 2>&1)
    echo "$create_response"
else
    log_warning "⚠ 存储桶检查返回意外状态码: $response_code"
fi

echo

# 8. 使用MinIO客户端（如果可用）
log_info "8. 检查MinIO客户端..."
if command -v mc &> /dev/null; then
    log_success "✓ MinIO客户端已安装"

    echo "测试MinIO客户端配置..."
    mc alias set local http://localhost:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" || {
        log_error "✗ MinIO客户端配置失败"
    }

    if mc ls local &>/dev/null; then
        log_success "✓ MinIO客户端连接成功"
        echo "存储桶列表："
        mc ls local
    else
        log_error "✗ MinIO客户端连接失败"
    fi
else
    log_info "MinIO客户端未安装，可以安装后进行更详细的测试"
    echo "安装命令："
    echo "  wget https://dl.min.io/client/mc/release/linux-amd64/mc"
    echo "  chmod +x mc"
    echo "  sudo mv mc /usr/local/bin/"
fi

echo
echo "========================================"
echo "           调试完成"
echo "========================================"
echo
echo "常见问题解决方案："
echo
echo "1. 如果认证失败（HTTP 403）："
echo "   - 检查凭据文件中的密钥是否正确"
echo "   - 确认MinIO配置文件中的MINIO_ROOT_USER和MINIO_ROOT_PASSWORD"
echo
echo "2. 如果连接失败："
echo "   - 确认MinIO服务状态：systemctl status minio"
echo "   - 检查防火墙设置"
echo "   - 确认端口监听：netstat -tuln | grep 9000"
echo
echo "3. 如果存储桶操作失败："
echo "   - 尝试使用MinIO客户端 mc"
echo "   - 检查存储桶权限配置"
echo
echo "4. 重新创建凭据文件："
echo "   # 如果凭据有问题，可以重新生成"
echo "   systemctl restart minio"
echo "   # 检查MinIO日志获取初始凭据"
echo "   journalctl -u minio -n 20"
echo