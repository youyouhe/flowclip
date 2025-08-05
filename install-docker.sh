#!/bin/bash

# Docker 安装和检查脚本
# 使用方法: ./install-docker.sh

set -e

echo "🐳 检查 Docker 安装状态..."

# 检查 Docker 是否已安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，开始安装..."
    
    # 更新包管理器
    echo "📦 更新包管理器..."
    sudo yum update -y
    
    # 安装 Docker
    echo "📥 安装 Docker..."
    sudo yum install -y docker
    
    # 启动 Docker 服务
    echo "🚀 启动 Docker 服务..."
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 添加当前用户到 docker 组
    echo "👤 添加用户到 docker 组..."
    sudo usermod -aG docker $USER
    
    echo "✅ Docker 安装完成！"
    echo "⚠️  请重新登录或运行 'newgrp docker' 来应用用户组更改"
    
else
    echo "✅ Docker 已安装"
    
    # 检查 Docker 是否运行
    if ! docker info &> /dev/null; then
        echo "❌ Docker 服务未运行，正在启动..."
        sudo systemctl start docker
        sudo systemctl enable docker
        echo "✅ Docker 服务已启动"
    else
        echo "✅ Docker 服务正在运行"
    fi
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，开始安装..."
    
    # 下载 Docker Compose
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # 添加执行权限
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo "✅ Docker Compose 安装完成！"
else
    echo "✅ Docker Compose 已安装"
fi

echo ""
echo "🎉 Docker 环境检查完成！"
echo ""
echo "📋 验证命令："
echo "   docker --version"
echo "   docker-compose --version"
echo "   docker ps"