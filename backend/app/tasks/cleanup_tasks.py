"""
Celery 定时清理任务
定期清理 processing_tasks 表中的僵尸任务和过期记录
"""

import logging
from celery import Celery
from datetime import datetime

from app.core.celery import celery_app
from scripts.cleanup_processing_tasks import ProcessingTasksCleaner

# 配置日志
logger = logging.getLogger(__name__)

@celery_app.task(
    name="cleanup_processing_tasks",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5分钟后重试
)
def cleanup_processing_tasks_task(self):
    """
    定期清理 processing_tasks 任务的 Celery 任务

    清理策略:
    - 超时运行中的任务 (超过24小时)
    - 长期等待中的任务 (超过2小时)
    - 过期的失败任务 (保留7天)
    - 过期的成功任务 (保留30天)
    """
    try:
        logger.info("开始执行定期清理 processing_tasks 任务")

        # 创建清理器，使用生产环境配置
        cleaner = ProcessingTasksCleaner(
            running_timeout_hours=24,      # 运行中任务超时时间
            pending_timeout_hours=2,       # 等待中任务超时时间
            failure_retention_days=7,      # 失败任务保留天数
            success_retention_days=30,     # 成功任务保留天数
            batch_size=1000,               # 批处理大小
            dry_run=False,                 # 实际执行清理
        )

        # 执行清理
        result = cleaner.run_cleanup()

        logger.info(f"清理任务完成: {result}")

        # 返回清理结果
        return {
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'total_processed': result['total_processed'],
            'total_success': result['total_success'],
            'total_failed': result['total_failed'],
            'cleanup_details': result['cleanup_results']
        }

    except Exception as exc:
        logger.error(f"清理任务执行失败: {exc}")

        # 重试逻辑
        if self.request.retries < self.max_retries:
            logger.info(f"将在 {self.default_retry_delay} 秒后重试 (第 {self.request.retries + 1} 次)")
            raise self.retry(exc=exc)
        else:
            logger.error("清理任务重试次数已达上限，任务失败")
            raise

@celery_app.task(
    name="cleanup_processing_tasks_dry_run",
    bind=True,
)
def cleanup_processing_tasks_dry_run_task(self):
    """
    试运行清理任务 - 仅查看需要清理的任务，不实际执行
    """
    try:
        logger.info("开始执行试运行清理 processing_tasks 任务")

        # 创建清理器，使用试运行模式
        cleaner = ProcessingTasksCleaner(
            running_timeout_hours=24,
            pending_timeout_hours=2,
            failure_retention_days=7,
            success_retention_days=30,
            batch_size=1000,
            dry_run=True,  # 试运行模式
        )

        # 执行清理
        result = cleaner.run_cleanup()

        logger.info(f"试运行清理任务完成: {result}")

        return {
            'status': 'dry_run_success',
            'timestamp': datetime.utcnow().isoformat(),
            'total_processed': result['total_processed'],
            'total_success': result['total_success'],
            'cleanup_details': result['cleanup_results']
        }

    except Exception as exc:
        logger.error(f"试运行清理任务执行失败: {exc}")
        raise

# Celery Beat 定时任务配置示例
# 在 celeryconfig.py 中添加以下配置:
#
# beat_schedule = {
#     'cleanup-processing-tasks': {
#         'task': 'cleanup_processing_tasks',
#         'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点执行
#         'options': {
#             'queue': 'cleanup',
#         }
#     },
#     'cleanup-processing-tasks-dry-run': {
#         'task': 'cleanup_processing_tasks_dry_run',
#         'schedule': crontab(hour=1, minute=0),  # 每天凌晨1点试运行
#         'options': {
#             'queue': 'cleanup',
#         }
#     }
# }