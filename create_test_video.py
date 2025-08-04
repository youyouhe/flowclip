#!/usr/bin/env python3
"""
创建测试视频记录用于测试WebSocket状态查询
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

async def create_test_video():
    """创建测试视频记录"""
    print("开始创建测试视频记录...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查项目是否存在
            stmt = select(Project).where(Project.id == 3)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            
            if not project:
                print("项目不存在，先创建项目")
                return
            
            # 创建测试视频记录
            test_video = Video(
                title="WebSocket测试视频",
                url="https://www.youtube.com/watch?v=test123",
                project_id=3,
                user_id=2,
                status="downloading",
                download_progress=25,
                processing_progress=0,
                processing_stage="download",
                processing_message="正在下载视频...",
                duration=300,
                file_size=1024000
            )
            
            db.add(test_video)
            await db.commit()
            await db.refresh(test_video)
            
            print(f"测试视频创建成功: {test_video.title} (ID: {test_video.id})")
            print(f"状态: {test_video.status}")
            print(f"下载进度: {test_video.download_progress}%")
            
        except Exception as e:
            print(f"创建测试视频失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_test_video())