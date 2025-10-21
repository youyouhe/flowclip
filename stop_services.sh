#!/bin/bash

# Flowclip 服务停止脚本

set -e

echo "停止 Flowclip 服务..."

# 停止所有PM2管理的服务
echo "停止PM2服务..."
pm2 stop all || echo "没有运行中的PM2服务"
pm2 delete all || echo "没有已删除的PM2服务"

# 可选：停止Redis和MinIO服务（根据需要）
read -p "是否停止Redis服务？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "停止Redis服务..."
    pkill -f redis-server || echo "Redis服务未运行"
fi

read -p "是否停止MinIO服务？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "停止MinIO服务..."
    pkill -f "minio server" || echo "MinIO服务未运行"
fi

echo "✅ 所有服务已停止"