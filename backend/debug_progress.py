#!/usr/bin/env python3
"""
调试进度显示问题
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def debug_progress_display():
    """调试进度显示"""
    
    base_url = "http://localhost:8001"
    
    # 使用硬编码的token进行测试
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwiZXhwIjoxNzMzNjI4ODk5fQ.example"  # 替换为有效token
    
    async with aiohttp.ClientSession() as session:
        try:
            # 获取视频列表
            headers = {"Authorization": f"Bearer {token}"}
            async with session.get(f"{base_url}/api/v1/videos", headers=headers) as response:
                if response.status == 200:
                    videos = await response.json()
                    if videos:
                        video = videos[0]  # 使用第一个视频
                        video_id = video['id']
                        
                        print(f"🔍 调试视频ID: {video_id}")
                        print(f"标题: {video['title']}")
                        print(f"当前状态: {video['status']}")
                        print(f"下载进度: {video['download_progress']}%")
                        
                        # 获取详细进度
                        async with session.get(f"{base_url}/api/v1/videos/{video_id}/progress", headers=headers) as progress_response:
                            if progress_response.status == 200:
                                detail = await progress_response.json()
                                print(f"\n📊 详细进度信息:")
                                print(json.dumps(detail, indent=2, ensure_ascii=False))
                                
                                # 检查数据库实际值
                                print(f"\n📋 关键信息:")
                                print(f"   视频ID: {detail['video_id']}")
                                print(f"   状态: {detail['status']}")
                                print(f"   下载进度: {detail['download_progress']}%")
                                print(f"   处理阶段: {detail['processing_stage']}")
                                print(f"   处理消息: {detail['processing_message']}")
                                
                                if detail['processing_tasks']:
                                    print(f"   处理任务:")
                                    for task in detail['processing_tasks']:
                                        print(f"     - {task['task_type']}: {task['status']} ({task['progress']:.1f}%)")
                            else:
                                print(f"获取详细进度失败: {progress_response.status}")
                    else:
                        print("❌ 没有找到视频")
                else:
                    print(f"获取视频列表失败: {response.status}")
                    
        except Exception as e:
            print(f"❌ 调试失败: {e}")

if __name__ == "__main__":
    asyncio.run(debug_progress_display())