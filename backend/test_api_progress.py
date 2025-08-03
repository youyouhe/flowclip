#!/usr/bin/env python3
"""
测试API进度查询
"""

import asyncio
import aiohttp
import json
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_progress_api():
    """测试进度查询API"""
    
    base_url = "http://localhost:8001"
    
    async with aiohttp.ClientSession() as session:
        try:
            # 测试获取视频列表
            print("📋 获取视频列表...")
            async with session.get(f"{base_url}/api/v1/videos") as response:
                if response.status == 200:
                    videos = await response.json()
                    print(f"   找到 {len(videos)} 个视频")
                    
                    if videos:
                        # 测试获取单个视频进度
                        video = videos[0]
                        video_id = video['id']
                        user_id = 1  # 假设用户ID
                        
                        print(f"\n📊 获取视频 {video_id} 的进度...")
                        async with session.get(f"{base_url}/api/v1/videos/{video_id}/progress") as progress_response:
                            if progress_response.status == 200:
                                progress_data = await progress_response.json()
                                print(f"   当前进度: {progress_data}")
                            else:
                                print(f"   获取进度失败: {progress_response.status}")
                else:
                    print(f"   获取视频列表失败: {response.status}")
                    
        except Exception as e:
            print(f"❌ API测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_progress_api())