#!/usr/bin/env python3
"""
测试获取所有活跃视频（包括已完成）的API端点
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = '/home/cat/github/slice-youtube/backend/.env'
load_dotenv(env_path)

sys.path.append('/home/cat/github/slice-youtube/backend')

import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask

async def get_all_active_video_ids(current_user: User, db):
    """获取所有活跃视频IDs（包括已完成）"""
    # 获取用户的所有项目中的视频
    stmt = select(Video.id).join(Project).where(
        Project.user_id == current_user.id,
        Video.status.in_(['pending', 'downloading', 'processing', 'completed'])
    ).distinct()
    
    result = await db.execute(stmt)
    active_video_ids = [row[0] for row in result.fetchall()]
    
    return active_video_ids

async def test_all_active_videos():
    """测试获取所有活跃视频"""
    print("🧪 测试获取所有活跃视频IDs")
    print("=" * 50)
    
    try:
        async with AsyncSessionLocal() as db:
            user = User()
            user.id = 1
            
            # 获取所有活跃视频
            active_video_ids = await get_all_active_video_ids(current_user=user, db=db)
            
            print(f"📋 所有活跃视频IDs: {active_video_ids}")
            print(f"📋 视频数量: {len(active_video_ids)}")
            
            # 详细信息
            for video_id in active_video_ids:
                stmt = select(Video).where(Video.id == video_id)
                result = await db.execute(stmt)
                video = result.scalar_one_or_none()
                
                if video:
                    print(f"   - 视频ID: {video.id}, 状态: {video.status}, 标题: {video.title[:50]}...")
                    
                    # 检查处理任务
                    stmt = select(ProcessingTask).where(ProcessingTask.video_id == video_id)
                    result = await db.execute(stmt)
                    tasks = result.scalars().all()
                    
                    print(f"     处理任务: {len(tasks)} 个")
                    for task in tasks:
                        print(f"       - 任务: {task.task_type}, 状态: {task.status}")
            
            return active_video_ids
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 开始测试所有活跃视频...")
    result = asyncio.run(test_all_active_videos())
    print("✅ 测试完成")