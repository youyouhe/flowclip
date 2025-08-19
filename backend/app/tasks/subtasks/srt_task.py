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
from app.core.database import get_sync_db
from app.core.config import settings
from app.models import Video, ProcessingTask
from sqlalchemy import select

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='app.tasks.video_tasks.generate_srt')
def generate_srt(self, video_id: str, project_id: int, user_id: int, split_files: list = None, slice_id: int = None, sub_slice_id: int = None, create_processing_task: bool = True) -> Dict[str, Any]:
    """Generate SRT subtitles from audio using ASR"""
    
    def _ensure_processing_task_exists(celery_task_id: str, video_id: int) -> bool:
        """确保处理任务记录存在"""
        try:
            with get_sync_db() as db:
                state_manager = get_state_manager(db)
                
                # 尝试创建任务记录，如果已存在则忽略
                try:
                    task = ProcessingTask(
                        video_id=int(video_id),
                        task_type=ProcessingTaskType.GENERATE_SRT,
                        task_name="字幕生成",
                        celery_task_id=celery_task_id,
                        input_data={"direct_audio": True},
                        status=ProcessingTaskStatus.RUNNING,
                        started_at=datetime.utcnow(),
                        progress=0.0,
                        stage=ProcessingStage.GENERATE_SRT
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
    
    def _get_audio_file_from_db(video_id_str: str, sub_slice_id: int = None) -> dict:
        """从数据库获取音频文件信息 - 同步版本"""
        with get_sync_db() as db:
            from sqlalchemy import select
            from app.models.processing_task import ProcessingTask
            from app.models.video import Video
            from app.models.video_slice import VideoSubSlice
            
            # 如果是子切片，直接从子切片记录中获取音频路径和时间信息
            if sub_slice_id:
                print(f"DEBUG: 查询子切片信息: sub_slice_id={sub_slice_id}")
                sub_slice = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                if sub_slice:
                    print(f"DEBUG: 找到子切片: sub_slice_id={sub_slice_id}, audio_url={getattr(sub_slice, 'audio_url', 'None')}, start_time={getattr(sub_slice, 'start_time', 'None')}, end_time={getattr(sub_slice, 'end_time', 'None')}")
                    if sub_slice.audio_url:
                        result = {
                            "audio_path": sub_slice.audio_url, 
                            "video_id": video_id_str,
                            "start_time": sub_slice.start_time,
                            "end_time": sub_slice.end_time
                        }
                        print(f"DEBUG: 返回子切片音频信息: {result}")
                        return result
                    else:
                        print(f"警告: 子切片 {sub_slice_id} 没有音频文件路径")
                        # 添加更多调试信息
                        print(f"DEBUG: 子切片完整信息: id={sub_slice.id}, slice_id={sub_slice.slice_id}, cover_title={sub_slice.cover_title}")
                        print(f"DEBUG: 子切片状态信息: audio_processing_status={getattr(sub_slice, 'audio_processing_status', 'None')}, audio_task_id={getattr(sub_slice, 'audio_task_id', 'None')}")
                        # 检查父视频的音频信息
                        try:
                            parent_video = db.query(Video).filter(Video.id == int(video_id_str)).first()
                            if parent_video and parent_video.processing_metadata and parent_video.processing_metadata.get('audio_path'):
                                parent_audio_path = parent_video.processing_metadata['audio_path']
                                print(f"DEBUG: 父视频有音频路径，可以使用: {parent_audio_path}")
                                # 即使子切片没有设置audio_url，也可以使用父视频的音频路径
                                result = {
                                    "audio_path": parent_audio_path, 
                                    "video_id": video_id_str,
                                    "start_time": sub_slice.start_time,
                                    "end_time": sub_slice.end_time
                                }
                                print(f"DEBUG: 使用父视频音频信息: {result}")
                                return result
                            else:
                                print(f"DEBUG: 父视频也没有音频路径")
                        except Exception as parent_error:
                            print(f"DEBUG: 查询父视频音频信息失败: {parent_error}")
                        return None
                else:
                    print(f"警告: 未找到子切片记录: sub_slice_id={sub_slice_id}")
                    return None
            
            # 首先查找视频记录（非子切片情况）
            video = db.query(Video).filter(Video.id == int(video_id_str)).first()
            if not video:
                return None
                
            # 尝试从视频的processing_metadata中获取音频路径
            audio_path = None
            if video.processing_metadata and video.processing_metadata.get('audio_path'):
                audio_path = video.processing_metadata.get('audio_path')
            else:
                # 查找最新的成功完成的extract_audio任务
                stmt = select(ProcessingTask).where(
                    ProcessingTask.video_id == int(video_id_str),
                    ProcessingTask.task_type == ProcessingTaskType.EXTRACT_AUDIO,
                    ProcessingTask.status == ProcessingTaskStatus.SUCCESS
                ).order_by(ProcessingTask.completed_at.desc())
                
                result = db.execute(stmt)
                task = result.first()
                
                if task and task[0].output_data:
                    audio_path = task[0].output_data.get('minio_path')
            
            if audio_path:
                return {"audio_path": audio_path, "video_id": video_id_str}
            return None
    
    def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
        """更新任务状态 - 同步版本"""
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
                        'stage': ProcessingStage.GENERATE_SRT
                    }
                )
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
        return loop.run_until_complete(coro)
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "开始生成字幕")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.GENERATE_SRT, 'message': '开始生成字幕'})
        
        # 获取音频文件信息
        audio_info = _get_audio_file_from_db(video_id, sub_slice_id)
        if not audio_info:
            if sub_slice_id:
                error_msg = f"没有找到可用的音频文件，请先提取音频 (sub_slice_id={sub_slice_id})"
            else:
                error_msg = "没有找到可用的音频文件，请先提取音频"
            _update_task_status(celery_task_id, ProcessingTaskStatus.FAILURE, 0, error_msg)
            raise Exception(error_msg)
        
        with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                audio_filename = f"{video_id}.wav"
                audio_path = temp_path / audio_filename
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 30, "正在下载音频文件")
                self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': ProcessingStage.GENERATE_SRT, 'message': '正在下载音频文件'})
                
                # Handle both full URLs and object names
                audio_minio_path = audio_info['audio_path']
                from app.core.config import settings
                bucket_prefix = f"{settings.minio_bucket_name}/"
                if audio_minio_path.startswith(bucket_prefix):
                    object_name = audio_minio_path[len(bucket_prefix):]
                else:
                    # Handle both full URLs and object names
                    if "http" in audio_minio_path:
                        # It's a full URL, extract the object name
                        from urllib.parse import urlparse
                        parsed = urlparse(audio_minio_path)
                        path_parts = parsed.path.strip('/').split('/', 1)
                        if len(path_parts) > 1:
                            object_name = path_parts[1]  # Skip bucket name
                        else:
                            object_name = audio_minio_path
                    else:
                        object_name = audio_minio_path
                
                audio_url = run_async(minio_service.get_file_url(object_name, expiry=3600))
                if not audio_url:
                    raise Exception(f"无法获取音频文件URL: {object_name}")
                
                import requests
                response = requests.get(audio_url, stream=True)
                response.raise_for_status()
                
                with open(audio_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 70, "正在生成字幕")
                self.update_state(state='PROGRESS', meta={'progress': 70, 'stage': ProcessingStage.GENERATE_SRT, 'message': '正在生成字幕'})
            
                # 准备自定义文件名
                if slice_id:
                    custom_filename = f"{video_id}_slice_{slice_id}.srt"
                elif sub_slice_id:
                    custom_filename = f"{video_id}_subslice_{sub_slice_id}.srt"
                else:
                    custom_filename = None
                
                # 准备时间参数（如果是子切片）
                start_time = None
                end_time = None
                if sub_slice_id and audio_info and 'start_time' in audio_info and 'end_time' in audio_info:
                    start_time = audio_info['start_time']
                    end_time = audio_info['end_time']
                    print(f"为子切片 {sub_slice_id} 生成SRT，时间范围: {start_time}s - {end_time}s")
                
                result = run_async(
                    audio_processor.generate_srt_from_audio(
                        audio_path=str(audio_path),
                        video_id=video_id,
                        project_id=project_id,
                        user_id=user_id,
                        custom_filename=custom_filename,
                        start_time=start_time,
                        end_time=end_time
                    )
                )
                
                if result.get('success'):
                    # 保存SRT生成结果到数据库 - 使用同步版本
                    try:
                        with get_sync_db() as db:
                            # 使用audio_processor返回的srt_url
                            srt_url = result.get('minio_path', result.get('srt_url'))
                            print(f"SRT文件URL: {srt_url}")
                            
                            try:
                                if slice_id:
                                    # 更新切片的srt_url
                                    from app.models import VideoSlice
                                    slice_record = db.query(VideoSlice).filter(VideoSlice.id == slice_id).first()
                                    if slice_record:
                                        slice_record.srt_url = srt_url
                                        slice_record.srt_processing_status = "completed"
                                        print(f"已更新切片: slice_id={slice_id}, srt_url={srt_url}")
                                    else:
                                        print(f"未找到切片记录: slice_id={slice_id}")
                                elif sub_slice_id:
                                    # 更新子切片的srt_url
                                    print(f"DEBUG: 开始更新子切片SRT URL: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                    from app.models import VideoSubSlice
                                    sub_slice_record = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                                    if sub_slice_record:
                                        print(f"DEBUG: 找到子切片记录: sub_slice_id={sub_slice_id}")
                                        sub_slice_record.srt_url = srt_url
                                        sub_slice_record.srt_processing_status = "completed"
                                        print(f"DEBUG: 设置子切片SRT URL: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                        print(f"已更新子切片: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                    else:
                                        print(f"DEBUG: 未找到子切片记录: sub_slice_id={sub_slice_id}")
                                        print(f"未找到子切片记录: sub_slice_id={sub_slice_id}")
                                else:
                                    print("警告: 既没有slice_id也没有sub_slice_id，无法保存srt_url")
                            except Exception as slice_error:
                                print(f"更新切片srt_url失败: {slice_error}")
                                import traceback
                                print(f"详细错误信息: {traceback.format_exc()}")
                            
                            # 尝试更新ProcessingTask记录（如果存在的话）
                            try:
                                state_manager = get_state_manager(db)
                                task = db.query(ProcessingTask).filter(
                                    ProcessingTask.celery_task_id == celery_task_id
                                ).first()
                                
                                if task:
                                    print(f"找到任务记录: task.id={task.id}, 更新状态...")
                                    state_manager.update_task_status_sync(
                                        task_id=task.id,
                                        status=ProcessingTaskStatus.SUCCESS,
                                        progress=100,
                                        message="字幕生成完成",
                                        output_data={
                                            'srt_filename': result['srt_filename'],
                                            'minio_path': result['minio_path'],
                                            'object_name': result['object_name'],
                                            'srt_url': srt_url,
                                            'total_segments': result['total_segments'],
                                            'processing_stats': result['processing_stats'],
                                            'asr_params': result['asr_params']
                                        },
                                        stage=ProcessingStage.GENERATE_SRT
                                    )
                                    
                                    # 更新视频记录
                                    video = db.query(Video).filter(Video.id == task.video_id).first()
                                    if video:
                                        video.processing_progress = 100
                                        video.processing_stage = ProcessingStage.GENERATE_SRT.value
                                        video.processing_message = "字幕生成完成"
                                        video.processing_completed_at = datetime.utcnow()
                                        print(f"已更新视频记录: video_id={video.id}")
                                    
                                    # 更新processing_status表
                                    try:
                                        from app.models.processing_task import ProcessingStatus
                                        processing_status = db.query(ProcessingStatus).filter(
                                            ProcessingStatus.video_id == task.video_id
                                        ).first()
                                        if processing_status:
                                            processing_status.overall_status = ProcessingTaskStatus.SUCCESS
                                            processing_status.overall_progress = 100
                                            processing_status.current_stage = ProcessingStage.COMPLETED.value
                                            print(f"已更新processing_status整体状态: video_id={task.video_id}")
                                    except Exception as status_error:
                                        print(f"更新processing_status失败: {status_error}")
                                        
                                else:
                                    print(f"未找到任务记录: celery_task_id={celery_task_id}，但这不影响srt_url保存")
                                    
                            except Exception as task_error:
                                print(f"更新任务状态失败，但srt_url已保存: {task_error}")
                            
                            # 提交数据库更改
                            db.commit()
                            print(f"数据库提交完成，srt_url已保存到对应切片表")
                            
                    except Exception as e:
                        print(f"保存SRT结果失败: {e}")
                        import traceback
                        print(f"详细错误信息: {traceback.format_exc()}")
                        # 如果失败，尝试回滚
                        try:
                            db.rollback()
                        except:
                            pass
                    
                    self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.GENERATE_SRT, 'message': '字幕生成完成'})
                    return {
                        'status': 'completed',
                        'video_id': video_id,
                        'srt_filename': custom_filename or result.get('srt_filename', f"{video_id}.srt"),
                        'minio_path': srt_url,
                        'object_name': srt_url,
                        'total_segments': result['total_segments'],
                        'processing_stats': result['processing_stats'],
                        'asr_params': result['asr_params']
                    }
                else:
                    raise Exception(result.get('error', 'Unknown error'))
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_type = type(e).__name__
        error_details = traceback.format_exc()
        
        print(f"SRT generation failed - {error_type}: {error_msg}")
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