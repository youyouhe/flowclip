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
FRONTEND_URL=http://frontend:3000

# Backend API URL (used by frontend to call backend)
API_URL=http://backend:8001

# Database Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer?charset=utf8mb4

# Redis Configuration
REDIS_URL=redis://redis:6379

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=http://$PUBLIC_IP:9000
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

# 替换 docker-compose.yml 中的占位符
echo "🔄 更新 docker-compose.yml 配置..."
if [ -f "docker-compose.yml" ]; then
    # 备份原文件
    cp docker-compose.yml docker-compose.yml.backup
    # 替换占位符
    sed -i "s/__PUBLIC_IP__/$PUBLIC_IP/g" docker-compose.yml
    echo "✅ docker-compose.yml 已更新"
else
    echo "⚠️  docker-compose.yml 未找到，跳过更新"
fi

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
echo "🌐 外部访问地址 (Public IP):"
echo "   前端: http://$PUBLIC_IP:3000"
echo "   后端 API: http://$PUBLIC_IP:8001"
echo "   API 文档: http://$PUBLIC_IP:8001/docs"
echo "   MinIO 控制台: http://$PUBLIC_IP:9001"
echo ""
echo "🔒 内部服务通信 (Docker 网络):"
echo "   Frontend: http://frontend:3000"
echo "   Backend: http://backend:8001"
echo "   MinIO: http://minio:9000"
echo ""
echo "📋 部署特性:"
echo "   ✅ 自动配置 MinIO 双端点 (内部/外部)"
echo "   ✅ 修复 CORS 跨域问题"
echo "   ✅ UTF-8 字符集支持 (中文)"
echo "   ✅ WebSocket 实时进度更新"
echo "   ✅ Docker 内部服务发现"
echo ""
echo "📋 管理命令:"
echo "   查看日志: docker-compose logs -f"
echo "   查看状态: docker-compose ps"
echo "   重新构建: docker-compose up -d --build"
echo "   停止服务: docker-compose down"
echo ""
echo "🔧 配置文件:"
echo "   .env: 环境变量配置"
echo "   docker-compose.yml: Docker 服务配置"
echo "   docker-compose.yml.backup: 原始配置备份"