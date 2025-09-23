from celery import shared_task
import asyncio
import tempfile
import requests
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
from app.models import Video, VideoSubSlice, ProcessingTask
from sqlalchemy import select
from app.tasks.subtasks.task_utils import run_async, update_task_status

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True, ignore_result=False, name='app.tasks.video_tasks.extract_sub_slice_audio')
def extract_sub_slice_audio(self, video_id: str, project_id: int, user_id: int, video_minio_path: str, sub_slice_id: int, create_processing_task: bool = True, trigger_srt_after_audio: bool = False) -> Dict[str, Any]:
    """Extract audio from video sub-slice using ffmpeg"""
    
    def _ensure_processing_task_exists(celery_task_id: str, video_id: int) -> bool:
        """确保处理任务记录存在"""
        try:
            with get_sync_db() as db:
                state_manager = get_state_manager(db)
                
                # 检查任务是否已存在
                task = db.query(ProcessingTask).filter(
                    ProcessingTask.celery_task_id == celery_task_id
                ).first()
                
                if not task:
                    # 创建新的处理任务记录
                    task = ProcessingTask(
                        video_id=int(video_id),
                        task_type=ProcessingTaskType.EXTRACT_AUDIO,
                        task_name="子切片音频提取",
                        celery_task_id=celery_task_id,
                        input_data={"video_minio_path": video_minio_path, "sub_slice_id": sub_slice_id},
                        status=ProcessingTaskStatus.RUNNING,
                        started_at=datetime.utcnow(),
                        progress=0.0,
                        stage=ProcessingStage.EXTRACT_AUDIO
                    )
                    db.add(task)
                    db.commit()
                    print(f"Created new processing task for celery_task_id: {celery_task_id}")
                    return True
                return True
        except Exception as e:
            # 检查是否是重复键错误
            if "Duplicate entry" in str(e):
                print(f"Processing task already exists for celery_task_id: {celery_task_id}")
                return True
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
            
            update_task_status(celery_task_id, status, progress, message, error, ProcessingStage.EXTRACT_AUDIO)
            
            # 更新数据库状态，供WebSocket后台查询
            try:
                # 获取task记录以找到video_id
                with get_sync_db() as db:
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
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "开始提取子切片音频")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '开始提取子切片音频'})
        
        # 总是提取子切片音频，不使用父视频音频优化
        audio_extraction_completed = False
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_filename = f"{video_id}.mp4"
            video_path = temp_path / video_filename
                
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
                
                response = requests.get(video_url, stream=True)
                response.raise_for_status()
                
                with open(video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 65, "正在提取音频")
                self.update_state(state='PROGRESS', meta={'progress': 65, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '正在提取音频'})

                result = run_async(
                    audio_processor.extract_audio_from_video(
                        video_path=str(video_path),
                        video_id=video_id,
                        project_id=project_id,
                        user_id=user_id,
                        custom_filename=f"{video_id}_subslice_{sub_slice_id}"
                    )
                )

                # 检查并转换音频采样率（在临时目录上下文内执行）
                if result.get('success'):
                    try:
                        # 音频文件需要在临时目录上下文中进行采样率检查
                        # 从MinIO下载音频文件到当前临时目录

                        # 从MinIO下载刚上传的音频文件到本地临时目录
                        audio_url = run_async(minio_service.get_file_url(result['object_name'], expiry=3600))
                        if not audio_url:
                            raise Exception("无法获取刚上传的音频文件URL")

                        audio_temp_path = temp_path / result['audio_filename']

                        response = requests.get(audio_url, stream=True)
                        response.raise_for_status()

                        with open(audio_temp_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)

                        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 85, "正在检查音频采样率")
                        self.update_state(state='PROGRESS', meta={'progress': 85, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '正在检查音频采样率'})

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
                                logger.info(f"子切片音频采样率已转换并重新上传: {audio_url}")
                            else:
                                logger.error("转换后的音频文件上传失败")
                                raise Exception("转换后的音频文件上传失败")
                    except Exception as e:
                        logger.error(f"子切片音频采样率检查/转换失败: {str(e)}")
                        # 不中断整个流程，继续使用原始音频
        # 处理成功逻辑
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
                            message="子切片音频提取完成",
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
                        _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "子切片音频提取完成")
            except Exception as e:
                print(f"状态更新失败: {e}")
                # 回退到原来的状态更新方式
                try:
                    _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "子切片音频提取完成")
                except Exception as fallback_error:
                    print(f"回退状态更新也失败: {fallback_error}")
            self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.EXTRACT_AUDIO, 'message': '子切片音频提取完成'})
            
            # 更新子切片的音频路径和时长信息
            try:
                # 使用同步方式更新数据库，避免async loop问题
                with get_sync_db() as db:
                    sub_slice = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                    
                    if sub_slice:
                        # 直接使用提取的音频，而不是父视频的音频
                        if result.get('minio_path'):
                            sub_slice.audio_url = result['minio_path']
                            sub_slice.audio_processing_status = "completed"
                            sub_slice.audio_progress = 100
                            print(f"设置子切片音频路径: sub_slice_id={sub_slice_id}, audio_url={result['minio_path']}")
                        else:
                            sub_slice.audio_processing_status = "failed"
                            sub_slice.audio_error_message = "无法获取有效的音频文件路径"
                        
                        db.commit()
                        print(f"已更新子切片音频状态: sub_slice_id={sub_slice_id}")
            except Exception as e:
                print(f"更新子切片音频路径失败: {e}")
                # 更新子切片状态为失败
                try:
                    async def _update_sub_slice_status():
                        async with AsyncSessionLocal() as db:
                            stmt = select(VideoSubSlice).where(VideoSubSlice.id == sub_slice_id)
                            sub_slice_result = await db.execute(stmt)
                            sub_slice = sub_slice_result.scalar_one_or_none()
                            
                            if sub_slice:
                                sub_slice.audio_processing_status = "failed"
                                await db.commit()
                                print(f"已更新子切片音频状态为失败: sub_slice_id={sub_slice_id}")
                    
                    run_async(_update_sub_slice_status())
                except Exception as status_error:
                    print(f"更新子切片状态失败: {status_error}")
            
            # 如果需要，触发SRT生成任务
            if trigger_srt_after_audio:
                try:
                    from app.tasks.subtasks.srt_task import generate_srt
                    import time
                    import random
                    
                    # 添加随机延迟以避免同时请求ASR服务 (1-3秒)
                    delay = random.uniform(1, 3)
                    print(f"子切片音频提取成功，将在 {delay:.1f} 秒后触发SRT生成任务: sub_slice_id={sub_slice_id}")
                    time.sleep(delay)
                    
                    srt_task = generate_srt.delay(
                        video_id=str(video_id),
                        project_id=project_id,
                        user_id=user_id,
                        split_files=[],
                        sub_slice_id=sub_slice_id,
                        create_processing_task=True
                    )
                    print(f"SRT生成任务已提交: task_id={srt_task.id}")
                except Exception as srt_error:
                    print(f"触发SRT生成任务失败: {srt_error}")
            
            return {
                'status': 'completed',
                'video_id': video_id,
                'sub_slice_id': sub_slice_id,
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
            
            # 更新子切片状态为失败
            try:
                async def _update_sub_slice_status():
                    async with AsyncSessionLocal() as db:
                        stmt = select(VideoSubSlice).where(VideoSubSlice.id == sub_slice_id)
                        sub_slice_result = await db.execute(stmt)
                        sub_slice = sub_slice_result.scalar_one_or_none()
                        
                        if sub_slice:
                            sub_slice.audio_processing_status = "failed"
                            sub_slice.audio_error_message = error_msg
                            await db.commit()
                            print(f"已更新子切片音频状态为失败: sub_slice_id={sub_slice_id}, error={error_msg}")
                
                run_async(_update_sub_slice_status())
            except Exception as sub_slice_error:
                print(f"更新子切片状态失败: {sub_slice_error}")
            
            raise Exception(f"{error_type}: {error_msg}")
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        error_details = traceback.format_exc()
        
        print(f"DEBUG: 捕获到主异常: {error_type}: {error_msg}")
        print(f"DEBUG: 完整堆栈跟踪: {error_details}")
        
        try:
            _update_task_status(
                self.request.id, 
                ProcessingTaskStatus.FAILURE, 
                0, 
                f"{error_type}: {error_msg}"
            )
        except Exception as status_error:
            print(f"Failed to update task status: {type(status_error).__name__}: {status_error}")
        
        # 更新子切片状态为失败
        try:
            async def _update_sub_slice_status():
                async with AsyncSessionLocal() as db:
                    stmt = select(VideoSubSlice).where(VideoSubSlice.id == sub_slice_id)
                    sub_slice_result = await db.execute(stmt)
                    sub_slice = sub_slice_result.scalar_one_or_none()
                    
                    if sub_slice:
                        sub_slice.audio_processing_status = "failed"
                        sub_slice.audio_error_message = error_msg
                        await db.commit()
                        print(f"已更新子切片音频状态为失败: sub_slice_id={sub_slice_id}, error={error_msg}")
            
            run_async(_update_sub_slice_status())
        except Exception as sub_slice_error:
            print(f"更新子切片状态失败: {sub_slice_error}")
        
        raise Exception(f"{error_type}: {error_msg}")