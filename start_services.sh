#!/bin/bash

# Flowclip 服务启动脚本
# 使用PM2管理所有服务进程

set -e

echo "启动 Flowclip 服务..."

# 确保日志目录存在
mkdir -p /home/flowclip/.pm2/logs

# 检查Redis服务是否运行
echo "检查Redis服务..."
if ! pgrep -x "redis-server" > /dev/null; then
    echo "启动Redis服务..."
    redis-server --daemonize yes --port 6379
    sleep 2
fi

# 检查Redis连接
echo "验证Redis连接..."
if redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis服务正常"
else
    echo "❌ Redis服务无响应，请检查Redis配置"
    exit 1
fi

# 检查MinIO服务
echo "检查MinIO服务..."
if ! pgrep -f "minio server" > /dev/null; then
    echo "启动MinIO服务..."
    export MINIO_ROOT_USER=minioadmin
    export MINIO_ROOT_PASSWORD=minioadmin123
    minio server /home/flowclip/minio-data --console-address ":9001" --address ":9000" > /dev/null 2>&1 &
    sleep 3
fi

# 停止现有的PM2进程（如果存在）
echo "停止现有服务..."
pm2 stop all || echo "没有运行中的服务"
pm2 delete all || echo "没有已删除的服务"

# 启动服务
echo "启动服务进程..."

# 启动后端服务
echo "启动后端服务..."
pm2 start ecosystem.config.js --only flowclip-backend

# 启动Celery Worker
echo "启动Celery Worker..."
pm2 start ecosystem.config.js --only flowclip-celery-worker

# 启动Celery Beat
echo "启动Celery Beat..."
pm2 start ecosystem.config.js --only flowclip-celery-beat

# 启动前端服务
echo "启动前端服务..."
pm2 start ecosystem.config.js --only flowclip-frontend

# 保存PM2配置
pm2 save

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo "检查服务状态..."
pm2 status

echo ""
echo "🎉 服务启动完成！"
echo ""
echo "📋 服务管理命令："
echo "  查看服务状态: pm2 status"
echo "  查看日志: pm2 logs"
echo "  查看特定服务日志: pm2 logs [service-name]"
echo "  重启服务: pm2 restart all"
echo "  停止服务: pm2 stop all"
echo "  重载配置: pm2 reload all"
echo ""
echo "🌐 服务访问地址："
echo "  前端: http://localhost:3000"
echo "  后端API: http://localhost:8001"
echo "  API文档: http://localhost:8001/docs"
echo "  MinIO控制台: http://localhost:9001"
echo ""
echo "🔧 如果服务启动失败，请检查日志："
echo "  pm2 logs flowclip-backend"
echo "  pm2 logs flowclip-celery-worker"
echo "  pm2 logs flowclip-celery-beat"
echo "  pm2 logs flowclip-frontend"