#!/usr/bin/env python3
"""
检查数据库中的视频
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.video import Video
from app.models.project import Project
from app.models.user import User

async def check_videos():
    """检查数据库中的视频"""
    async with AsyncSessionLocal() as db:
        # 查询所有视频
        stmt = select(Video, Project, User).join(Project, Video.project_id == Project.id).join(User, Project.user_id == User.id)
        result = await db.execute(stmt)
        videos = result.fetchall()
        
        print(f"数据库中的视频数量: {len(videos)}")
        
        for video, project, user in videos:
            print(f"视频ID: {video.id}")
            print(f"标题: {video.title}")
            print(f"状态: {video.status}")
            print(f"项目: {project.name} (ID: {project.id})")
            print(f"用户: {user.username} (ID: {user.id})")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_videos())