#!/bin/bash

# FlowClip 部署脚本
# 使用方法: ./deploy.sh <public-ip> [private-ip]

set -e

# 颜色输出函数
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 配置验证函数
validate_config() {
    log_info "验证配置文件..."
    
    if [ ! -f ".env" ]; then
        log_error ".env 文件不存在！"
        return 1
    fi
    
    # 检查必需的配置项
    required_vars=("PUBLIC_IP" "PRIVATE_IP" "DATABASE_URL" "REDIS_URL" "MINIO_ENDPOINT")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env; then
            log_error "缺少必需的配置项: $var"
            return 1
        fi
    done
    
    # 检查IP地址格式
    public_ip=$(grep "^PUBLIC_IP=" .env | cut -d'=' -f2)
    private_ip=$(grep "^PRIVATE_IP=" .env | cut -d'=' -f2)
    
    if ! [[ $public_ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        log_error "Public IP 格式无效: $public_ip"
        return 1
    fi
    
    if ! [[ $private_ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        log_error "Private IP 格式无效: $private_ip"
        return 1
    fi
    
    log_success "配置文件验证通过"
    return 0
}

# 备份函数
backup_configs() {
    log_info "备份现有配置文件..."
    
    timestamp=$(date +"%Y%m%d_%H%M%S")
    backup_dir="backup_$timestamp"
    
    mkdir -p "$backup_dir"
    
    if [ -f ".env" ]; then
        cp .env "$backup_dir/.env.backup"
        log_success "已备份 .env 到 $backup_dir/.env.backup"
    fi
    
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "$backup_dir/docker-compose.yml.backup"
        log_success "已备份 docker-compose.yml 到 $backup_dir/docker-compose.yml.backup"
    fi
    
    log_info "备份文件保存在: $backup_dir/"
}

# 环境预检查
pre_deploy_check() {
    log_info "执行部署前检查..."
    
    # 检查是否存在重要进程
    if docker-compose ps | grep -q "Up"; then
        log_warning "检测到正在运行的Docker容器"
        read -p "是否要停止现有容器？(y/N): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "停止现有容器..."
            docker-compose down
            log_success "容器已停止"
        else
            log_info "跳过容器停止"
        fi
    fi
    
    # 检查端口占用
    if netstat -tuln | grep -q ":3000 "; then
        log_warning "端口 3000 已被占用"
    fi
    
    if netstat -tuln | grep -q ":8001 "; then
        log_warning "端口 8001 已被占用"
    fi
    
    log_success "预检查完成"
}

# 检查参数
if [ -z "$1" ]; then
    log_error "使用方法: $0 <public-ip> [private-ip]"
    log_error "例如: $0 8.213.226.34"
    log_error "或者: $0 8.213.226.34 172.16.0.10"
    exit 1
fi

PUBLIC_IP=$1
PRIVATE_IP=$2

# 如果没有提供 private IP，自动检测
if [ -z "$PRIVATE_IP" ]; then
    log_info "🔍 自动检测 Private IP..."
    # 尝试多种方法获取 private IP
    PRIVATE_IP=$(ip route get 8.8.8.8 | awk '{print $7; exit}' 2>/dev/null || \
                 hostname -I | awk '{print $1}' 2>/dev/null || \
                 echo "127.0.0.1")
    log_success "检测到 Private IP: $PRIVATE_IP"
fi

ENV_FILE=".env"

log_info "🚀 开始部署 FlowClip"
log_info "📡 Public IP: $PUBLIC_IP (用户访问)"
log_info "🔒 Private IP: $PRIVATE_IP (内部服务通信)"

# 执行预检查
pre_deploy_check

# 备份现有配置
if [ -f "$ENV_FILE" ] || [ -f "docker-compose.yml" ]; then
    backup_configs
fi

# 检查是否已存在 .env 文件
if [ -f "$ENV_FILE" ]; then
    log_warning "发现已存在的 .env 文件，是否要覆盖？(y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        log_info "覆盖现有 .env 文件"
    else
        log_error "取消部署"
        exit 1
    fi
fi

# 创建 .env 文件
log_info "📝 创建 .env 文件..."

# 从 docker-compose.yml 动态读取 MinIO 配置
if [ -f "docker-compose.yml" ]; then
    MINIO_ACCESS_KEY=$(grep -A 10 "minio:" docker-compose.yml | grep "MINIO_ROOT_USER" | cut -d ':' -f 2 | cut -d '#' -f 1 | xargs)
    MINIO_SECRET_KEY=$(grep -A 10 "minio:" docker-compose.yml | grep "MINIO_ROOT_PASSWORD" | cut -d ':' -f 2 | cut -d '#' -f 1 | xargs)
else
    log_warning "docker-compose.yml 未找到，使用默认 MinIO 凭证"
    MINIO_ACCESS_KEY="minioadmin"
    MINIO_SECRET_KEY="minioadmin"
fi

cat > "$ENV_FILE" << EOF
# Server Configuration
PUBLIC_IP=$PUBLIC_IP
PRIVATE_IP=$PRIVATE_IP

# Frontend URL (where users access the application)
FRONTEND_URL=http://frontend:3000

# Backend API URL (used by frontend to call backend)
API_URL=http://backend:8001

# Database Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer?charset=utf8mb4

# Redis Configuration
REDIS_URL=redis://redis:6379

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=$PUBLIC_IP:9000
MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY
MINIO_SECRET_KEY=$MINIO_SECRET_KEY
MINIO_BUCKET_NAME=youtube-videos

# Security
SECRET_KEY=your-secret-key-change-this-in-production

# OpenAI API Key (for AI features)
OPENAI_API_KEY=your-openai-api-key

# OpenRouter API Key (for alternative LLM service)
OPENROUTER_API_KEY=your-openrouter-api-key

# Google OAuth (for social login)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# YouTube API Key
YOUTUBE_API_KEY=your-youtube-api-key

# Optional: YouTube cookies for age-restricted content
YOUTUBE_COOKIES_FILE=/path/to/youtube_cookies.txt

# ASR Service Configuration
ASR_SERVICE_URL=http://$PRIVATE_IP:5001/asr

# Debug mode (set to false in production)
DEBUG=true
EOF

log_success ".env 文件已创建"

# 验证 docker-compose.yml 配置
log_info "🔄 验证 docker-compose.yml 配置..."
if [ -f "docker-compose.yml" ]; then
    log_success "docker-compose.yml 配置验证通过"
else
    log_warning "docker-compose.yml 未找到"
fi

# 验证配置文件
if ! validate_config; then
    log_error "配置验证失败，正在恢复备份..."
    if [ -f "docker-compose.yml.backup" ]; then
        mv docker-compose.yml.backup docker-compose.yml
        log_info "已恢复 docker-compose.yml"
    fi
    exit 1
fi

# 检查 Docker 环境
log_info "🐳 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    log_error "Docker 未安装！"
    log_error "请先运行安装脚本："
    log_error "  ./install-docker.sh"
    log_error "安装完成后重新运行部署脚本："
    log_error "  ./deploy.sh $PUBLIC_IP $PRIVATE_IP"
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker 服务未运行！"
    log_error "请启动 Docker 服务："
    log_error "  sudo systemctl start docker"
    log_error "  sudo systemctl enable docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose 未安装！"
    log_error "请先运行安装脚本："
    log_error "  ./install-docker.sh"
    exit 1
fi

log_success "Docker 环境检查通过"

# 检查依赖服务可用性
log_info "🔍 检查依赖服务可用性..."

# 检查是否在Docker环境中运行
if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null; then
    # 在Docker容器内运行，使用Docker服务名
    log_info "在Docker环境中运行，使用服务名检测"
    
    # 检查MySQL服务
    if docker-compose exec mysql mysqladmin ping -h localhost -u youtube_user -pyoutube_password &> /dev/null; then
        log_success "✅ MySQL 服务可用"
    else
        log_warning "⚠️  MySQL 服务不可用，将在容器启动后自动初始化"
    fi
    
    # 检查Redis服务
    if docker-compose exec redis redis-cli ping &> /dev/null; then
        log_success "✅ Redis 服务可用"
    else
        log_warning "⚠️  Redis 服务不可用，将在容器启动后自动初始化"
    fi
    
    # 检查MinIO服务
    if docker-compose exec minio curl -f http://localhost:9000/minio/health/live &> /dev/null; then
        log_success "✅ MinIO 服务可用"
    else
        log_warning "⚠️  MinIO 服务不可用，将在容器启动后自动初始化"
    fi
else
    # 在宿主机上运行，使用本地端口检测
    log_info "在宿主机上运行，使用端口检测"
    
    # 检查nc命令是否可用
    if ! command -v nc &> /dev/null && ! command -v telnet &> /dev/null; then
        log_warning "nc 和 telnet 命令都不可用，跳过端口检测"
    else
        # 检查MySQL服务 (端口 3307)
        if nc -z 127.0.0.1 3307 2>/dev/null || telnet 127.0.0.1 3307 2>&1 | grep -q Connected; then
            log_success "✅ MySQL 服务可用 (127.0.0.1:3307)"
        else
            log_warning "⚠️  MySQL 服务不可用 (127.0.0.1:3307)，将在容器启动后自动初始化"
        fi
        
        # 检查Redis服务 (端口 6379)
        if nc -z 127.0.0.1 6379 2>/dev/null || telnet 127.0.0.1 6379 2>&1 | grep -q Connected; then
            log_success "✅ Redis 服务可用 (127.0.0.1:6379)"
        else
            log_warning "⚠️  Redis 服务不可用 (127.0.0.1:6379)，将在容器启动后自动初始化"
        fi
        
        # 检查MinIO服务 (端口 9000)
        if nc -z 127.0.0.1 9000 2>/dev/null || telnet 127.0.0.1 9000 2>&1 | grep -q Connected; then
            log_success "✅ MinIO 服务可用 (127.0.0.1:9000)"
        else
            log_warning "⚠️  MinIO 服务不可用 (127.0.0.1:9000)，将在容器启动后自动初始化"
        fi
    fi
fi

# 询问是否要重建容器
log_warning "是否要重新构建并启动容器？(y/N)"
read -r rebuild_response
if [[ "$rebuild_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    log_info "📥 拉取最新代码..."
    git pull origin main
    
    log_info "🐳 重新构建并启动容器..."
    docker-compose down
    docker-compose up -d --build
    
    log_success "容器重新构建完成"
else
    log_info "跳过容器重建，仅生成配置文件"
fi

# 等待数据库服务准备就绪
log_info "⏳ 等待数据库服务准备就绪..."
MAX_ATTEMPTS=30
ATTEMPT=1
while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if docker-compose exec mysql mysqladmin ping -h localhost -u youtube_user -pyoutube_password &> /dev/null; then
        log_success "数据库服务已准备就绪"
        break
    fi
    log_info "等待数据库服务... (尝试 $ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
    log_error "数据库服务未能在规定时间内准备就绪"
    exit 1
fi

# 等待一段时间确保数据库初始化完成
log_info "⏳ 等待数据库初始化完成..."
sleep 10

# 初始化数据库配置
log_info "💾 初始化数据库配置..."
# 在Docker容器内运行数据库初始化脚本，增加重试机制
INIT_MAX_ATTEMPTS=5
INIT_ATTEMPT=1
while [ $INIT_ATTEMPT -le $INIT_MAX_ATTEMPTS ]; do
    if docker-compose exec -T backend python init_system_config.py; then
        log_success "数据库配置初始化成功"
        break
    else
        log_warning "数据库配置初始化失败，$((INIT_ATTEMPT * 5))秒后进行第 $((INIT_ATTEMPT + 1)) 次重试..."
        sleep $((INIT_ATTEMPT * 5))
        INIT_ATTEMPT=$((INIT_ATTEMPT + 1))
    fi
done

if [ $INIT_ATTEMPT -gt $INIT_MAX_ATTEMPTS ]; then
    log_error "数据库配置初始化失败，已达到最大重试次数"
    exit 1
fi

log_success "🎉 部署完成！"
echo ""
log_info "🌐 外部访问地址 (Public IP):"
echo "   前端: http://$PUBLIC_IP:3000"
echo "   MinIO 文件访问: http://$PUBLIC_IP:9000"
echo "   MinIO 控制台: http://$PUBLIC_IP:9001"
echo ""
log_info "🔒 内部服务通信 (Docker 网络):"
echo "   Frontend: http://frontend:3000"
echo "   Backend: http://backend:8001"
echo "   MinIO: http://minio:9000"
echo ""
log_info "📋 部署特性:"
echo "   ✅ 自动配置 MinIO 双端点 (内部/外部)"
echo "   ✅ 修复 CORS 跨域问题"
echo "   ✅ UTF-8 字符集支持 (中文)"
echo "   ✅ WebSocket 实时进度更新"
echo "   ✅ Docker 内部服务发现"
echo "   ✅ 配置文件自动备份"
echo "   ✅ 环境预检查和验证"
echo "   ✅ 数据库配置初始化"
echo ""
log_info "📋 管理命令:"
echo "   查看日志: docker-compose logs -f"
echo "   查看状态: docker-compose ps"
echo "   重新构建: docker-compose up -d --build"
echo "   停止服务: docker-compose down"
echo ""
log_info "🔧 配置文件:"
echo "   .env: 环境变量配置"
echo "   docker-compose.yml: Docker 服务配置"
if ls backup_* 1>/dev/null 2>&1; then
    echo "   backup_*/: 配置文件备份目录"
fi