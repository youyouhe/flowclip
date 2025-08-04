#!/usr/bin/env python3
"""
测试数据库连接和配置的脚本
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = '/home/cat/github/slice-youtube/backend/.env'
load_dotenv(env_path)

sys.path.append('/home/cat/github/slice-youtube/backend')

from app.core.config import settings
from app.core.database import AsyncSessionLocal, async_engine
from sqlalchemy import text, select
from app.models.video import Video
from app.models.project import Project

async def test_database_config():
    """测试数据库配置和连接"""
    print("🔧 数据库配置测试")
    print("=" * 50)
    
    # 1. 检查配置
    print(f"📋 Database URL: {settings.database_url}")
    print(f"📋 是否使用MySQL: {'mysql' in settings.database_url.lower()}")
    
    # 2. 测试数据库连接
    try:
        async with AsyncSessionLocal() as db:
            print("✅ 数据库连接成功")
            
            # 3. 查询项目
            result = await db.execute(select(Project))
            projects = result.scalars().all()
            print(f"📋 项目总数: {len(projects)}")
            
            for project in projects:
                print(f"   - 项目ID: {project.id}, 用户ID: {project.user_id}, 名称: {project.name}")
            
            # 4. 查询视频
            result = await db.execute(select(Video))
            videos = result.scalars().all()
            print(f"📋 视频总数: {len(videos)}")
            
            for video in videos:
                print(f"   - 视频ID: {video.id}, 项目ID: {video.project_id}, 状态: {video.status}, 标题: {video.title[:50]}...")
            
            # 5. 查询用户1的视频
            result = await db.execute(
                select(Video).join(Project).where(
                    Project.user_id == 1,
                    Video.status.in_(['pending', 'downloading', 'processing', 'completed'])
                )
            )
            user_videos = result.scalars().all()
            print(f"📋 用户1的活跃视频: {len(user_videos)}")
            
            for video in user_videos:
                print(f"   - 视频ID: {video.id}, 状态: {video.status}")
                
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    import asyncio
    
    print("🚀 开始数据库配置测试...")
    asyncio.run(test_database_config())
    print("✅ 测试完成")