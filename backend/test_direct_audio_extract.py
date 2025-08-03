import asyncio
import sys
import os
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

async def test_direct_audio_extraction():
    """直接测试音频提取功能，绕过Celery任务队列"""
    try:
        from app.services.audio_processor import audio_processor
        from app.services.minio_client import minio_service
        
        # 确保MinIO存储桶存在
        bucket_ok = await minio_service.ensure_bucket_exists()
        logger.info(f"MinIO存储桶状态: {bucket_ok}")
        
        # 测试视频文件路径 - 这里使用项目根目录下的测试视频文件
        video_file = "MMtXQ5C6RL4.mp4"  # 假设这个文件在项目根目录
        video_path = str(Path(video_file).absolute())
        
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            video_files = list(Path('.').glob('*.mp4'))
            if video_files:
                video_path = str(video_files[0].absolute())
                logger.info(f"尝试使用替代视频文件: {video_path}")
            else:
                logger.error("找不到任何MP4视频文件")
                return
        
        logger.info(f"开始从视频提取音频: {video_path}")
        
        # 直接调用音频提取功能
        result = await audio_processor.extract_audio_from_video(
            video_path=video_path,
            video_id="test_direct",
            project_id=1,
            user_id=1,
            audio_format="wav"
        )
        
        logger.info(f"音频提取结果: {result}")
        
        if result.get('success'):
            logger.info("✅ 音频提取成功!")
            logger.info(f"音频文件: {result['audio_filename']}")
            logger.info(f"MinIO路径: {result['minio_path']}")
            logger.info(f"对象名称: {result['object_name']}")
            logger.info(f"文件大小: {result['file_size']} 字节")
            logger.info(f"音频时长: {result['duration']} 秒")
            logger.info(f"采样率: {result['sample_rate']} Hz")
            logger.info(f"声道数: {result['channels']}")
            
            # 生成预签名下载URL
            url = await minio_service.get_file_url(result['object_name'], expiry=3600)
            if url:
                logger.info(f"下载URL (有效期1小时): {url}")
        else:
            logger.error("❌ 音频提取失败")
        
    except Exception as e:
        logger.error(f"测试过程中出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_direct_audio_extraction())