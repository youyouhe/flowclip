from celery import shared_task
import os
import uuid
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import desc

from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.core.database import get_sync_db
from app.models import Video, ProcessingTask

# 创建logger
logger = logging.getLogger(__name__)

def extract_video_metadata(file_path: str) -> Tuple[float, int, int, Optional[str]]:
    """提取视频元数据：时长、宽度、高度、格式"""
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise Exception(f"视频文件不存在: {file_path}")
        
        # 使用ffprobe获取视频信息
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format',
            '-show_streams', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        
        # 获取视频信息
        duration = 0.0
        if 'format' in metadata and 'duration' in metadata['format']:
            duration = float(metadata['format']['duration'])
        
        file_size = 0
        if 'format' in metadata and 'size' in metadata['format']:
            file_size = int(metadata['format']['size'])
        
        # 获取视频流信息
        width = 0
        height = 0
        format_name = 'unknown'
        
        if 'streams' in metadata:
            video_streams = [s for s in metadata['streams'] if s.get('codec_type') == 'video']
            if video_streams:
                width = video_streams[0].get('width', 0)
                height = video_streams[0].get('height', 0)
                format_name = video_streams[0].get('codec_name', 'unknown')
        
        logger.info(f"提取视频元数据成功 - 文件: {file_path}, 时长: {duration}秒, 分辨率: {width}x{height}")
        
        return duration, width, height, format_name
        
    except subprocess.CalledProcessError as e:
        logger.error(f"提取视频元数据失败: {e}")
        logger.error(f"ffprobe输出: {e.output}")
        raise Exception(f"Failed to extract video metadata: {e}")
    except Exception as e:
        logger.error(f"提取视频元数据错误: {e}")
        raise Exception(f"Error extracting video metadata: {e}")

def generate_video_thumbnail(file_path: str, video_id: int, project_id: int, user_id: int) -> str:
    """生成视频缩略图并上传到MinIO"""
    try:
        # 检查视频文件是否存在
        if not os.path.exists(file_path):
            raise Exception(f"视频文件不存在: {file_path}")
        
        # 临时缩略图路径
        thumbnail_dir = f"/tmp/thumbnails/{user_id}"
        os.makedirs(thumbnail_dir, exist_ok=True)
        thumbnail_path = os.path.join(thumbnail_dir, f"{video_id}_thumbnail.jpg")
        
        # 使用ffmpeg生成缩略图
        cmd = [
            'ffmpeg', '-i', file_path, '-vframes', '1', '-vf', 'scale=640:360',
            '-y', thumbnail_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ffmpeg生成缩略图失败 - 返回码: {result.returncode}")
            logger.error(f"stderr: {result.stderr}")
            # 如果生成失败，创建一个默认的空白缩略图
            from PIL import Image
            default_image = Image.new('RGB', (640, 360), color='black')
            default_image.save(thumbnail_path, 'JPEG')
            logger.info("已创建默认缩略图")
        
        # 生成MinIO对象名称
        thumbnail_object = f"users/{user_id}/projects/{project_id}/thumbnails/{video_id}.jpg"
        
        # 上传缩略图到MinIO
        try:
            minio_service.upload_file_sync(thumbnail_path, thumbnail_object)
        except Exception as upload_error:
            logger.error(f"上传缩略图到MinIO失败: {upload_error}")
            # 不抛出异常，继续处理
        
        # 清理临时文件
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                logger.warning(f"清理临时缩略图文件失败: {e}")
        
        logger.info(f"缩略图生成成功 - video_id: {video_id}, 对象: {thumbnail_object}")
        return thumbnail_object
        
    except Exception as e:
        logger.error(f"生成缩略图错误: {e}")
        # 返回一个默认的缩略图路径，而不是抛出异常
        default_thumbnail = f"users/{user_id}/projects/{project_id}/thumbnails/{video_id}.jpg"
        logger.info(f"使用默认缩略图路径: {default_thumbnail}")
        return default_thumbnail

def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
    """更新任务状态 - 同步版本"""
    try:
        with get_sync_db() as db:
            state_manager = get_state_manager(db)
            state_manager.update_celery_task_status_sync(
                celery_task_id=celery_task_id,
                celery_status=status,
                meta={
                    'progress': progress,
                    'message': message,
                    'error': error,
                    'stage': ProcessingStage.DOWNLOAD
                }
            )
    except ValueError as e:
        # 如果处理任务记录不存在，只记录日志而不抛出异常
        logger.warning(f"Warning: Processing task not found for status update: {e}")
    except Exception as e:
        logger.error(f"更新任务状态失败: {e}")

@shared_task(
    bind=True, 
    name='app.tasks.video_tasks.upload_video',
    soft_time_limit=60 * 60,  # 60分钟软时间限制（增加一倍）
    time_limit=70 * 60  # 70分钟硬时间限制
)
def upload_video(self, video_id: int, project_id: int, user_id: int, temp_file_path: str) -> Dict[str, Any]:
    """处理上传的视频文件（后台任务）"""
    
    def _update_status(progress: float, message: str = None):
        """更新任务状态"""
        _update_task_status(self.request.id, ProcessingTaskStatus.RUNNING, progress, message)
    
    logger.info(f"开始处理上传视频 - video_id: {video_id}, temp_path: {temp_file_path}")
    
    try:
        # 阶段1: 验证文件 (5%)
        _update_status(5, "验证上传文件")
        if not os.path.exists(temp_file_path):
            raise FileNotFoundError(f"临时文件不存在: {temp_file_path}")
        
        file_size = os.path.getsize(temp_file_path)
        logger.info(f"开始处理上传文件: video_id={video_id}, file_size={file_size}")
        
        with get_sync_db() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"视频记录不存在: {video_id}")
            
            # 阶段2: 更新状态为downloading (10%)
            _update_status(10, "开始上传处理")
            
            video.status = "downloading"
            video.download_progress = 10.0
            db.commit()
            
            # 阶段3: 提取视频元数据 (10-30%)
            _update_status(15, "提取视频信息")
            try:
                duration, width, height, format_name = extract_video_metadata(temp_file_path)
                
                video.duration = duration
                video.file_size = file_size
                video.download_progress = 30.0
                db.commit()
            except Exception as metadata_error:
                logger.warning(f"提取视频元数据失败，继续处理: {metadata_error}")
                video.file_size = file_size
                video.download_progress = 30.0
                db.commit()
                duration = width = height = 0
                format_name = "unknown"
            
            # 阶段4: 生成缩略图 (30-50%)
            _update_status(35, "生成视频缩略图")
            try:
                thumbnail_path = generate_video_thumbnail(temp_file_path, video_id, project_id, user_id)
                video.thumbnail_path = thumbnail_path
                # 生成缩略图的可访问URL
                try:
                    thumbnail_url = minio_service.get_file_url_sync(thumbnail_path)
                    video.thumbnail_url = thumbnail_url
                except Exception as url_error:
                    logger.warning(f"生成缩略图URL失败: {url_error}")
                video.download_progress = 50.0
                db.commit()
            except Exception as thumbnail_error:
                logger.warning(f"生成缩略图失败，继续处理: {thumbnail_error}")
                video.download_progress = 50.0
                db.commit()
            
            # 阶段5: 上传文件到MinIO (50-90%)
            _update_status(60, "上传文件到存储系统")
            
            # 生成MinIO对象名称
            object_name = f"users/{user_id}/projects/{project_id}/videos/{video.filename}"
            
            # 上传文件到MinIO
            try:
                # 重新加载MinIO配置，确保使用最新的访问密钥
                minio_service.reload_config()
                
                minio_service.upload_file_sync(temp_file_path, object_name)
                
                video.file_path = object_name
                video.download_progress = 90.0
                db.commit()
            except Exception as upload_error:
                logger.error(f"上传文件到MinIO失败: {upload_error}")
                raise Exception(f"上传文件到MinIO失败: {upload_error}")
            
            # 阶段6: 完成处理 (90-100%)
            _update_status(95, "上传处理完成")
            
            # 更新最终状态
            video.status = "completed"
            video.download_progress = 100.0
            db.commit()
            
            # 更新处理任务状态为成功
            _update_task_status(self.request.id, ProcessingTaskStatus.SUCCESS, 100, "视频上传完成")
            
            # 清理临时文件
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"清理临时文件: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            logger.info(f"视频上传处理完成 - video_id: {video_id}")
            
            return {
                "success": True,
                "video_id": video_id,
                "duration": duration,
                "file_size": file_size,
                "object_name": object_name,
                "thumbnail_path": thumbnail_path if 'thumbnail_path' in locals() else None,
                "width": width,
                "height": height,
                "format": format_name
            }
            
    except Exception as e:
        logger.error(f"视频上传处理失败: video_id={video_id}, error={str(e)}", exc_info=True)
        
        # 更新失败状态
        try:
            with get_sync_db() as db:
                video = db.query(Video).filter(Video.id == video_id).first()
                if video:
                    video.status = "failed"
                    video.download_progress = 0.0
                    video.processing_error = str(e)
                    db.commit()
                    logger.info(f"更新失败状态: video_id={video_id}")
        except Exception as db_error:
            logger.error(f"更新失败状态失败: {db_error}")
        
        # 清理临时文件
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"清理临时文件: {temp_file_path}")
            except Exception as cleanup_error:
                logger.error(f"清理临时文件失败: {cleanup_error}")
        
        # 更新任务状态为失败
        _update_task_status(self.request.id, ProcessingTaskStatus.FAILURE, 0, error=str(e))
        # 不抛出异常，而是返回错误信息
        return {
            "success": False,
            "video_id": video_id,
            "error": str(e)
        }