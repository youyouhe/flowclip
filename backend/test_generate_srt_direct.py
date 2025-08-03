#!/usr/bin/env python3
"""
简化的SRT生成测试，不依赖状态管理
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
from app.models.processing_task import ProcessingTask
from sqlalchemy import select
from app.services.minio_client import minio_service
from app.services.audio_processor import audio_processor
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus

async def test_generate_srt_direct():
    """直接测试SRT生成功能"""
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
        
        # 2. 检查是否有音频文件
        try:
            audio_object_name = f"users/{project.user_id}/projects/{video.project_id}/audio/{video.id}.wav"
            audio_exists = await minio_service.file_exists(audio_object_name)
            if audio_exists:
                print(f"✅ 音频文件存在: {audio_object_name}")
            else:
                print(f"⚠️  音频文件不存在: {audio_object_name}")
                return
        except Exception as e:
            print(f"❌ 检查音频文件失败: {e}")
            return
        
        # 3. 下载音频文件到临时目录
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audio_file = temp_path / f"{video.id}.wav"
            
            print(f"📥 下载音频文件到: {audio_file}")
            
            try:
                # 从MinIO下载音频文件
                audio_data = await minio_service.client.get_object(
                    minio_service.bucket_name,
                    audio_object_name
                )
                
                with open(audio_file, 'wb') as f:
                    f.write(audio_data.read())
                
                print(f"✅ 音频文件下载完成: {audio_file.stat().st_size} bytes")
                
            except Exception as e:
                print(f"❌ 下载音频文件失败: {e}")
                return
            
            # 4. 创建音频目录
            audio_dir = temp_path / "audio_segments"
            audio_dir.mkdir(exist_ok=True)
            
            # 5. 复制音频文件到音频目录
            import shutil
            segment_file = audio_dir / f"{video.id}_001.wav"
            shutil.copy2(audio_file, segment_file)
            
            print(f"✅ 准备音频文件: {segment_file}")
            
            # 6. 测试ASR服务连接
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://192.168.8.107:5000/health", timeout=5) as response:
                        if response.status == 200:
                            print("✅ ASR服务连接正常")
                        else:
                            print(f"⚠️  ASR服务状态异常: {response.status}")
            except Exception as e:
                print(f"⚠️  ASR服务连接失败: {e}")
                print("   将继续测试，但可能会失败")
            
            # 7. 直接调用SRT生成功能
            print("🚀 开始生成SRT...")
            
            try:
                # 直接使用音频处理器生成SRT
                result = await audio_processor.generate_srt_from_audio(
                    audio_dir=str(audio_dir),
                    video_id=str(video.id),
                    project_id=video.project_id,
                    user_id=project.user_id,
                    api_url="http://192.168.8.107:5000/asr",
                    lang="zh",
                    max_workers=1
                )
                
                print(f"✅ SRT生成完成!")
                print(f"   结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                # 8. 验证生成的SRT文件
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
                
            except Exception as e:
                print(f"❌ SRT生成失败: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_generate_srt_direct())