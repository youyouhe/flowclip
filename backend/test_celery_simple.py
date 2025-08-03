#!/usr/bin/env python3
"""
一个简单的Celery任务测试，用于检查Celery与Redis连接是否正常
"""

import os
from celery import Celery
from dotenv import load_dotenv
import time

# 加载环境变量
load_dotenv()

# 获取Redis URL
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
print(f"使用Redis URL: {redis_url}")

# 创建一个简单的Celery实例
app = Celery(
    'test_celery',
    broker=redis_url,
    backend=redis_url
)

# 最简单的配置
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
)

@app.task
def add(x, y):
    """简单的加法任务"""
    print(f"执行任务: {x} + {y}")
    return x + y

@app.task
def hello_world():
    """简单的问候任务"""
    time.sleep(2)  # 模拟处理时间
    print("Hello, World!")
    return "Hello, World!"

if __name__ == '__main__':
    print("发送测试任务...")
    
    # 发送一个简单的加法任务
    result = add.delay(4, 4)
    print(f"任务ID: {result.id}")
    print("等待结果...")
    
    try:
        task_result = result.get(timeout=5)
        print(f"任务结果: {task_result}")
        print("✅ Celery任务执行成功!")
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")
        print("检查Redis连接和Celery Worker是否正在运行")
    
    print("\n使用说明:")
    print("1. 先启动一个Celery Worker:")
    print("   celery -A test_celery_simple worker --loglevel=info")
    print("\n2. 然后在另一个终端运行此脚本:")
    print("   python test_celery_simple.py")