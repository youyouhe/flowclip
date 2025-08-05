#!/bin/bash

# YouTube Slicer 部署脚本
# 使用方法: ./deploy.sh <server-ip>

set -e

# 检查参数
if [ -z "$1" ]; then
    echo "使用方法: $0 <server-ip>"
    echo "例如: $0 8.213.226.34"
    exit 1
fi

SERVER_IP=$1
ENV_FILE=".env"

echo "🚀 开始部署 YouTube Slicer 到服务器 $SERVER_IP"

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
SERVER_IP=$SERVER_IP

# Frontend URL (where users access the application)
FRONTEND_URL=http://$SERVER_IP:3000

# Backend API URL (used by frontend to call backend)
API_URL=http://$SERVER_IP:8001

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

# 拉取最新代码
echo "📥 拉取最新代码..."
git pull origin main

# 重新构建并启动容器
echo "🐳 重新构建并启动容器..."
docker-compose down
docker-compose up -d --build

echo "🎉 部署完成！"
echo ""
echo "🌐 访问地址:"
echo "   前端: http://$SERVER_IP:3000"
echo "   后端 API: http://$SERVER_IP:8001"
echo "   API 文档: http://$SERVER_IP:8001/docs"
echo "   MinIO 控制台: http://$SERVER_IP:9001"
echo ""
echo "📋 查看日志: docker-compose logs -f"
echo "📊 查看状态: docker-compose ps"
echo "🛑 停止服务: docker-compose down"