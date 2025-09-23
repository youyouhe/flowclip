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
from app.services.audio_processor import audio_processor
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.core.database import get_sync_db, AsyncSessionLocal
from app.core.config import settings
from app.models import Video, ProcessingTask
from sqlalchemy import select

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True, ignore_result=False, name='app.tasks.video_tasks.extract_audio')
def extract_audio(self, video_id: str, project_id: int, user_id: int, video_minio_path: str, create_processing_task: bool = True, slice_id: int = None, trigger_srt_after_audio: bool = False) -> Dict[str, Any]:
    """Extract audio from video using ffmpeg"""
    
    # 在执行任务前重新加载MinIO配置，确保使用最新的访问密钥
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
    
    def _ensure_processing_task_exists(celery_task_id: str, video_id: int) -> bool:
        """确保处理任务记录存在"""
        try:
            with get_sync_db() as db:
                state_manager = get_state_manager(db)
                
                # 尝试创建任务记录，如果已存在则忽略
                try:
                    from app.core.constants import ProcessingTaskType
                    task = ProcessingTask(
                        video_id=int(video_id),
                        task_type=ProcessingTaskType.EXTRACT_AUDIO,
                        task_name="音频提取",
                        celery_task_id=celery_task_id,
                        input_data={"video_minio_path": video_minio_path},
                        status=ProcessingTaskStatus.RUNNING,
                        started_at=datetime.utcnow(),
                        progress=0.0,
                        stage=ProcessingStage.EXTRACT_AUDIO
                    )
                    db.add(task)
                    db.commit()
                    print(f"Created new processing task for celery_task_id: {celery_task_id}")
                except Exception as create_error:
                    # 如果创建失败（可能是因为重复键），则回滚并忽略错误
                    db.rollback()
                    # 检查任务是否已存在
                    existing_task = db.query(ProcessingTask).filter(
                        ProcessingTask.celery_task_id == celery_task_id
                    ).first()
                    if not existing_task:
                        # 如果任务确实不存在，但创建失败了，重新抛出错误
                        raise create_error
                    # 如果任务已存在，正常返回
                    print(f"Processing task already exists for celery_task_id: {celery_task_id}")
                return True
        except Exception as e:
            print(f"Error ensuring processing task exists: {e}")
            return False
    
    def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
        """更新任务状态 - 同步版本，确保任务存在"""
        # 如果这个任务是作为子任务运行的，不创建处理任务记录
        if not create_processing_task:
            print(f"Skipping status update for sub-task {celery_task_id} (create_processing_task=False)")
            return
            
        try:
            # 确保任务存在
            _ensure_processing_task_exists(celery_task_id, video_id)
            
            with get_sync_db() as db:
                state_manager = get_state_manager(db)
                state_manager.update_celery_task_status_sync(
                    celery_task_id=celery_task_id,
                    celery_status=status,
                    meta={
                        'progress': progress,
                        'message': message,
                        'error': error,
                        'stage': ProcessingStage.EXTRACT_AUDIO
                    }
                )
                
                # 更新数据库状态，供WebSocket后台查询
                try:
                    # 获取task记录以找到video_id
                    task = db.query(ProcessingTask).filter(
                        ProcessingTask.celery_task_id == celery_task_id
                    ).first()
                    
                    if task:
                        # 更新视频记录的进度状态
                        video = db.query(Video).filter(Video.id == task.video_id).first()
                        if video:
                            video.processing_progress = progress
                            video.processing_stage = ProcessingStage.EXTRACT_AUDIO.value
                            video.processing_message = message or ""
                            db.commit()
                            print(f"数据库状态已更新 - video_id: {task.video_id}, progress: {progress}")
                            
                except Exception as db_error:
                    print(f"数据库更新失败: {db_error}")
                
        except ValueError as e:
            # 记录详细错误信息
            print(f"Warning: Processing task update failed - {type(e).__name__}: {e}")
        except Exception as e:
            print(f"Error updating task status: {type(e).__name__}: {e}")
    
    def run_async(coro):
        """运行异步代码的辅助函数"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # 如果循环已经在运行，使用ensure_future
        if loop.is_running():
            future = asyncio.ensure_future(coro, loop=loop)
            return future
        else:
            return loop.run_until_complete(coro)
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "开始提取音频")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '开始提取音频'})
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_filename = f"{video_id}.mp4"
            video_path = temp_path / video_filename
            
            from app.core.config import settings
            bucket_prefix = f"{settings.minio_bucket_name}/"
            if video_minio_path.startswith(bucket_prefix):
                object_name = video_minio_path[len(bucket_prefix):]
            else:
                # Handle both full URLs and object names
                if "http" in video_minio_path:
                    # It's a full URL, extract the object name
                    from urllib.parse import urlparse
                    parsed = urlparse(video_minio_path)
                    path_parts = parsed.path.strip('/').split('/', 1)
                    if len(path_parts) > 1:
                        object_name = path_parts[1]  # Skip bucket name
                    else:
                        object_name = video_minio_path
                else:
                    object_name = video_minio_path
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 30, "正在下载视频文件")
            self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '正在下载视频文件'})
            
            video_url = run_async(minio_service.get_file_url(object_name, expiry=3600))
            if not video_url:
                raise Exception("无法获取视频文件URL")
            
            import requests
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 70, "正在提取音频")
            self.update_state(state='PROGRESS', meta={'progress': 70, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '正在提取音频'})
            
            result = run_async(
                audio_processor.extract_audio_from_video(
                    video_path=str(video_path),
                    video_id=video_id,
                    project_id=project_id,
                    user_id=user_id
                )
            )
            
            if result.get('success'):
                try:
                    # 音频文件已经在临时目录中，直接检查本地文件
                    audio_filename = result['audio_filename']
                    audio_temp_path = temp_path / audio_filename
                    
                    # 检查并转换采样率
                    converted_audio_path = run_async(
                        audio_processor.convert_audio_sample_rate(str(audio_temp_path), 16000)
                    )
                    
                    # 如果采样率被转换，需要重新上传文件
                    if converted_audio_path != str(audio_temp_path):
                        # 重新上传转换后的音频文件
                        audio_url = run_async(
                            minio_service.upload_file(
                                converted_audio_path,
                                result['object_name'],
                                f"audio/{result['audio_format']}"
                            )
                        )
                        
                        if audio_url:
                            # 更新结果中的音频路径和文件大小
                            result['minio_path'] = audio_url
                            result['file_size'] = Path(converted_audio_path).stat().st_size
                            print(f"音频采样率已转换并重新上传: {audio_url}")
                        else:
                            print("转换后的音频文件上传失败")
                            raise Exception("转换后的音频文件上传失败")
                except Exception as e:
                    print(f"音频采样率检查/转换失败: {str(e)}")
                    # 不中断整个流程，继续使用原始音频
            
            if result.get('success'):
                try:
                    # 更新处理任务的output_data
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
                                message="音频提取完成",
                                output_data={
                                    'audio_filename': result['audio_filename'],
                                    'minio_path': result['minio_path'],
                                    'object_name': result['object_name'],
                                    'duration': result['duration'],
                                    'file_size': result['file_size'],
                                    'audio_format': result['audio_format']
                                },
                                stage=ProcessingStage.EXTRACT_AUDIO
                            )
                        else:
                            _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "音频提取完成")
                except Exception as e:
                    print(f"状态更新失败: {e}")
                    # 回退到原来的状态更新方式
                    try:
                        _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "音频提取完成")
                    except Exception as fallback_error:
                        print(f"回退状态更新也失败: {fallback_error}")
                self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '音频提取完成'})
                # 更新视频的音频路径和时长信息
                try:
                    async def _update_audio_path():
                        async with AsyncSessionLocal() as db:
                            from sqlalchemy import select
                            from app.models.video import Video
                            
                            stmt = select(Video).where(Video.id == int(video_id))
                            video_result = await db.execute(stmt)
                            video = video_result.scalar_one()
                            
                            # 更新音频路径和时长信息到processing_metadata
                            if not video.processing_metadata:
                                video.processing_metadata = {}
                            video.processing_metadata['audio_path'] = result['minio_path']
                            video.processing_metadata['audio_info'] = {
                                'duration': result.get('duration', 0),
                                'audio_filename': result.get('audio_filename'),
                                'file_size': result.get('file_size'),
                                'audio_format': result.get('audio_format')
                            }
                            await db.commit()
                    
                    # 使用同步方式运行异步函数，避免事件循环问题
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_update_audio_path())
                    loop.close()
                except Exception as e:
                    print(f"更新音频路径失败: {e}")
                
                # 如果需要，触发SRT生成任务
                if trigger_srt_after_audio and slice_id:
                    try:
                        from app.tasks.subtasks.srt_task import generate_srt
                        print(f"音频提取成功，触发SRT生成任务: slice_id={slice_id}")
                        srt_task = generate_srt.delay(
                            video_id=str(video_id),
                            project_id=project_id,
                            user_id=user_id,
                            split_files=[],
                            slice_id=slice_id,
                            create_processing_task=True
                        )
                        print(f"SRT生成任务已提交: task_id={srt_task.id}")
                    except Exception as srt_error:
                        print(f"触发SRT生成任务失败: {srt_error}")
                
                return {
                    'status': 'completed',
                    'video_id': video_id,
                    'audio_filename': result['audio_filename'],
                    'minio_path': result['minio_path'],
                    'object_name': result['object_name'],
                    'duration': result['duration'],
                    'file_size': result['file_size'],
                    'audio_format': result['audio_format']
                }
            else:
                import traceback
                error_msg = result.get('error', 'Unknown error')
                error_type = 'ProcessingError'
                error_details = traceback.format_stack()
                
                try:
                    _update_task_status(celery_task_id, ProcessingTaskStatus.FAILURE, 0, f"{error_type}: {error_msg}")
                except Exception as status_error:
                    print(f"Failed to update task status: {type(status_error).__name__}: {status_error}")
                raise Exception(f"{error_type}: {error_msg}")
                
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        error_details = traceback.format_exc()
        
        print(f"Audio extraction failed - {error_type}: {error_msg}")
        print(f"Full traceback: {error_details}")
        
        try:
            _update_task_status(
                self.request.id, 
                ProcessingTaskStatus.FAILURE, 
                0, 
                f"{error_type}: {error_msg}"
            )
        except Exception as status_error:
            print(f"Failed to update task status: {type(status_error).__name__}: {status_error}")
        
        raise Exception(f"{error_type}: {error_msg}")