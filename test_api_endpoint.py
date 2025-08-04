#!/usr/bin/env python3
"""
简单的API端点测试脚本
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
from app.api.v1.status import get_running_video_ids
from app.models.user import User

async def test_api_endpoint():
    """测试API端点"""
    print("🧪 测试获取运行中视频IDs的API端点")
    print("=" * 50)
    
    try:
        async with AsyncSessionLocal() as db:
            # 使用用户ID 1进行测试
            # 创建一个模拟用户对象
            user = User()
            user.id = 1
            
            # 直接调用API函数
            running_video_ids = await get_running_video_ids(current_user=user, db=db)
            
            print(f"📋 运行中的视频IDs: {running_video_ids}")
            print(f"📋 视频数量: {len(running_video_ids)}")
            
            if len(running_video_ids) == 0:
                print("ℹ️  没有找到运行中的视频")
                
                # 检查数据库中的处理任务
                from app.models.processing_task import ProcessingTask
                from app.models.video import Video
                from app.models.project import Project
                from sqlalchemy import select
                
                # 查询所有处理任务
                stmt = select(ProcessingTask).where(
                    ProcessingTask.status.in_(['pending', 'running'])
                )
                result = await db.execute(stmt)
                tasks = result.scalars().all()
                
                print(f"📋 处理中的任务数量: {len(tasks)}")
                for task in tasks:
                    print(f"   - 任务ID: {task.id}, 视频ID: {task.video_id}, 状态: {task.status}")
                
                # 查询用户1的所有视频
                stmt = select(Video).join(Project).where(
                    Project.user_id == 1
                )
                result = await db.execute(stmt)
                videos = result.scalars().all()
                
                print(f"📋 用户1的所有视频: {len(videos)}")
                for video in videos:
                    print(f"   - 视频ID: {video.id}, 状态: {video.status}")
            
            return running_video_ids
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 开始API端点测试...")
    result = asyncio.run(test_api_endpoint())
    print("✅ 测试完成")