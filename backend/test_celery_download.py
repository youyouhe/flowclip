#!/usr/bin/env python3
"""
测试Celery视频下载功能
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/home/cat/github/slice-youtube/backend')

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.video import Video
from sqlalchemy import select
from app.tasks.video_tasks import download_video
from app.core.celery import celery_app

async def test_celery_video_download():
    """测试Celery视频下载功能"""
    print("开始测试Celery视频下载功能...")
    
    # 获取数据库会话
    async with AsyncSessionLocal() as db:
        try:
            # 获取测试用户
            stmt = select(User).where(User.email == "admin@example.com")
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                print("未找到测试用户，请先创建用户")
                return
            
            print(f"找到测试用户: {user.username} (ID: {user.id})")
            
            # 获取或创建测试项目
            stmt = select(Project).where(Project.name == "Celery测试项目")
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            
            if not project:
                project = Project(
                    name="Celery测试项目",
                    description="用于测试Celery视频下载功能的项目",
                    user_id=user.id
                )
                db.add(project)
                await db.commit()
                await db.refresh(project)
                print(f"创建测试项目: {project.name} (ID: {project.id})")
            else:
                print(f"找到测试项目: {project.name} (ID: {project.id})")
            
            # 测试视频URL
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # 一个简短的测试视频
            
            print(f"准备启动Celery下载任务...")
            print(f"视频URL: {test_url}")
            print(f"项目ID: {project.id}")
            print(f"用户ID: {user.id}")
            
            # 启动Celery任务
            task = celery_app.send_task(
                'app.tasks.video_tasks.download_video',
                args=[test_url, project.id, user.id, 'best', None]
            )
            
            print(f"Celery任务已启动")
            print(f"任务ID: {task.id}")
            print(f"任务状态: {task.status}")
            
            # 等待几秒钟检查任务状态
            print("\n等待5秒后检查任务状态...")
            await asyncio.sleep(5)
            
            task_result = task.result
            print(f"任务结果: {task_result}")
            
            # 检查数据库中是否创建了视频记录
            stmt = select(Video).where(
                Video.url == test_url,
                Video.project_id == project.id
            )
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if video:
                print(f"\n数据库中已创建视频记录:")
                print(f"  视频ID: {video.id}")
                print(f"  标题: {video.title}")
                print(f"  状态: {video.status}")
                print(f"  下载进度: {video.download_progress}%")
            else:
                print("\n警告: 数据库中未找到视频记录")
            
            print("\n测试完成！")
            
        except Exception as e:
            print(f"测试失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_celery_video_download())