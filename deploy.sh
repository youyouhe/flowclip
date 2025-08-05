#!/bin/bash

# YouTube Slicer 部署脚本
# 使用方法: ./deploy.sh <public-ip> [private-ip]

set -e

# 检查参数
if [ -z "$1" ]; then
    echo "使用方法: $0 <public-ip> [private-ip]"
    echo "例如: $0 8.213.226.34"
    echo "或者: $0 8.213.226.34 172.16.0.10"
    exit 1
fi

PUBLIC_IP=$1
PRIVATE_IP=$2

# 如果没有提供 private IP，自动检测
if [ -z "$PRIVATE_IP" ]; then
    echo "🔍 自动检测 Private IP..."
    # 尝试多种方法获取 private IP
    PRIVATE_IP=$(ip route get 8.8.8.8 | awk '{print $7; exit}' 2>/dev/null || \
                 hostname -I | awk '{print $1}' 2>/dev/null || \
                 echo "127.0.0.1")
    echo "✅ 检测到 Private IP: $PRIVATE_IP"
fi

ENV_FILE=".env"

echo "🚀 开始部署 YouTube Slicer"
echo "📡 Public IP: $PUBLIC_IP (用户访问)"
echo "🔒 Private IP: $PRIVATE_IP (内部服务通信)"

# 检查是否已存在 .env 文件
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  发现已存在的 .env 文件，是否要覆盖？(y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "📝 覆盖现有 .env 文件"
    else
        echo "❌ 取消部署"
        exit 1
    fi
fi

# 创建 .env 文件
echo "📝 创建 .env 文件..."
cat > "$ENV_FILE" << EOF
# Server Configuration
PUBLIC_IP=$PUBLIC_IP
PRIVATE_IP=$PRIVATE_IP

# Frontend URL (where users access the application)
FRONTEND_URL=http://$PUBLIC_IP:3000

# Backend API URL (used by frontend to call backend)
API_URL=http://$PUBLIC_IP:8001

# Database Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer

# Redis Configuration
REDIS_URL=redis://redis:6379

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=youtube-videos

# Security
SECRET_KEY=your-secret-key-change-this-in-production

# OpenAI API Key (for AI features)
OPENAI_API_KEY=your-openai-api-key

# Optional: YouTube cookies for age-restricted content
YOUTUBE_COOKIES_FILE=/path/to/youtube_cookies.txt

# Debug mode (set to false in production)
DEBUG=true
EOF

echo "✅ .env 文件已创建"

# 检查 Docker 环境
echo "🐳 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装！"
    echo "请先运行安装脚本："
    echo "  ./install-docker.sh"
    echo "安装完成后重新运行部署脚本："
    echo "  ./deploy.sh $PUBLIC_IP $PRIVATE_IP"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker 服务未运行！"
    echo "请启动 Docker 服务："
    echo "  sudo systemctl start docker"
    echo "  sudo systemctl enable docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装！"
    echo "请先运行安装脚本："
    echo "  ./install-docker.sh"
    exit 1
fi

echo "✅ Docker 环境检查通过"

# 拉取最新代码
echo "📥 拉取最新代码..."
git pull origin main

# 重新构建并启动容器
echo "🐳 重新构建并启动容器..."
docker-compose down
docker-compose up -d --build

echo "🎉 部署完成！"
echo ""
echo "🌐 访问地址 (Public IP):"
echo "   前端: http://$PUBLIC_IP:3000"
echo "   后端 API: http://$PUBLIC_IP:8001"
echo "   API 文档: http://$PUBLIC_IP:8001/docs"
echo "   MinIO 控制台: http://$PUBLIC_IP:9001"
echo ""
echo "🔒 内部服务通信 (Private IP): $PRIVATE_IP"
echo ""
echo "📋 查看日志: docker-compose logs -f"
echo "📊 查看状态: docker-compose ps"
echo "🛑 停止服务: docker-compose down"