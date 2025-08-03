#!/usr/bin/env python3
"""
测试SRT生成功能的简化版本
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
from app.services.audio_processor import audio_processor
from app.tasks.video_tasks import generate_srt

async def test_srt_generation():
    """测试SRT生成功能"""
    print("🎯 开始测试SRT生成功能...")
    
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
        
        # 2. 检查音频文件
        audio_object_name = f"users/{project.user_id}/projects/{video.project_id}/audio/{video.id}.wav"
        try:
            audio_exists = await minio_service.file_exists(audio_object_name)
            if audio_exists:
                print(f"✅ 音频文件存在: {audio_object_name}")
            else:
                print(f"❌ 音频文件不存在: {audio_object_name}")
                return
        except Exception as e:
            print(f"❌ 检查音频文件失败: {e}")
            return
        
        # 3. 直接调用SRT生成任务（不通过Celery）
        print("🚀 开始生成SRT...")
        
        try:
            # 直接运行SRT生成逻辑
            result = await audio_processor.generate_srt_from_audio(
                audio_dir=f"/tmp/audio_{video.id}",  # 临时目录
                video_id=str(video.id),
                project_id=video.project_id,
                user_id=project.user_id,
                api_url="http://192.168.8.107:5000/asr",
                lang="zh",
                max_workers=1
            )
            
            print(f"✅ SRT生成完成!")
            print(f"   结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
        except Exception as e:
            print(f"❌ SRT生成失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_srt_generation())