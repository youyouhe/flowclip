#!/usr/bin/env python3
"""
测试主应用的add任务
"""

import os
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 先导入celery_app确保应用初始化
from app.core.celery import celery_app
# 导入主应用的任务
from app.tasks.video_tasks import add

if __name__ == "__main__":
    print("测试主应用的add任务...")
    
    # 发送一个简单的加法任务
    result = add.delay(4, 4)
    print(f"任务ID: {result.id}")
    print("等待结果...")
    
    try:
        task_result = result.get(timeout=10)
        print(f"任务结果: {task_result}")
        print("✅ 主应用Celery任务执行成功!")
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")
        print("检查Redis连接和Celery Worker是否正在运行")
    
    print("\n注意: 确保主应用的Celery Worker正在运行:")
    print("   celery -A app.core.celery worker --loglevel=info --concurrency=2")