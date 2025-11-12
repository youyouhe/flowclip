#!/usr/bin/env python3
"""
Processing Tasks 清理手动执行脚本

使用方法:
1. 直接执行清理:
   python scripts/run_cleanup.py

2. 试运行模式（仅查看，不执行）:
   python scripts/run_cleanup.py --dry-run

3. 自定义参数:
   python scripts/run_cleanup.py --running-timeout 12 --failure-retention 3

4. 查看统计信息:
   python scripts/run_cleanup.py --stats-only

5. 强制清理特定任务:
   python scripts/run_cleanup.py --force-status failure --older-than 5
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def show_stats(db):
    """显示当前任务统计信息"""
    from app.models.processing_task import ProcessingTask, ProcessingTaskStatus
    from app.core.constants import ProcessingTaskType

    print("\n" + "=" * 50)
    print("Processing Tasks 当前统计信息")
    print("=" * 50)

    # 总任务数
    total_tasks = db.query(ProcessingTask).count()
    print(f"总任务数: {total_tasks}")

    # 按状态统计
    print(f"\n按状态统计:")
    for status in ProcessingTaskStatus:
        count = db.query(ProcessingTask).filter(ProcessingTask.status == status).count()
        percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
        print(f"  {status:12} : {count:6} ({percentage:5.1f}%)")

    # 按类型统计
    print(f"\n按类型统计:")
    for task_type in ProcessingTaskType:
        count = db.query(ProcessingTask).filter(ProcessingTask.task_type == task_type).count()
        percentage = (count / total_tasks * 100) if total_tasks > 0 else 0
        print(f"  {task_type:16} : {count:6} ({percentage:5.1f}%)")

    # 最近24小时的任务统计
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_tasks = db.query(ProcessingTask).filter(ProcessingTask.created_at >= yesterday).count()
    print(f"\n最近24小时创建的任务: {recent_tasks}")

    # 超时任务统计
    running_timeout = datetime.utcnow() - timedelta(hours=24)
    timeout_running = db.query(ProcessingTask).filter(
        ProcessingTask.status == ProcessingTaskStatus.RUNNING,
        ProcessingTask.started_at < running_timeout,
        ProcessingTask.started_at.isnot(None)
    ).count()

    pending_timeout = datetime.utcnow() - timedelta(hours=2)
    long_pending = db.query(ProcessingTask).filter(
        ProcessingTask.status == ProcessingTaskStatus.PENDING,
        ProcessingTask.created_at < pending_timeout
    ).count()

    print(f"\n需要关注的任务:")
    print(f"  超时运行中的任务 (>24小时): {timeout_running}")
    print(f"  长期等待中的任务 (>2小时): {long_pending}")

    print("=" * 50)
    return total_tasks, timeout_running, long_pending

def force_cleanup_by_status(db, status: str, older_than_days: int, dry_run: bool = False):
    """强制清理特定状态的任务"""
    from app.models.processing_task import ProcessingTask, ProcessingTaskStatus

    cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

    # 验证状态
    if status not in [s.value for s in ProcessingTaskStatus]:
        print(f"错误: 无效的状态 '{status}'")
        print(f"有效状态: {[s.value for s in ProcessingTaskStatus]}")
        return 0, 0

    # 查询任务
    tasks = db.query(ProcessingTask).filter(
        ProcessingTask.status == status,
        ProcessingTask.updated_at < cutoff_date,
        ProcessingTask.updated_at.isnot(None)
    ).all()

    if not tasks:
        print(f"没有找到状态为 '{status}' 且超过 {older_than_days} 天的任务")
        return 0, 0

    print(f"找到 {len(tasks)} 个状态为 '{status}' 且超过 {older_than_days} 天的任务")

    success_count = 0
    for task in tasks:
        if dry_run:
            print(f"[DRY RUN] 将删除任务 {task.id} ({task.task_type}) - 状态: {task.status}")
            success_count += 1
        else:
            try:
                task_id = task.id
                db.delete(task)
                print(f"已删除任务 {task_id} ({task.task_type})")
                success_count += 1
            except Exception as e:
                print(f"删除任务 {task.id} 失败: {e}")

    return len(tasks), success_count

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='手动执行 Processing Tasks 清理',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s                                    # 执行标准清理
  %(prog)s --dry-run                          # 试运行模式
  %(prog)s --running-timeout 12               # 自定义运行超时时间
  %(prog)s --stats-only                       # 仅显示统计信息
  %(prog)s --force-status failure 5           # 强制清理5天前的失败任务
        """
    )

    # 基本选项
    parser.add_argument('--dry-run', action='store_true',
                      help='试运行模式，仅显示将要执行的操作，不实际修改数据')

    # 清理参数
    parser.add_argument('--running-timeout', type=int, default=24,
                      help='运行中任务超时时间（小时，默认: 24）')
    parser.add_argument('--pending-timeout', type=int, default=2,
                      help='等待中任务超时时间（小时，默认: 2）')
    parser.add_argument('--failure-retention', type=int, default=7,
                      help='失败任务保留天数（默认: 7）')
    parser.add_argument('--success-retention', type=int, default=30,
                      help='成功任务保留天数（默认: 30）')
    parser.add_argument('--batch-size', type=int, default=1000,
                      help='批处理大小（默认: 1000）')

    # 特殊选项
    parser.add_argument('--stats-only', action='store_true',
                      help='仅显示统计信息，不执行清理')
    parser.add_argument('--force-status', type=str,
                      help='强制清理特定状态的任务 (pending/running/success/failure/retry/revoked)')
    parser.add_argument('--older-than', type=int,
                      help='配合 --force-status 使用，清理多少天前的任务')

    args = parser.parse_args()

    # 验证强制清理参数
    if (args.force_status and not args.older_than) or (not args.force_status and args.older_than):
        parser.error("--force-status 和 --older-than 必须同时使用")

    try:
        # 导入清理器和数据库连接
        from scripts.cleanup_processing_tasks import ProcessingTasksCleaner
        from app.core.database import get_sync_db_context

        with get_sync_db_context() as db:
            # 显示统计信息
            total_tasks, timeout_running, long_pending = show_stats(db)

            # 如果只需要统计信息
            if args.stats_only:
                return

            # 检查是否需要清理
            if timeout_running == 0 and long_pending == 0 and not args.force_status:
                print("\n没有发现需要清理的任务。")
                print("如需强制清理，请使用 --force-status 参数。")
                return

            # 强制清理特定状态的任务
            if args.force_status:
                print(f"\n强制清理状态为 '{args.force_status}' 且超过 {args.older_than} 天的任务:")
                total_processed, total_success = force_cleanup_by_status(
                    db, args.force_status, args.older_than, args.dry_run
                )
            else:
                # 执行标准清理流程
                print(f"\n开始执行清理流程:")
                print(f"  - 运行中任务超时: {args.running_timeout} 小时")
                print(f"  - 等待中任务超时: {args.pending_timeout} 小时")
                print(f"  - 失败任务保留: {args.failure_retention} 天")
                print(f"  - 成功任务保留: {args.success_retention} 天")
                print(f"  - 试运行模式: {args.dry_run}")
                print()

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
                result = cleaner.run_cleanup()
                total_processed = result['total_processed']
                total_success = result['total_success']

            # 提交更改（如果不是试运行）
            if not args.dry_run and total_success > 0:
                try:
                    db.commit()
                    print(f"\n✓ 数据库更改已提交")
                except Exception as e:
                    print(f"\n✗ 提交数据库更改失败: {e}")
                    db.rollback()
                    return 1
            elif args.dry_run:
                print(f"\n[DRY RUN] 试运行模式，未提交任何更改")

            # 显示清理结果
            print(f"\n清理结果:")
            print(f"  总处理任务数: {total_processed}")
            print(f"  成功操作数: {total_success}")
            print(f"  失败操作数: {total_processed - total_success}")

            if args.force_status:
                print(f"\n✓ 强制清理完成")
            else:
                print(f"\n✓ 标准清理流程完成")

            return 0 if total_processed == total_success else 1

    except KeyboardInterrupt:
        print("\n\n清理被用户中断")
        return 1
    except Exception as e:
        print(f"\n清理过程中发生错误: {e}")
        logger.exception("清理过程异常")
        return 1

if __name__ == "__main__":
    sys.exit(main())