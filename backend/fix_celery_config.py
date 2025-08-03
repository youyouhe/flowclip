#!/usr/bin/env python3
"""
修复Celery配置，确保正确使用Redis连接信息
"""

import sys
import os
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

def update_celery_config():
    """更新Celery配置，确保正确连接Redis"""
    celery_config_path = Path("./app/core/celery.py")
    
    if not celery_config_path.exists():
        print(f"错误: Celery配置文件不存在: {celery_config_path}")
        return
    
    with open(celery_config_path, "r") as f:
        content = f.read()
    
    # 添加更健壮的Redis连接配置
    updated_content = """from celery import Celery
import os
from dotenv import load_dotenv
from app.core.config import settings

# 显式加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path)

# 确保直接从环境变量获取Redis URL
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
print(f"使用Redis URL: {redis_url}")

# 增加Redis连接池和重试配置
broker_pool_limit = 10  # 连接池大小
broker_connection_timeout = 30  # 连接超时时间
broker_connection_retry = True  # 启用连接重试
broker_connection_max_retries = 10  # 最大重试次数
task_acks_late = True  # 任务完成后才确认
task_reject_on_worker_lost = True  # 当worker丢失时拒绝任务

celery_app = Celery(
    "youtube_slicer",
    broker=redis_url,
    backend=redis_url,
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

if __name__ == "__main__":
    print("===== 修复Celery配置 =====")
    update_celery_config()
    print("\n修复已完成。请重启Celery服务:")
    print("pkill -f 'celery -A app.core.celery'")
    print("celery -A app.core.celery worker --loglevel=info --concurrency=2")