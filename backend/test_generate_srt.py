#!/usr/bin/env python3
"""
测试生成字幕功能的完整流程
"""
import asyncio
import sys
import os
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from app.core.database import AsyncSessionLocal
from app.models.video import Video
from app.models.project import Project
from app.models.user import User
from sqlalchemy import select
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.tasks.video_tasks import generate_srt

async def test_generate_srt():
    """测试生成字幕功能"""
    print("🎯 开始测试生成字幕功能...")
    
    async with AsyncSessionLocal() as db:
        # 1. 获取一个可用的视频
        print("📹 获取测试视频...")
        stmt = select(Video).join(Project).join(User).where(
            Video.status == "completed",
            Video.file_path.isnot(None)
        ).limit(1)
        
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            print("❌ 没有找到可用的测试视频")
            return
        
        print(f"✅ 找到测试视频: {video.title} (ID: {video.id})")
        print(f"   文件路径: {video.file_path}")
        
        # 获取项目信息
        project_result = await db.execute(select(Project).where(Project.id == video.project_id))
        project = project_result.scalar_one()
        
        # 2. 检查是否有分割文件
        split_files = []
        if video.processing_metadata and video.processing_metadata.get('split_files'):
            split_files = video.processing_metadata.get('split_files', [])
            print(f"✅ 找到分割文件: {len(split_files)} 个")
        else:
            print("⚠️  没有找到分割文件，将使用空列表")
        
        # 3. 检查音频文件
        try:
            audio_object_name = f"users/{project.user_id}/projects/{video.project_id}/audio/{video.id}.wav"
            audio_exists = await minio_service.file_exists(audio_object_name)
            if audio_exists:
                print(f"✅ 音频文件存在: {audio_object_name}")
            else:
                print(f"⚠️  音频文件不存在: {audio_object_name}")
        except Exception as e:
            print(f"❌ 检查音频文件失败: {e}")
        
        # 4. 测试生成SRT任务
        print("\n🚀 启动生成SRT任务...")
        try:
            task = generate_srt.delay(
                video_id=str(video.id),
                project_id=video.project_id,
                user_id=project.user_id,
                split_files=split_files
            )
            
            print(f"✅ 任务已启动: {task.id}")
            print(f"   任务状态: {task.status}")
            
            # 5. 等待任务完成（最多等待30秒）
            print("\n⏳ 等待任务完成...")
            import time
            start_time = time.time()
            
            while time.time() - start_time < 30:
                from celery.result import AsyncResult
                current_task = AsyncResult(task.id)
                print(f"   任务状态: {current_task.status}")
                
                if current_task.ready():
                    if current_task.successful():
                        result = current_task.get()
                        print(f"✅ 任务完成!")
                        print(f"   结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
                        
                        # 6. 验证生成的SRT文件
                        if result.get('success'):
                            srt_object_name = result.get('object_name')
                            if srt_object_name:
                                srt_exists = await minio_service.file_exists(srt_object_name)
                                if srt_exists:
                                    print(f"✅ SRT文件已生成: {srt_object_name}")
                                    
                                    # 获取下载URL
                                    url = await minio_service.get_file_url(srt_object_name, 3600)
                                    print(f"✅ SRT下载URL: {url}")
                                else:
                                    print(f"❌ SRT文件未找到: {srt_object_name}")
                        break
                    else:
                        error = current_task.result
                        print(f"❌ 任务失败: {error}")
                        break
                
                time.sleep(2)
            
            if not task.ready():
                print("⚠️  任务未在30秒内完成，可能需要更长时间")
            
        except Exception as e:
            print(f"❌ 启动任务失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_generate_srt())