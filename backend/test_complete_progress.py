#!/usr/bin/env python3
"""
完整进度跟踪测试脚本
"""

import asyncio
import aiohttp
import json
import time
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

class CompleteProgressTest:
    """完整进度测试类"""
    
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.test_user_id = None
        self.test_project_id = None
        self.test_video_id = None
        
    async def login_and_get_token(self, username="testuser", password="testpass"):
        """登录获取token"""
        async with aiohttp.ClientSession() as session:
            login_data = {
                "username": username,
                "password": password
            }
            
            async with session.post(f"{self.base_url}/api/v1/auth/login", data=login_data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("access_token")
                else:
                    print(f"登录失败: {response.status}")
                    return None
    
    async def create_test_project(self, token, name="测试进度项目"):
        """创建测试项目"""
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            project_data = {
                "name": name,
                "description": "用于测试进度跟踪的项目"
            }
            
            async with session.post(
                f"{self.base_url}/api/v1/projects", 
                json=project_data, 
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["id"]
                else:
                    print(f"创建项目失败: {response.status}")
                    return None
    
    async def start_video_download(self, token, project_id, url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
        """开始视频下载"""
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field("url", url)
            form_data.add_field("project_id", str(project_id))
            form_data.add_field("quality", "worst")  # 使用低质量加快测试
            
            async with session.post(
                f"{self.base_url}/api/v1/videos/download",
                data=form_data,
                headers=headers
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["id"]
                else:
                    print(f"开始下载失败: {response.status}")
                    text = await response.text()
                    print(f"错误信息: {text}")
                    return None
    
    async def monitor_progress(self, token, video_id, max_wait=30):
        """监控下载进度"""
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            start_time = time.time()
            last_progress = -1
            
            print(f"\n📊 开始监控视频 {video_id} 的下载进度...")
            
            while time.time() - start_time < max_wait:
                try:
                    async with session.get(
                        f"{self.base_url}/api/v1/videos/{video_id}/progress",
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            progress = await response.json()
                            
                            current_progress = progress.get('download_progress', 0)
                            message = progress.get('processing_message', '无消息')
                            status = progress.get('status', 'unknown')
                            
                            # 只在进度变化时打印
                            if current_progress != last_progress:
                                last_progress = current_progress
                                print(f"   ⏳ 进度: {current_progress:.1f}% - {message}")
                            
                            # 检查是否完成
                            if status == "completed" or current_progress >= 100:
                                print(f"   ✅ 下载完成!")
                                return True
                            
                            # 检查是否失败
                            if status == "failed":
                                print(f"   ❌ 下载失败: {progress.get('processing_error', '未知错误')}")
                                return False
                        
                        await asyncio.sleep(2)  # 每2秒检查一次
                        
                except Exception as e:
                    print(f"监控进度时出错: {e}")
                    await asyncio.sleep(2)
            
            print(f"   ⏰ 监控超时 ({max_wait}秒)")
            return False
    
    async def run_complete_test(self):
        """运行完整测试"""
        print("🎯 开始完整进度跟踪测试")
        print("=" * 60)
        
        # 1. 登录获取token
        print("1. 登录获取token...")
        token = await self.login_and_get_token()
        if not token:
            print("❌ 登录失败，跳过测试")
            return
        print("   ✅ 登录成功")
        
        # 2. 创建测试项目
        print("\n2. 创建测试项目...")
        project_id = await self.create_test_project(token)
        if not project_id:
            print("❌ 创建项目失败")
            return
        self.test_project_id = project_id
        print(f"   ✅ 项目创建成功，ID: {project_id}")
        
        # 3. 开始视频下载
        print("\n3. 开始视频下载...")
        video_id = await self.start_video_download(token, project_id)
        if not video_id:
            print("❌ 开始下载失败")
            return
        self.test_video_id = video_id
        print(f"   ✅ 下载任务已启动，视频ID: {video_id}")
        
        # 4. 监控进度
        print("\n4. 监控下载进度...")
        success = await self.monitor_progress(token, video_id)
        
        if success:
            print("\n🎉 测试完成！进度跟踪功能正常")
        else:
            print("\n⚠️  测试完成，但下载可能遇到问题")
        
        # 5. 获取最终状态
        print("\n5. 获取最终状态...")
        await self.get_final_status(token, video_id)
    
    async def get_final_status(self, token, video_id):
        """获取最终状态"""
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/v1/videos/{video_id}/progress",
                headers=headers
            ) as response:
                if response.status == 200:
                    final_status = await response.json()
                    print("\n📋 最终状态:")
                    print(f"   视频ID: {final_status['video_id']}")
                    print(f"   标题: {final_status['title']}")
                    print(f"   状态: {final_status['status']}")
                    print(f"   下载进度: {final_status['download_progress']:.1f}%")
                    print(f"   文件大小: {final_status['file_size']:,} bytes")
                    print(f"   处理消息: {final_status['processing_message']}")
                    
                    if final_status['processing_tasks']:
                        print("\n   相关任务:")
                        for task in final_status['processing_tasks'][:2]:  # 显示前2个任务
                            print(f"     - {task['task_type']}: {task['status']} ({task['progress']:.1f}%)")

async def main():
    """主函数"""
    tester = CompleteProgressTest()
    
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
    
    await tester.run_complete_test()

if __name__ == "__main__":
    asyncio.run(main())