#!/usr/bin/env python3
"""
修复数据库中重复的youtube-videos/路径问题
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from app.core.database import get_db
from app.models.video import Video
from app.core.config import settings

async def fix_video_paths():
    """修复视频文件路径"""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as session:
        # 查询所有有重复路径的视频
        stmt = select(Video).where(Video.file_path.like('youtube-videos/%'))
        result = await session.execute(stmt)
        videos = result.scalars().all()
        
        print(f"找到 {len(videos)} 个需要修复的视频")
        
        for video in videos:
            old_path = video.file_path
            new_path = old_path.replace('youtube-videos/', '', 1)  # 只替换第一个匹配
            
            print(f"修复视频 {video.id}: {old_path} -> {new_path}")
            
            # 更新路径
            await session.execute(
                update(Video)
                .where(Video.id == video.id)
                .values(file_path=new_path)
            )
        
        await session.commit()
        print("修复完成")

if __name__ == "__main__":
    asyncio.run(fix_video_paths())