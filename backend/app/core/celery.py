from celery import Celery
import os
from dotenv import load_dotenv
from app.core.config import settings

# 显式加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path)

# 直接从环境变量获取Redis URL，如果没有则使用设置中的值或默认值
redis_url = os.getenv('REDIS_URL') or settings.redis_url or 'redis://localhost:6379'
print(f"Celery使用Redis URL: {redis_url}")

# 确保URL格式正确，包含协议前缀
if not redis_url.startswith('redis://'):
    redis_url = f'redis://{redis_url}'

# 创建Celery应用，显式指定broker和backend
celery_app = Celery(
    "youtube_slicer",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.video_tasks",
        "app.tasks.subtasks.simple_task",
        "app.tasks.subtasks.download_task",
        "app.tasks.subtasks.audio_task",
        "app.tasks.subtasks.srt_task",
        "app.tasks.subtasks.slice_task",
        "app.tasks.subtasks.capcut_task"
    ]
)

# 基本配置
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
    
    # 增加后端容错配置
    result_backend_always_retry=True,
    result_backend_max_retries=3,
    result_backend_retry_policy={
        'timeout': 5.0,
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 2.0,
    },
    
    # 禁用结果压缩以避免序列化问题
    result_compression=False,
    
    # 简化错误处理
    eager_propagates_exceptions=True,
    task_ignore_result=False,
    
    # 防止状态更新被存储为结果
    task_store_errors_even_if_ignored=True,
)

# Broker 特定配置
celery_app.conf.update(
    # 显式指定使用Redis作为broker和backend
    broker_url=redis_url,
    result_backend=redis_url,
    
    # 指定传输类型为Redis
    broker_transport='redis',
    
    # Redis连接池设置
    broker_pool_limit=10,  # 连接池大小
    broker_connection_timeout=30,  # 连接超时时间
    
    # 重试策略
    broker_connection_retry=True,  # 启用连接重试
    broker_connection_retry_on_startup=True,  # 启动时重试连接
    broker_connection_max_retries=10,  # 最大重试次数
    
    # Redis相关选项
    broker_transport_options={
        'visibility_timeout': 3600,  # 1小时
        'max_retries': 5,
        'interval_start': 0,
        'interval_step': 1,
        'interval_max': 30,
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
    },
    
    # 任务确认设置
    task_acks_late=True,  # 任务完成后才确认
    task_reject_on_worker_lost=True,  # 当worker丢失时拒绝任务
    worker_prefetch_multiplier=1,  # 限制每个worker的预取任务数量
)

# 打印配置信息以便调试
print(f"Broker URL: {celery_app.conf.broker_url}")
print(f"Broker Transport: {celery_app.conf.broker_transport}")
print(f"Broker Transport Options: {celery_app.conf.broker_transport_options}")

# 定义重新加载系统配置的任务
@celery_app.task
def reload_system_configs():
    """重新加载系统配置的任务"""
    try:
        from app.services.system_config_service import SystemConfigService
        from app.core.database import get_sync_db
        from app.services.minio_client import minio_service
        
        # 获取数据库会话并加载配置
        db = get_sync_db()
        SystemConfigService.update_settings_from_db_sync(db)
        db.close()
        
        # 重新加载MinIO客户端配置
        minio_service.reload_config()
        
        print("系统配置已重新加载")
        return {"status": "success", "message": "系统配置已重新加载"}
    except Exception as e:
        print(f"重新加载系统配置失败: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    celery_app.start()
