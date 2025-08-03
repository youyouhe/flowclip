#!/usr/bin/env python3
"""
直接测试进度API，不依赖前端
"""

import asyncio
import aiohttp
import json
import time
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_progress_api_direct(video_id: int, token: str):
    """直接测试进度API"""
    
    base_url = "http://localhost:8001"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"🎯 直接测试视频 {video_id} 的进度API...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # 获取当前进度
            async with session.get(
                f"{base_url}/api/v1/videos/{video_id}/progress",
                headers=headers
            ) as response:
                if response.status == 200:
                    progress_data = await response.json()
                    print(f"\n📊 当前进度:")
                    print(f"   视频ID: {progress_data['video_id']}")
                    print(f"   标题: {progress_data['title']}")
                    print(f"   状态: {progress_data['status']}")
                    print(f"   下载进度: {progress_data['download_progress']:.1f}%")
                    print(f"   处理消息: {progress_data['processing_message']}")
                    print(f"   阶段: {progress_data['processing_stage']}")
                    print(f"   文件大小: {progress_data['file_size']:,} bytes")
                    
                    # 显示处理任务
                    if progress_data['processing_tasks']:
                        print(f"\n   处理任务:")
                        for task in progress_data['processing_tasks']:
                            print(f"     - {task['task_type']}: {task['status']} ({task['progress']:.1f}%)")
                    
                    return progress_data
                else:
                    print(f"   获取进度失败: {response.status}")
                    text = await response.text()
                    print(f"   错误信息: {text}")
                    return None
                    
        except Exception as e:
            print(f"❌ API测试失败: {e}")
            return None

async def monitor_progress_realtime(video_id: int, token: str, duration: int = 30):
    """实时监控进度变化"""
    
    base_url = "http://localhost:8001"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n⏱️  开始实时监控视频 {video_id} 的进度 ({duration}秒)...")
    
    last_progress = -1
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            try:
                async with session.get(
                    f"{base_url}/api/v1/videos/{video_id}/progress",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        progress_data = await response.json()
                        
                        current_progress = progress_data.get('download_progress', 0)
                        message = progress_data.get('processing_message', '无消息')
                        status = progress_data.get('status', 'unknown')
                        
                        # 只在进度变化时打印
                        if current_progress != last_progress:
                            last_progress = current_progress
                            elapsed = time.time() - start_time
                            print(f"   [{elapsed:.1f}s] 进度: {current_progress:.1f}% - {message}")
                        
                        # 检查是否完成
                        if status == "completed" or current_progress >= 100:
                            print(f"   ✅ 下载完成!")
                            return True
                        
                        # 检查是否失败
                        if status == "failed":
                            print(f"   ❌ 下载失败: {progress_data.get('processing_error', '未知错误')}")
                            return False
                    
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"监控进度时出错: {e}")
                await asyncio.sleep(2)
        
        print(f"   ⏰ 监控超时 ({duration}秒)")
        return False

async def get_test_token():
    """获取测试token"""
    base_url = "http://localhost:8001"
    
    async with aiohttp.ClientSession() as session:
        # 尝试登录获取token
        login_data = {
            "username": "hem",
            "password": "123456"
        }
        
        async with session.post(f"{base_url}/api/v1/auth/login", data=login_data) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("access_token")
            else:
                print(f"登录失败: {response.status}")
                return None

async def main():
    """主函数"""
    
    # 检查服务是否可用
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8001/docs") as response:
                if response.status != 200:
                    print("❌ 后端服务未启动或不可用")
                    return
    except:
        print("❌ 无法连接到后端服务 (http://localhost:8001)")
        print("请确保后端服务已启动: python -m backend.app.main")
        return
    
    # 获取token
    print("1. 获取测试token...")
    token = await get_test_token()
    if not token:
        print("❌ 无法获取token，使用示例token进行测试")
        # 使用示例token
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwiZXhwIjoxNzMzNjI4ODk5fQ.example"
    else:
        print("   ✅ token获取成功")
    
    # 让用户输入视频ID或自动发现
    video_id = input("\n请输入要测试的视频ID (或按回车自动发现): ").strip()
    
    if not video_id:
        # 自动发现最新的视频
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            async with session.get(f"http://localhost:8001/api/v1/videos", headers=headers) as response:
                if response.status == 200:
                    videos = await response.json()
                    if videos:
                        video_id = str(videos[0]['id'])
                        print(f"   自动发现视频ID: {video_id}")
                    else:
                        print("   没有找到视频，请手动输入ID")
                        return
                else:
                    print("   无法获取视频列表")
                    return
    
    try:
        video_id = int(video_id)
    except ValueError:
        print("❌ 无效的视频ID")
        return
    
    # 测试单次获取
    await test_progress_api_direct(video_id, token)
    
    # 询问是否进行实时监控
    monitor = input("\n是否开始实时监控进度变化? (y/n): ").strip().lower()
    if monitor == 'y':
        await monitor_progress_realtime(video_id, token, duration=6)

if __name__ == "__main__":
    asyncio.run(main())
