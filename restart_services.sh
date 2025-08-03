#!/bin/bash
echo "🔄 统一所有服务到localhost配置..."

# 停止所有相关服务
echo "停止Celery worker..."
pkill -f "celery worker" || true

echo "停止Redis..."
pkill -f "redis-server" || true

echo "停止MinIO..."
pkill -f "minio server" || true

# 启动服务
echo "启动Redis..."
redis-server --daemonize yes

echo "启动MinIO..."
minio server /data --console-address :9001 &

echo "等待服务启动..."
sleep 3

echo "启动Celery worker..."
cd backend
source .env
nohup celery -A app.core.celery worker --loglevel=info &

echo "✅ 所有服务已重新启动，现在统一使用localhost配置"