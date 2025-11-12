"""
Processing Tasks 清理脚本
定期清理 processing_tasks 表中的僵尸任务和过期记录

清理策略:
1. 超时运行中的任务 (RUNNING 状态超过指定时间)
2. 长期等待中的任务 (PENDING 状态超过指定时间)
3. 过期的失败任务 (FAILURE 状态，超过保留时间)
4. 过期的成功任务 (SUCCESS 状态，超过保留时间)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import get_sync_db_context
from app.models.processing_task import ProcessingTask, ProcessingTaskStatus
from app.core.constants import ProcessingTaskType

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcessingTasksCleaner:
    """Processing Tasks 清理器"""

    def __init__(
        self,
        # 清理配置
        running_timeout_hours: int = 24,      # 运行中任务超时时间（小时）
        pending_timeout_hours: int = 2,       # 等待中任务超时时间（小时）
        failure_retention_days: int = 7,      # 失败任务保留天数
        success_retention_days: int = 30,     # 成功任务保留天数

        # 批处理配置
        batch_size: int = 1000,               # 每批处理数量
        dry_run: bool = False,                # 是否为试运行模式
    ):
        self.running_timeout_hours = running_timeout_hours
        self.pending_timeout_hours = pending_timeout_hours
        self.failure_retention_days = failure_retention_days
        self.success_retention_days = success_retention_days
        self.batch_size = batch_size
        self.dry_run = dry_run

        # 计算时间阈值
        self.now = datetime.utcnow()
        self.running_timeout = self.now - timedelta(hours=running_timeout_hours)
        self.pending_timeout = self.now - timedelta(hours=pending_timeout_hours)
        self.failure_retention_cutoff = self.now - timedelta(days=failure_retention_days)
        self.success_retention_cutoff = self.now - timedelta(days=success_retention_days)

        logger.info(f"ProcessingTasksCleaner 初始化完成:")
        logger.info(f"  - 试运行模式: {self.dry_run}")
        logger.info(f"  - RUNNING 任务超时: {running_timeout_hours} 小时")
        logger.info(f"  - PENDING 任务超时: {pending_timeout_hours} 小时")
        logger.info(f"  - FAILURE 任务保留: {failure_retention_days} 天")
        logger.info(f"  - SUCCESS 任务保留: {success_retention_days} 天")

    def get_timeout_running_tasks(self, db: Session) -> List[ProcessingTask]:
        """获取超时的运行中任务"""
        return db.query(ProcessingTask).filter(
            and_(
                ProcessingTask.status == ProcessingTaskStatus.RUNNING,
                ProcessingTask.started_at < self.running_timeout,
                ProcessingTask.started_at.isnot(None)
            )
        ).all()

    def get_long_pending_tasks(self, db: Session) -> List[ProcessingTask]:
        """获取长期等待中的任务"""
        return db.query(ProcessingTask).filter(
            and_(
                ProcessingTask.status == ProcessingTaskStatus.PENDING,
                ProcessingTask.created_at < self.pending_timeout
            )
        ).all()

    def get_expired_failure_tasks(self, db: Session) -> List[ProcessingTask]:
        """获取过期的失败任务"""
        return db.query(ProcessingTask).filter(
            and_(
                ProcessingTask.status == ProcessingTaskStatus.FAILURE,
                ProcessingTask.updated_at < self.failure_retention_cutoff,
                ProcessingTask.updated_at.isnot(None)
            )
        ).all()

    def get_expired_success_tasks(self, db: Session) -> List[ProcessingTask]:
        """获取过期的成功任务"""
        return db.query(ProcessingTask).filter(
            and_(
                ProcessingTask.status == ProcessingTaskStatus.SUCCESS,
                ProcessingTask.updated_at < self.success_retention_cutoff,
                ProcessingTask.updated_at.isnot(None)
            )
        ).all()

    def mark_task_as_failed(self, db: Session, task: ProcessingTask, reason: str) -> bool:
        """将任务标记为失败"""
        try:
            old_status = task.status
            task.status = ProcessingTaskStatus.FAILURE
            task.error_message = reason
            task.completed_at = self.now
            task.duration_seconds = (
                (self.now - task.started_at).total_seconds()
                if task.started_at else 0
            )
            task.updated_at = self.now

            logger.info(f"任务 {task.id} ({task.task_type}) 状态已更新: {old_status} -> FAILURE")
            logger.info(f"  失败原因: {reason}")
            return True

        except Exception as e:
            logger.error(f"更新任务 {task.id} 状态失败: {e}")
            return False

    def delete_task(self, db: Session, task: ProcessingTask) -> bool:
        """删除任务记录"""
        try:
            task_id = task.id
            task_type = task.task_type
            task_status = task.status
            created_at = task.created_at

            db.delete(task)
            logger.info(f"已删除任务 {task_id} ({task_type}) - 状态: {task_status}, 创建时间: {created_at}")
            return True

        except Exception as e:
            logger.error(f"删除任务 {task.id} 失败: {e}")
            return False

    def process_timeout_running_tasks(self, db: Session) -> Tuple[int, int]:
        """处理超时的运行中任务"""
        tasks = self.get_timeout_running_tasks(db)
        if not tasks:
            logger.info("没有发现超时的运行中任务")
            return 0, 0

        logger.info(f"发现 {len(tasks)} 个超时的运行中任务")

        success_count = 0
        for task in tasks:
            if self.dry_run:
                logger.info(f"[DRY RUN] 将标记任务 {task.id} ({task.task_type}) 为失败 - 超时运行")
                success_count += 1
            else:
                if self.mark_task_as_failed(db, task, f"任务运行超时 (超过 {self.running_timeout_hours} 小时)"):
                    success_count += 1

        return len(tasks), success_count

    def process_long_pending_tasks(self, db: Session) -> Tuple[int, int]:
        """处理长期等待中的任务"""
        tasks = self.get_long_pending_tasks(db)
        if not tasks:
            logger.info("没有发现长期等待中的任务")
            return 0, 0

        logger.info(f"发现 {len(tasks)} 个长期等待中的任务")

        success_count = 0
        for task in tasks:
            if self.dry_run:
                logger.info(f"[DRY RUN] 将标记任务 {task.id} ({task.task_type}) 为失败 - 长期等待")
                success_count += 1
            else:
                if self.mark_task_as_failed(db, task, f"任务长期等待超时 (超过 {self.pending_timeout_hours} 小时)"):
                    success_count += 1

        return len(tasks), success_count

    def process_expired_failure_tasks(self, db: Session) -> Tuple[int, int]:
        """处理过期的失败任务"""
        tasks = self.get_expired_failure_tasks(db)
        if not tasks:
            logger.info("没有发现过期的失败任务")
            return 0, 0

        logger.info(f"发现 {len(tasks)} 个过期的失败任务")

        success_count = 0
        for task in tasks:
            if self.dry_run:
                logger.info(f"[DRY RUN] 将删除任务 {task.id} ({task.task_type}) - 过期失败任务")
                success_count += 1
            else:
                if self.delete_task(db, task):
                    success_count += 1

        return len(tasks), success_count

    def process_expired_success_tasks(self, db: Session) -> Tuple[int, int]:
        """处理过期的成功任务"""
        tasks = self.get_expired_success_tasks(db)
        if not tasks:
            logger.info("没有发现过期的成功任务")
            return 0, 0

        logger.info(f"发现 {len(tasks)} 个过期的成功任务")

        success_count = 0
        for task in tasks:
            if self.dry_run:
                logger.info(f"[DRY RUN] 将删除任务 {task.id} ({task.task_type}) - 过期成功任务")
                success_count += 1
            else:
                if self.delete_task(db, task):
                    success_count += 1

        return len(tasks), success_count

    def get_task_statistics(self, db: Session) -> Dict[str, int]:
        """获取任务统计信息"""
        stats = {}

        # 总任务数
        stats['total_tasks'] = db.query(ProcessingTask).count()

        # 按状态统计
        for status in ProcessingTaskStatus:
            stats[f'status_{status}'] = db.query(ProcessingTask).filter(
                ProcessingTask.status == status
            ).count()

        # 按类型统计
        for task_type in ProcessingTaskType:
            stats[f'type_{task_type}'] = db.query(ProcessingTask).filter(
                ProcessingTask.task_type == task_type
            ).count()

        return stats

    def run_cleanup(self) -> Dict[str, any]:
        """执行完整的清理流程"""
        logger.info("=" * 60)
        logger.info("开始 Processing Tasks 清理流程")
        logger.info("=" * 60)

        total_processed = 0
        total_success = 0
        cleanup_results = {}

        with get_sync_db_context() as db:
            # 显示清理前的统计信息
            logger.info("清理前统计信息:")
            before_stats = self.get_task_statistics(db)
            for key, value in before_stats.items():
                logger.info(f"  {key}: {value}")

            logger.info("-" * 40)

            # 1. 处理超时的运行中任务
            processed, success = self.process_timeout_running_tasks(db)
            cleanup_results['timeout_running'] = {'processed': processed, 'success': success}
            total_processed += processed
            total_success += success

            # 2. 处理长期等待中的任务
            processed, success = self.process_long_pending_tasks(db)
            cleanup_results['long_pending'] = {'processed': processed, 'success': success}
            total_processed += processed
            total_success += success

            # 3. 处理过期的失败任务
            processed, success = self.process_expired_failure_tasks(db)
            cleanup_results['expired_failure'] = {'processed': processed, 'success': success}
            total_processed += processed
            total_success += success

            # 4. 处理过期的成功任务
            processed, success = self.process_expired_success_tasks(db)
            cleanup_results['expired_success'] = {'processed': processed, 'success': success}
            total_processed += processed
            total_success += success

            if not self.dry_run:
                # 提交所有更改
                try:
                    db.commit()
                    logger.info("所有更改已提交到数据库")
                except Exception as e:
                    logger.error(f"提交数据库更改失败: {e}")
                    db.rollback()
                    raise
            else:
                logger.info("[DRY RUN] 试运行模式，未提交任何更改")

            logger.info("-" * 40)

            # 显示清理后的统计信息
            logger.info("清理后统计信息:")
            after_stats = self.get_task_statistics(db)
            for key, value in after_stats.items():
                logger.info(f"  {key}: {value}")

        logger.info("=" * 60)
        logger.info("Processing Tasks 清理流程完成")
        logger.info(f"总处理任务数: {total_processed}")
        logger.info(f"总成功操作数: {total_success}")
        logger.info(f"总失败操作数: {total_processed - total_success}")
        logger.info("=" * 60)

        return {
            'total_processed': total_processed,
            'total_success': total_success,
            'total_failed': total_processed - total_success,
            'cleanup_results': cleanup_results,
            'before_stats': before_stats,
            'after_stats': after_stats
        }

def main():
    """主函数 - 支持命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(description='清理 processing_tasks 表中的僵尸任务')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式，不实际修改数据')
    parser.add_argument('--running-timeout', type=int, default=24, help='运行中任务超时时间（小时）')
    parser.add_argument('--pending-timeout', type=int, default=2, help='等待中任务超时时间（小时）')
    parser.add_argument('--failure-retention', type=int, default=7, help='失败任务保留天数')
    parser.add_argument('--success-retention', type=int, default=30, help='成功任务保留天数')
    parser.add_argument('--batch-size', type=int, default=1000, help='批处理大小')

    args = parser.parse_args()

    # 创建清理器
    cleaner = ProcessingTasksCleaner(
        running_timeout_hours=args.running_timeout,
        pending_timeout_hours=args.pending_timeout,
        failure_retention_days=args.failure_retention,
        success_retention_days=args.success_retention,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    # 执行清理
    try:
        result = cleaner.run_cleanup()
        logger.info("清理任务完成!")

        # 如果是脚本执行，返回适当的退出码
        if result['total_failed'] > 0:
            exit(1)
        else:
            exit(0)

    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}")
        exit(1)

if __name__ == "__main__":
    main()