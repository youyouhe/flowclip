from celery import shared_task
import asyncio
import tempfile
import os
import requests
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from sqlalchemy import desc
from app.services.youtube_downloader_minio import downloader_minio
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage, MAX_VIDEO_DURATION_SECONDS
from app.core.database import get_sync_db
from app.models import Video, ProcessingTask

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    name='app.tasks.video_tasks.download_video',
    soft_time_limit=60 * 60,  # 60分钟软时间限制
    time_limit=70 * 60  # 70分钟硬时间限制
)
def download_video(self, video_url: str, project_id: int, user_id: int, quality: str = 'best', cookies_path: str = None, video_id: int = None) -> Dict[str, Any]:
    """Download video from YouTube using yt-dlp"""
    
    def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
        """更新任务状态 - 同步版本"""
        try:
            # 明确使用全局导入的函数，避免作用域冲突
            from app.core.database import get_sync_db as _get_sync_db
            from app.services.state_manager import get_state_manager as _get_state_manager

            with _get_sync_db() as db:
                state_manager = _get_state_manager(db)
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
            print(f"Warning: Processing task not found for status update: {e}")
        except Exception as e:
            print(f"Error updating task status: {e}")
    
    try:
        # 获取有效的任务ID
        celery_task_id = self.request.id if self.request and hasattr(self.request, 'id') and self.request.id else f"download_{int(time.time())}"

        # 确保 task_id 不为空
        if not celery_task_id or celery_task_id == "unknown":
            celery_task_id = f"download_{int(time.time())}"

        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 5, "开始下载视频")
        self.update_state(state='PROGRESS', meta={'progress': 5, 'stage': ProcessingStage.DOWNLOAD, 'message': '开始下载视频'})
        
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 20, "正在获取视频信息")
        self.update_state(state='PROGRESS', meta={'progress': 20, 'stage': ProcessingStage.DOWNLOAD, 'message': '正在获取视频信息'})

        # 获取视频信息并验证时长限制
        try:
            import asyncio
            video_info = asyncio.run(
                downloader_minio.get_video_info(video_url, cookies_path)
            )

            # 检查视频时长限制
            duration_seconds = video_info.get('duration')
            if duration_seconds and duration_seconds > MAX_VIDEO_DURATION_SECONDS:
                duration_minutes = duration_seconds / 60
                error_msg = f"视频时长超过系统限制。当前视频时长: {duration_minutes:.1f}分钟，系统最大允许: {MAX_VIDEO_DURATION_SECONDS // 60}分钟。"
                print(error_msg)

                # 更新视频记录为失败状态
                try:
                    with get_sync_db() as db:
                        if video_id:
                            video = db.query(Video).filter(Video.id == video_id).first()
                            if video:
                                video.status = "failed"
                                video.download_progress = 0.0
                                video.processing_message = error_msg
                                db.commit()
                                print(f"已更新视频记录为失败状态: video_id={video.id}")
                except Exception as db_error:
                    print(f"更新视频失败状态失败: {db_error}")

                _update_task_status(celery_task_id, ProcessingTaskStatus.FAILURE, 0, error_msg)
                raise Exception(error_msg)

            print(f"视频时长验证通过: {duration_seconds}秒 ({duration_seconds/60:.1f}分钟)")

        except Exception as e:
            if "视频时长超过系统限制" in str(e):
                # 重新抛出时长限制异常
                raise e
            print(f"获取视频信息失败，继续执行下载: {e}")

        # 确保有视频ID
        if video_id is None:
            # 如果没有传入video_id，尝试通过处理任务记录查找
            try:
                with get_sync_db() as db:
                    processing_task = db.query(ProcessingTask).filter(
                        ProcessingTask.celery_task_id == celery_task_id
                    ).first()
                    
                    if processing_task and processing_task.video_id:
                        video_id = processing_task.video_id
                        print(f"通过处理任务找到视频ID: {video_id}")
                    else:
                        # 最后回退到通过URL查找
                        video = db.query(Video).filter(
                            Video.url == video_url,
                            Video.project_id == project_id
                        ).order_by(desc(Video.created_at)).first()
                        
                        if video:
                            video_id = video.id
                            print(f"通过URL查找找到视频ID: {video_id}")
            except Exception as e:
                print(f"获取视频ID失败: {e}")
        
        print(f"使用视频ID: {video_id}")
        
        # 定义进度回调函数 - 同步版本
        def progress_callback(progress: float, message: str):
            """下载进度回调函数 - 同步版本"""
            try:
                # 计算整体进度 (20% + 80% * download_progress)
                overall_progress = 20 + (progress * 0.8)

                # 确保 celery_task_id 不为空才更新状态
                if celery_task_id and celery_task_id != "unknown":
                    try:
                        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, overall_progress, message)
                        self.update_state(state='PROGRESS', meta={'progress': overall_progress, 'stage': ProcessingStage.DOWNLOAD, 'message': message})
                    except Exception as status_error:
                        print(f"Warning: Failed to update task status: {status_error}")

                # 更新视频记录的下载进度
                try:
                    from app.core.database import get_sync_db as _get_sync_db
                    with _get_sync_db() as db:
                        if video_id:
                            video = db.query(Video).filter(Video.id == video_id).first()
                            if video:
                                video.download_progress = overall_progress
                                video.status = "downloading"
                                video.processing_progress = overall_progress
                                video.processing_message = message
                                db.commit()
                                print(f"已更新视频 {video_id} 进度: {overall_progress}%")

                            # 只更新数据库，不发送WebSocket通知
                            # 前端会通过定时查询获取最新状态

                except Exception as e:
                    print(f"更新视频进度失败: {e}")

            except Exception as e:
                print(f"Progress callback error: {e}")
        
        # 在执行下载前重新加载MinIO配置，确保使用最新的访问密钥
        try:
            from app.services.system_config_service import SystemConfigService
            from app.core.database import get_sync_db
            from app.services.minio_client import minio_service
            
            # 重新加载系统配置
            db = get_sync_db()
            SystemConfigService.update_settings_from_db_sync(db)
            db.close()
            
            # 重新加载MinIO客户端配置
            minio_service.reload_config()
            
            print("已重新加载MinIO配置")
        except Exception as config_error:
            print(f"重新加载MinIO配置失败: {config_error}")
        
        # 运行异步下载器
        import asyncio
        result = asyncio.run(
            downloader_minio.download_and_upload_video(
                url=video_url,
                project_id=project_id,
                user_id=user_id,
                video_id=video_id,
                quality=quality,
                cookies_file=cookies_path,
                progress_callback=progress_callback
            )
        )
        
        if result.get('success'):
            # 更新视频记录
            try:
                with get_sync_db() as db:
                    if video_id:
                        video = db.query(Video).filter(Video.id == video_id).first()
                        if video:
                            video.status = "completed"
                            video.download_progress = 100.0
                            video.file_path = result['minio_path']
                            video.filename = result['filename']
                            video.file_size = result['filesize']
                            
                            # 保存缩略图路径而不是完整URL
                            thumbnail_url = result.get('thumbnail_url')
                            if thumbnail_url:
                                # 从完整URL中提取对象路径
                                from urllib.parse import urlparse, parse_qs
                                parsed_url = urlparse(thumbnail_url)
                                # 路径格式: /bucket_name/object_path
                                # 我们需要的是object_path部分
                                path_parts = parsed_url.path.lstrip('/').split('/', 1)
                                if len(path_parts) > 1:
                                    thumbnail_path = path_parts[1]  # 获取对象路径部分
                                    video.thumbnail_path = thumbnail_path
                                else:
                                    # 如果无法解析路径，仍然保存完整URL以保持向后兼容
                                    video.thumbnail_url = thumbnail_url
                            db.commit()
                            print(f"已更新视频记录: video_id={video.id}")
                        
                        # 只更新数据库，不发送WebSocket通知
                        # 前端会通过定时查询获取最新状态
            except Exception as e:
                print(f"更新视频记录失败: {e}")
            
            # 更新处理任务的output_data
            try:
                with get_sync_db() as db:
                    state_manager = get_state_manager(db)
                    # 通过celery_task_id找到task_id
                    task = db.query(ProcessingTask).filter(
                        ProcessingTask.celery_task_id == celery_task_id
                    ).first()
                    
                    if task:
                        state_manager.update_task_status_sync(
                            task_id=task.id,
                            status=ProcessingTaskStatus.SUCCESS,
                            progress=100,
                            message="视频下载完成",
                            output_data={
                                'video_id': result.get('video_id'),
                                'title': result['title'],
                                'filename': result['filename'],
                                'minio_path': result['minio_path'],
                                'duration': result['duration'],
                                'file_size': result['filesize'],
                                'thumbnail_url': result['thumbnail_url']
                            },
                            stage=ProcessingStage.DOWNLOAD
                        )
                    else:
                        _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "视频下载完成")
            except Exception as e:
                print(f"状态更新失败: {e}")
                # 回退到原来的状态更新方式
                try:
                    _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "视频下载完成")
                except Exception as fallback_error:
                    print(f"回退状态更新也失败: {fallback_error}")
            
            self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.DOWNLOAD, 'message': '视频下载完成'})
            return {
                'status': 'completed',
                'video_id': result.get('video_id'),
                'title': result['title'],
                'filename': result['filename'],
                'minio_path': result['minio_path'],
                'duration': result['duration'],
                'file_size': result['filesize'],
                'thumbnail_url': result['thumbnail_url']
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            # 更新视频记录为失败状态
            try:
                with get_sync_db() as db:
                    if video_id:
                        video = db.query(Video).filter(Video.id == video_id).first()
                        if video:
                            video.status = "failed"
                            video.download_progress = 0.0
                            db.commit()
                            print(f"已更新视频记录为失败状态: video_id={video.id}")
                        
                        # 只更新数据库，不发送WebSocket通知
                        # 前端会通过定时查询获取最新状态
            except Exception as e:
                print(f"更新视频失败状态失败: {e}")
            
            try:
                _update_task_status(celery_task_id, ProcessingTaskStatus.FAILURE, 0, error_msg)
            except Exception as e:
                print(f"状态更新失败: {e}")
            raise Exception(error_msg)
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        error_details = traceback.format_exc()
        
        print(f"Video download failed - {error_type}: {error_msg}")
        print(f"Full traceback: {error_details}")
        
        # 更新视频记录为失败状态
        try:
            with get_sync_db() as db:
                video = db.query(Video).filter(
                    Video.url == video_url,
                    Video.project_id == project_id
                ).order_by(desc(Video.created_at)).first()
                if video:
                    video.status = "failed"
                    video.download_progress = 0.0
                    db.commit()
                    print(f"Updated video to failed state: video_id={video.id}")
                    
                    # 只更新数据库，不发送WebSocket通知
                    # 前端会通过定时查询获取最新状态
        except Exception as db_error:
            print(f"Failed to update video failed status: {type(db_error).__name__}: {db_error}")
        
        try:
            _update_task_status(self.request.id, ProcessingTaskStatus.FAILURE, 0, f"{error_type}: {error_msg}")
        except Exception as status_error:
            print(f"Failed to update task status: {type(status_error).__name__}: {status_error}")
        
        raise Exception(f"{error_type}: {error_msg}")
    finally:
        # 清理cookie文件（如果存在）
        if cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
                print(f"已清理cookie文件: {cookies_path}")
            except Exception as cleanup_error:
                print(f"清理cookie文件失败: {cleanup_error}")