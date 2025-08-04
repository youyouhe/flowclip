#!/usr/bin/env python3
"""
检查数据库中的测试视频
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/home/cat/github/slice-youtube/backend')

from app.core.database import AsyncSessionLocal
from app.models.video import Video
from app.models.project import Project
from sqlalchemy import select

async def check_test_video():
    """检查测试视频"""
    print("检查数据库中的测试视频...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查所有视频
            stmt = select(Video)
            result = await db.execute(stmt)
            videos = result.scalars().all()
            
            print(f"数据库中共有 {len(videos)} 个视频:")
            for video in videos:
                print(f"  - ID: {video.id}, 标题: {video.title}, 状态: {video.status}, 进度: {video.download_progress}%")
            
            # 检查活跃状态的视频
            active_statuses = ["pending", "downloading", "processing"]
            stmt = select(Video).where(Video.status.in_(active_statuses))
            result = await db.execute(stmt)
            active_videos = result.scalars().all()
            
            print(f"\n活跃状态的视频 ({len(active_videos)} 个):")
            for video in active_videos:
                print(f"  - ID: {video.id}, 标题: {video.title}, 状态: {video.status}")
            
        except Exception as e:
            print(f"检查失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_test_video())