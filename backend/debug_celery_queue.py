#!/usr/bin/env python3
"""
Celery队列调试工具
用于检查Redis队列状态和任务积压情况
"""

import os
import sys
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

from app.core.celery import celery_app
from celery import current_app

def inspect_queue():
    """检查Celery队列状态"""
    try:
        # 获取inspect实例
        inspect = celery_app.control.inspect()

        print("=== Celery Worker状态 ===")
        # 检查活跃的workers
        active_workers = inspect.active()
        if active_workers:
            for worker_name, tasks in active_workers.items():
                print(f"Worker: {worker_name}")
                print(f"  活跃任务数: {len(tasks)}")
                for task in tasks:
                    print(f"    - {task.get('name', 'Unknown')} (ID: {task.get('id', 'Unknown')})")
        else:
            print("没有活跃的worker")

        print("\n=== 预定任务 ===")
        # 检查预定的任务
        scheduled_tasks = inspect.scheduled()
        if scheduled_tasks:
            for worker_name, tasks in scheduled_tasks.items():
                print(f"Worker: {worker_name}")
                print(f"  预定任务数: {len(tasks)}")
                for task in tasks:
                    print(f"    - {task.get('request', {}).get('task', 'Unknown')} (ETA: {task.get('eta', 'Unknown')})")
        else:
            print("没有预定任务")

        print("\n=== 保留任务 ===")
        # 检查保留的任务
        reserved_tasks = inspect.reserved()
        if reserved_tasks:
            for worker_name, tasks in reserved_tasks.items():
                print(f"Worker: {worker_name}")
                print(f"  保留任务数: {len(tasks)}")
                for task in tasks:
                    print(f"    - {task.get('name', 'Unknown')} (ID: {task.get('id', 'Unknown')})")
        else:
            print("没有保留任务")

        # 检查队列长度
        print("\n=== Redis队列状态 ===")
        with celery_app.connection() as conn:
            try:
                # 检查默认队列
                default_queue_length = conn.default_channel.client.llen('celery')
                print(f"默认队列(celery)长度: {default_queue_length}")

                # 检查是否有其他队列
                queues = celery_app.conf.task_routes
                if queues:
                    for queue_name in queues.values():
                        if isinstance(queue_name, dict):
                            queue_name = queue_name.get('queue', 'default')
                        if queue_name != 'celery':
                            queue_length = conn.default_channel.client.llen(queue_name)
                            print(f"队列({queue_name})长度: {queue_length}")

            except Exception as e:
                print(f"检查Redis队列失败: {e}")

        print("\n=== 统计信息 ===")
        # 获取worker统计信息
        stats = inspect.stats()
        if stats:
            for worker_name, stat in stats.items():
                print(f"Worker: {worker_name}")
                print(f"  池大小: {stat.get('pool', {}).get('max-concurrency', 'Unknown')}")
                print(f"  总处理任务数: {stat.get('total', 'Unknown')}")
        else:
            print("无法获取统计信息")

    except Exception as e:
        print(f"检查队列状态失败: {e}")
        import traceback
        traceback.print_exc()

def purge_queue(queue_name='celery'):
    """清空指定队列（谨慎使用）"""
    confirm = input(f"确定要清空队列 '{queue_name}' 吗？(yes/no): ")
    if confirm.lower() != 'yes':
        print("操作取消")
        return

    try:
        with celery_app.connection() as conn:
            purged_count = conn.default_channel.client.delete(queue_name)
            print(f"已清空队列 '{queue_name}'，删除了 {purged_count} 个任务")
    except Exception as e:
        print(f"清空队列失败: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Celery队列调试工具')
    parser.add_argument('--inspect', action='store_true', help='检查队列状态')
    parser.add_argument('--purge', type=str, help='清空指定队列')

    args = parser.parse_args()

    if args.inspect:
        inspect_queue()
    elif args.purge:
        purge_queue(args.purge)
    else:
        inspect_queue()