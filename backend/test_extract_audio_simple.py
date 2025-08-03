#!/usr/bin/env python3
"""
测试extract_audio任务的基本调用
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
from app.tasks.video_tasks import extract_audio

if __name__ == "__main__":
    print("测试extract_audio任务...")
    
    # 使用简单的测试参数
    test_params = {
        'video_id': 'test_video_123',
        'project_id': 1,
        'user_id': 1,
        'video_minio_path': 'test/video.mp4'
    }
    
    print(f"发送任务参数: {test_params}")
    
    try:
        # 发送任务
        result = extract_audio.delay(
            video_id=test_params['video_id'],
            project_id=test_params['project_id'],
            user_id=test_params['user_id'],
            video_minio_path=test_params['video_minio_path']
        )
        print(f"任务ID: {result.id}")
        print("等待结果...")
        
        # 等待结果（可能需要更长时间）
        task_result = result.get(timeout=30)
        print(f"任务结果: {task_result}")
        print("✅ extract_audio任务执行成功!")
        
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n注意: 确保主应用的Celery Worker正在运行")
    print("   celery -A app.core.celery worker --loglevel=info --concurrency=2")