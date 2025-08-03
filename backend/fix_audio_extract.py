#!/usr/bin/env python3
"""
直接音频提取脚本，不依赖Celery任务队列
用于修复Web界面上"提取音频"功能失败的问题

使用方法:
python fix_audio_extract.py <video_id>
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

async def extract_audio_from_video_id(video_id: int):
    """直接提取视频的音频，绕过Celery任务队列"""
    try:
        from app.services.audio_processor import audio_processor
        from app.services.minio_client import minio_service
        from app.models.video import Video
        from app.models.project import Project
        from app.core.config import settings
        
        # 确保MinIO存储桶存在
        bucket_ok = await minio_service.ensure_bucket_exists()
        logger.info(f"MinIO存储桶状态: {bucket_ok}")
        
        # 创建数据库会话
        engine = create_async_engine(settings.database_url)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # 获取视频记录
        async with async_session() as db:
            stmt = select(Video).join(Project).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                logger.error(f"找不到ID为 {video_id} 的视频")
                return
            
            if not video.file_path:
                logger.error(f"视频 {video_id} 没有关联的视频文件")
                return
            
            # 从minio_path中提取对象名称
            object_name = video.file_path
            if object_name.startswith(f"{settings.minio_bucket_name}/"):
                object_name = object_name[len(f"{settings.minio_bucket_name}/"):]
            
            # 获取临时访问URL
            video_url = await minio_service.get_file_url(object_name, expiry=3600)
            
            if not video_url:
                logger.error(f"无法获取视频文件URL")
                return
            
            # 创建临时文件
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                video_path = temp_path / f"{video.id}.mp4"
                
                # 下载视频文件
                import requests
                logger.info(f"下载视频文件到临时路径: {video_path}")
                response = requests.get(video_url, stream=True)
                response.raise_for_status()
                
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # 提取音频
                logger.info(f"开始提取音频...")
                result = await audio_processor.extract_audio_from_video(
                    video_path=str(video_path),
                    video_id=str(video.id),
                    project_id=video.project_id,
                    user_id=video.project.user_id
                )
                
                if result.get('success'):
                    logger.info("✅ 音频提取成功!")
                    logger.info(f"音频文件: {result['audio_filename']}")
                    logger.info(f"MinIO路径: {result['minio_path']}")
                    logger.info(f"对象名称: {result['object_name']}")
                    logger.info(f"文件大小: {result['file_size']} 字节")
                    logger.info(f"音频时长: {result['duration']} 秒")
                    
                    # 更新视频记录
                    video.audio_status = "completed"
                    video.audio_path = result['minio_path']
                    await db.commit()
                    logger.info("视频记录已更新")
                    
                    # 生成下载URL
                    url = await minio_service.get_file_url(result['object_name'], expiry=3600)
                    if url:
                        logger.info(f"音频下载URL (有效期1小时): {url}")
                else:
                    logger.error("❌ 音频提取失败")
                    
    except Exception as e:
        logger.error(f"处理过程中出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python fix_audio_extract.py <video_id>")
        sys.exit(1)
    
    try:
        video_id = int(sys.argv[1])
    except ValueError:
        print("视频ID必须是数字")
        sys.exit(1)
    
    asyncio.run(extract_audio_from_video_id(video_id))