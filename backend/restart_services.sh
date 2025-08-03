#!/bin/bash
# 重启Docker中的Redis和Celery服务

# Docker容器名称（根据docker-compose.yml）
REDIS_CONTAINER="backend_redis_1"

echo "重启Docker中的Redis服务..."
if docker ps | grep -q "${REDIS_CONTAINER}"; then
    echo "重启Redis容器: ${REDIS_CONTAINER}"
    docker restart ${REDIS_CONTAINER}
else
    echo "Redis容器未运行，尝试启动Docker Compose服务..."
    docker-compose -f ./docker-compose.yml up -d redis
fi

# 等待Redis服务就绪
echo "等待Redis服务就绪..."
sleep 3

# 检查Redis连接
echo "检查Redis连接..."
if docker exec ${REDIS_CONTAINER} redis-cli ping | grep -q "PONG"; then
    echo "Redis服务正常运行！"
else
    echo "Redis服务无响应，请检查Docker容器状态！"
    docker logs ${REDIS_CONTAINER}
    exit 1
fi

echo "停止现有Celery worker..."
pkill -f "celery -A app.core.celery worker" || echo "Celery worker可能没有运行"
sleep 2

echo "启动Celery worker..."
cd $(dirname $0)
source ~/miniconda3/etc/profile.d/conda.sh
conda activate youtube-slicer
celery -A app.core.celery worker --loglevel=info --concurrency=2 &

echo "Celery worker已启动"
echo "请重启FastAPI服务器以应用所有更改:"
echo "uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

exit 0
