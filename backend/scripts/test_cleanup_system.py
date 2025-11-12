#!/usr/bin/env python3
"""
Processing Tasks 清理系统测试脚本

用于测试清理系统的各种功能和边界情况
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.core.database import get_sync_db_context
from app.models.processing_task import ProcessingTask
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus

def create_test_tasks():
    """创建测试任务数据"""
    print("创建测试任务数据...")

    with get_sync_db_context() as db:
        # 1. 创建超时的运行中任务 (3天前开始)
        timeout_task = ProcessingTask(
            video_id=1,  # 假设存在
            task_type=ProcessingTaskType.DOWNLOAD,
            task_name="超时测试任务",
            celery_task_id="test_timeout_123",
            status=ProcessingTaskStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(days=3),
            created_at=datetime.utcnow() - timedelta(days=3, hours=1)
        )
        db.add(timeout_task)

        # 2. 创建长期等待的任务 (1天前创建)
        pending_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.GENERATE_SRT,
            task_name="长期等待测试任务",
            celery_task_id="test_pending_456",
            status=ProcessingTaskStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(pending_task)

        # 3. 创建过期的失败任务 (10天前更新)
        expired_failure_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.EXTRACT_AUDIO,
            task_name="过期失败测试任务",
            celery_task_id="test_failure_789",
            status=ProcessingTaskStatus.FAILURE,
            error_message="测试失败",
            updated_at=datetime.utcnow() - timedelta(days=10),
            created_at=datetime.utcnow() - timedelta(days=11)
        )
        db.add(expired_failure_task)

        # 4. 创建过期的成功任务 (40天前更新)
        expired_success_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.VIDEO_SLICE,
            task_name="过期成功测试任务",
            celery_task_id="test_success_012",
            status=ProcessingTaskStatus.SUCCESS,
            updated_at=datetime.utcnow() - timedelta(days=40),
            created_at=datetime.utcnow() - timedelta(days=41)
        )
        db.add(expired_success_task)

        # 5. 创建正常的运行中任务 (30分钟前开始)
        normal_running_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.CAPCUT_EXPORT,
            task_name="正常运行测试任务",
            celery_task_id="test_normal_345",
            status=ProcessingTaskStatus.RUNNING,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            created_at=datetime.utcnow() - timedelta(minutes=35)
        )
        db.add(normal_running_task)

        # 6. 创建正常的等待任务 (30分钟前创建)
        normal_pending_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.JIANYING_EXPORT,
            task_name="正常等待测试任务",
            celery_task_id="test_normal_pending_678",
            status=ProcessingTaskStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db.add(normal_pending_task)

        # 7. 创建近期的成功任务 (1天前完成)
        recent_success_task = ProcessingTask(
            video_id=1,
            task_type=ProcessingTaskType.PROCESS_COMPLETE,
            task_name="近期成功测试任务",
            celery_task_id="test_recent_901",
            status=ProcessingTaskStatus.SUCCESS,
            updated_at=datetime.utcnow() - timedelta(days=1),
            created_at=datetime.utcnow() - timedelta(days=1, hours=2)
        )
        db.add(recent_success_task)

        db.commit()
        print("✓ 测试数据创建完成")

def show_test_tasks():
    """显示测试任务状态"""
    print("\n当前测试任务状态:")
    print("-" * 80)

    with get_sync_db_context() as db:
        test_tasks = db.query(ProcessingTask).filter(
            ProcessingTask.celery_task_id.like('test_%')
        ).all()

        for task in test_tasks:
            age_info = []
            if task.started_at:
                age_info.append(f"运行: {datetime.utcnow() - task.started_at}")
            if task.created_at:
                age_info.append(f"创建: {datetime.utcnow() - task.created_at}")
            if task.updated_at and task.updated_at != task.created_at:
                age_info.append(f"更新: {datetime.utcnow() - task.updated_at}")

            print(f"ID: {task.id:3} | 类型: {task.task_type:16} | 状态: {task.status:8} | {', '.join(age_info)}")

    print("-" * 80)

def test_dry_run():
    """测试试运行模式"""
    print("\n测试试运行模式...")

    os.system("python scripts/run_cleanup.py --dry-run")

def test_force_cleanup():
    """测试强制清理"""
    print("\n测试强制清理特定状态任务...")

    # 清理测试创建的失败任务
    os.system("python scripts/run_cleanup.py --force-status failure --older-than 5 --dry-run")
    os.system("python scripts/run_cleanup.py --force-status failure --older-than 5")

def cleanup_test_tasks():
    """清理测试任务"""
    print("\n清理测试数据...")

    with get_sync_db_context() as db:
        # 删除所有测试任务
        deleted_count = db.query(ProcessingTask).filter(
            ProcessingTask.celery_task_id.like('test_%')
        ).delete()

        db.commit()
        print(f"✓ 已删除 {deleted_count} 个测试任务")

def main():
    """主测试流程"""
    print("=" * 60)
    print("Processing Tasks 清理系统测试")
    print("=" * 60)

    try:
        # 1. 创建测试数据
        create_test_tasks()

        # 2. 显示测试数据
        show_test_tasks()

        # 3. 测试统计信息
        print("\n测试统计信息显示:")
        os.system("python scripts/run_cleanup.py --stats-only")

        # 4. 测试试运行模式
        test_dry_run()

        # 5. 等待用户确认
        input("\n按 Enter 继续执行实际清理测试...")

        # 6. 测试实际清理（使用较短的超时时间）
        print("\n测试实际清理（使用较短超时时间）:")
        os.system("python scripts/run_cleanup.py --running-timeout 0 --pending-timeout 0 --failure-retention 0 --success-retention 0")

        # 7. 显示清理后状态
        print("\n清理后的测试任务状态:")
        show_test_tasks()

        # 8. 测试强制清理
        test_force_cleanup()

        # 9. 清理剩余测试数据
        cleanup_test_tasks()

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n测试被用户中断")
        cleanup_test_tasks()
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        cleanup_test_tasks()
        raise

if __name__ == "__main__":
    main()