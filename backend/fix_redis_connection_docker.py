#!/usr/bin/env python3
"""
修复Redis连接稳定性问题，增加重试机制和连接池配置
适配Docker环境版本
"""

import sys
import os
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

from app.core.config import settings

def update_celery_config():
    """更新Celery配置，增加连接池和重试机制"""
    celery_config_path = Path("./app/core/celery.py")
    
    if not celery_config_path.exists():
        print(f"错误: Celery配置文件不存在: {celery_config_path}")
        return
    
    with open(celery_config_path, "r") as f:
        content = f.read()
    
    # 添加更健壮的Redis连接配置
    updated_content = """from celery import Celery
from app.core.config import settings

# 增加Redis连接池和重试配置
broker_pool_limit = 10  # 连接池大小
broker_connection_timeout = 30  # 连接超时时间
broker_connection_retry = True  # 启用连接重试
broker_connection_max_retries = 10  # 最大重试次数
task_acks_late = True  # 任务完成后才确认
task_reject_on_worker_lost = True  # 当worker丢失时拒绝任务

celery_app = Celery(
    "youtube_slicer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.video_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    broker_transport_options={
        'visibility_timeout': 3600,  # 1小时
        'max_retries': 10,
        'interval_start': 0,
        'interval_step': 1,
        'interval_max': 30,
    },
    worker_prefetch_multiplier=1,  # 限制每个worker的预取任务数量
)

if __name__ == "__main__":
    celery_app.start()
"""
    
    # 创建备份
    backup_path = celery_config_path.with_suffix(".py.bak")
    with open(backup_path, "w") as f:
        f.write(content)
    print(f"原Celery配置已备份到: {backup_path}")
    
    # 写入更新后的配置
    with open(celery_config_path, "w") as f:
        f.write(updated_content)
    print(f"Celery配置已更新: {celery_config_path}")

def create_restart_script():
    """创建重启Docker中的Redis和Celery的脚本"""
    script_content = """#!/bin/bash
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
"""
    
    script_path = Path("./restart_services.sh")
    with open(script_path, "w") as f:
        f.write(script_content)
    
    # 添加可执行权限
    os.chmod(script_path, 0o755)
    
    print(f"重启脚本已创建: {script_path.absolute()}")
    print("使用以下命令重启服务:")
    print("./restart_services.sh")

if __name__ == "__main__":
    print("===== 修复Redis连接和Celery配置（Docker版） =====")
    update_celery_config()
    create_restart_script()
    print("\n所有修复已完成。请执行以下步骤:")
    print("1. 运行 ./restart_services.sh 重启Docker中的Redis和Celery服务")
    print("2. 重启FastAPI服务器: uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
    print("3. 如果Redis或Celery出现问题，也可以使用 python fix_audio_extract.py <视频ID> 直接提取音频")