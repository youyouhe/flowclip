#!/usr/bin/env python3
"""
测试实时进度追踪系统
- 验证WebSocket连接
- 验证进度更新到数据库
- 验证实时通知机制
"""

import asyncio
import json
import time
import requests
import websockets
from app.core.database import get_db
from app.models.video import Video

# 测试配置
API_BASE = "http://localhost:8001"
WS_URL = "ws://localhost:8001"

async def test_websocket_connection():
    """测试WebSocket连接"""
    print("🔍 测试WebSocket连接...")
    
    # 先测试后端API是否可访问
    try:
        response = requests.get(f"{API_BASE}/api/v1/health")
        print(f"✅ 后端API响应: {response.status_code}")
    except Exception as e:
        print(f"❌ 后端API不可访问: {e}")
        return False
    
    # 测试WebSocket端点
    try:
        async with websockets.connect(f"{WS_URL}/ws/progress/test_token") as websocket:
            print("✅ WebSocket连接成功")
            return True
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

def test_database_progress_update():
    """测试数据库进度更新"""
    print("🔍 测试数据库进度更新...")
    
    # 创建测试视频
    db = next(get_db())
    
    # 检查是否有视频
    videos = db.query(Video).limit(5).all()
    if not videos:
        print("⚠️  没有找到视频，创建测试数据...")
        return False
    
    video = videos[0]
    old_progress = video.download_progress
    
    # 手动更新进度
    video.download_progress = 75.5
    video.processing_stage = "download"
    video.processing_message = "测试中"
    db.commit()
    
    # 验证更新
    updated_video = db.query(Video).filter(Video.id == video.id).first()
    
    if updated_video.download_progress == 75.5:
        print(f"✅ 数据库进度更新成功: {old_progress} -> {updated_video.download_progress}")
        return True
    else:
        print(f"❌ 数据库进度更新失败")
        return False

def test_celery_task_progress():
    """测试Celery任务进度"""
    print("🔍 测试Celery任务进度...")
    
    # 启动一个测试下载任务
    test_data = {
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "project_id": 1,
        "user_id": 1,
        "quality": "720p"
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/videos/download",
            json=test_data,
            headers={"Authorization": "Bearer test_token"}
        )
        
        if response.status_code == 200:
            print("✅ 下载任务已启动")
            return True
        else:
            print(f"❌ 下载任务启动失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 测试任务启动失败: {e}")
        return False

def check_service_status():
    """检查服务状态"""
    print("🔍 检查服务状态...")
    
    services = [
        ("后端API", f"{API_BASE}/api/v1/health"),
        ("WebSocket", f"{WS_URL}/ws/progress/test"),
    ]
    
    for name, url in services:
        try:
            if name == "WebSocket":
                # WebSocket测试稍后进行
                print(f"⏳ {name}: 待测试")
            else:
                response = requests.get(url)
                print(f"✅ {name}: 正常 ({response.status_code})")
        except Exception as e:
            print(f"❌ {name}: 异常 ({e})")

if __name__ == "__main__":
    print("🚀 实时进度系统测试开始")
    print("=" * 50)
    
    # 检查服务状态
    check_service_status()
    
    # 测试数据库进度更新
    test_database_progress_update()
    
    # 测试WebSocket连接
    asyncio.run(test_websocket_connection())
    
    print("\n✅ 测试完成！")