#!/bin/bash

# YouTube Slicer 配置验证脚本
# 使用方法: ./verify-config.sh

set -e

echo "🔍 YouTube Slicer 配置验证"
echo "================================"

# 检查 .env 文件
if [ -f ".env" ]; then
    echo "✅ .env 文件存在"
    
    # 提取关键配置
    PUBLIC_IP=$(grep "PUBLIC_IP=" .env | cut -d'=' -f2)
    PRIVATE_IP=$(grep "PRIVATE_IP=" .env | .env | cut -d'=' -f2)
    MINIO_PUBLIC_ENDPOINT=$(grep "MINIO_PUBLIC_ENDPOINT=" .env | cut -d'=' -f2)
    
    echo "   📡 Public IP: $PUBLIC_IP"
    echo "   🔒 Private IP: $PRIVATE_IP"
    echo "   📦 MinIO Public Endpoint: $MINIO_PUBLIC_ENDPOINT"
    
else
    echo "❌ .env 文件不存在"
    exit 1
fi

# 检查 docker-compose.yml
if [ -f "docker-compose.yml" ]; then
    echo "✅ docker-compose.yml 存在"
    
    # 检查 IP 替换是否正确
    if grep -q "$PUBLIC_IP" docker-compose.yml; then
        echo "   ✅ docker-compose.yml 中的 IP 已正确替换"
    else
        echo "   ⚠️  docker-compose.yml 中的 IP 可能未正确替换"
    fi
    
else
    echo "❌ docker-compose.yml 不存在"
    exit 1
fi

# 检查 Docker 服务状态
echo ""
echo "🐳 检查 Docker 服务状态..."

if docker-compose ps | grep -q "Up"; then
    echo "✅ Docker 服务正在运行"
    
    # 显示各服务状态
    echo ""
    echo "📊 服务状态:"
    docker-compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
    
else
    echo "❌ Docker 服务未运行"
    echo "请运行: docker-compose up -d"
fi

# 测试后端健康检查
echo ""
echo "🏥 测试后端健康检查..."

if curl -f "http://localhost:8001/docs" &>/dev/null; then
    echo "✅ 后端 API 可访问"
    echo "   📖 API 文档: http://$PUBLIC_IP:8001/docs"
else
    echo "❌ 后端 API 不可访问"
fi

# 测试前端访问
echo ""
echo "🌐 测试前端访问..."

if curl -f "http://localhost:3000" &>/dev/null; then
    echo "✅ 前端可访问"
    echo "   🎯 前端地址: http://$PUBLIC_IP:3000"
else
    echo "❌ 前端不可访问"
fi

# 测试 MinIO 访问
echo ""
echo "📦 测试 MinIO 访问..."

if curl -f "http://localhost:9001" &>/dev/null; then
    echo "✅ MinIO 控制台可访问"
    echo "   🗂️  MinIO 控制台: http://$PUBLIC_IP:9001"
else
    echo "❌ MinIO 控制台不可访问"
fi

echo ""
echo "🎉 配置验证完成！"
echo ""
echo "📋 如果所有检查都通过，系统应该可以正常工作。"
echo "🔄 如果有服务未启动，请运行: docker-compose logs -f"
echo "🔧 如果需要重新配置，请运行: ./deploy.sh <public-ip>"