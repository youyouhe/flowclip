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
from app.services.system_config_service import SystemConfigService

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='app.tasks.video_tasks.generate_srt',
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},  # 重试3次，间隔60秒
    retry_backoff=True,
    retry_jitter=True
)
def generate_srt(self, video_id: str, project_id: int, user_id: int, split_files: list = None, slice_id: int = None, sub_slice_id: int = None, create_processing_task: bool = True) -> Dict[str, Any]:
    """Generate SRT subtitles from audio using ASR"""
    
    print(f"DEBUG: SRT任务开始执行 - video_id: {video_id}, project_id: {project_id}, user_id: {user_id}")
    
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
    
    def _ensure_processing_task_exists(celery_task_id: str, video_id: str, slice_id: int = None, sub_slice_id: int = None) -> bool:
        """确保处理任务记录存在"""
        try:
            with get_sync_db() as db:
                state_manager = get_state_manager(db)

                # 验证video_id参数
                if video_id is None or video_id == "None" or video_id == "":
                    print(f"Error: Invalid video_id parameter: {video_id}")
                    return False

                try:
                    video_id_int = int(video_id)
                except (ValueError, TypeError):
                    print(f"Error: Cannot convert video_id to int: {video_id}")
                    return False

                # 构建input_data，包含关联信息
                input_data = {"direct_audio": True}
                if slice_id:
                    input_data["slice_id"] = slice_id
                if sub_slice_id:
                    input_data["sub_slice_id"] = sub_slice_id

                # 尝试创建任务记录，如果已存在则忽略
                try:
                    task = ProcessingTask(
                        video_id=video_id_int,
                        task_type=ProcessingTaskType.GENERATE_SRT,
                        task_name="字幕生成",
                        celery_task_id=celery_task_id,
                        input_data=input_data,
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
    
    def _get_audio_file_from_db(video_id_str: str, sub_slice_id: int = None, slice_id: int = None) -> dict:
        """从数据库获取音频文件信息 - 同步版本"""
        with get_sync_db() as db:
            from sqlalchemy import select
            from app.models.processing_task import ProcessingTask
            from app.models.video import Video
            from app.models.video_slice import VideoSubSlice, VideoSlice
            
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
            
            # 如果是full类型切片，从切片记录中获取音频路径
            elif slice_id:
                print(f"DEBUG: 查询切片信息: slice_id={slice_id}")
                video_slice = db.query(VideoSlice).filter(VideoSlice.id == slice_id).first()
                if video_slice and video_slice.audio_url:
                    print(f"DEBUG: 找到切片: slice_id={slice_id}, audio_url={video_slice.audio_url}")
                    result = {
                        "audio_path": video_slice.audio_url,
                        "video_id": video_id_str
                    }
                    print(f"DEBUG: 返回切片音频信息: {result}")
                    return result
                else:
                    print(f"警告: 切片 {slice_id} 没有音频文件路径")
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
            _ensure_processing_task_exists(celery_task_id, video_id, slice_id, sub_slice_id)
            
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
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        print(f"DEBUG: 获取到CeleryTaskID: {celery_task_id}")

        # 记录处理开始时间
        processing_start_time = time.time()

        # 动态获取最新的ASR服务URL和模型类型
        with get_sync_db() as db:
            from app.core.config import settings
            db_configs = SystemConfigService.get_all_configs_sync(db)
            asr_service_url = db_configs.get("asr_service_url", settings.asr_service_url)
            asr_model_type = db_configs.get("asr_model_type", settings.asr_model_type)
            logger.info(f"动态获取ASR服务URL: {asr_service_url}, 模型类型: {asr_model_type}")
        
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "Start Generating Subtitles")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.GENERATE_SRT, 'message': 'Start Generating Subtitles'})
        
        print(f"DEBUG: 任务状态已更新为运行中")
        
        
        # 获取音频文件信息
        audio_info = _get_audio_file_from_db(video_id, sub_slice_id, slice_id)
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
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 30, "The audio file is being downloaded.")
                self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': ProcessingStage.GENERATE_SRT, 'message': 'The audio file is being downloaded.'})
                
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
                
                def run_async(coro):
                    """运行异步代码的辅助函数"""
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    return loop.run_until_complete(coro)
                
                audio_url = run_async(minio_service.get_file_url(object_name, expiry=3600))
                if not audio_url:
                    raise Exception(f"无法获取音频文件URL: {object_name}")
                
                import requests
                response = requests.get(audio_url, stream=True)
                response.raise_for_status()
                
                with open(audio_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # 检查下载的文件大小
                downloaded_file_size = os.path.getsize(audio_path)
                print(f"下载的音频文件大小: {downloaded_file_size} bytes")
                if downloaded_file_size < 100:
                    raise Exception(f"下载的音频文件太小，可能下载失败，大小: {downloaded_file_size} bytes")
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 70, "Start Generating Subtitles")
                self.update_state(state='PROGRESS', meta={'progress': 70, 'stage': ProcessingStage.GENERATE_SRT, 'message': 'Start Generating Subtitles'})
            
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
                # 对于子切片，音频文件已经是分割好的完整文件，不需要再进行时间范围分割
                if not sub_slice_id and audio_info and 'start_time' in audio_info and 'end_time' in audio_info:
                    start_time = audio_info['start_time']
                    end_time = audio_info['end_time']
                    print(f"为完整音频生成SRT，时间范围: {start_time}s - {end_time}s")
                
                result = run_async(
                    audio_processor.generate_srt_from_audio(
                        audio_path=str(audio_path),
                        video_id=video_id,
                        project_id=project_id,
                        user_id=user_id,
                        custom_filename=custom_filename,
                        start_time=start_time,
                        end_time=end_time,
                        asr_service_url=asr_service_url,  # 传递最新的URL
                        asr_model_type=asr_model_type  # 传递模型类型
                    )
                )

                # TUS异步处理：Celery任务只负责提交，不等待callback
                if result.get('strategy') == 'tus' and result.get('success'):
                    logger.info(f"✅ TUS任务提交成功: task_id={result.get('task_id')}")
                    logger.info(f"📝 ASR处理将由callback服务器异步完成，Celery任务结束")

                    # Celery任务完成，后续处理由callback服务器负责
                    # 不需要等待，让callback服务器处理所有的数据库更新和SRT下载
                
                if result.get('success'):
                    strategy = result.get('strategy', 'standard')

                    if strategy == 'tus':
                        # TUS异步处理 - Celery任务完成，callback服务器负责后续处理
                        self.update_state(state='SUCCESS', meta={
                            'progress': 15,
                            'stage': ProcessingStage.GENERATE_SRT,
                            'message': f'TUS ASR任务已提交 (ID: {result.get("task_id")})，等待异步处理',
                            'tus_task_id': result.get('task_id'),
                            'async_processing': True
                        })
                        return {
                            'status': 'processing',
                            'video_id': video_id,
                            'strategy': 'tus_async',
                            'task_id': result.get('task_id'),
                            'message': 'TUS任务已启动，等待callback_server处理',
                            'processing_info': result.get('processing_info', {}),
                        }
                    else:
                        # 标准处理或同步TUS处理 - 正常处理（保持原有逻辑）
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
                                            # 1. 先保存SRT URL
                                            slice_record.srt_url = srt_url
                                            print(f"🔗 SRT URL已保存: slice_id={slice_id}, srt_url={srt_url}")

                                            # 2. 验证SRT URL确实有效后再设置状态为completed
                                            if srt_url:
                                                slice_record.srt_processing_status = "completed"
                                                print(f"✅ 切片状态已更新为completed: slice_id={slice_id}, srt_url={srt_url}")
                                            else:
                                                print(f"⚠️ SRT URL为空，不更新状态: slice_id={slice_id}")
                                                slice_record.srt_processing_status = "failed"
                                                slice_record.srt_error_message = "SRT URL保存失败"
                                        else:
                                            print(f"未找到切片记录: slice_id={slice_id}")
                                    elif sub_slice_id:
                                        # 更新子切片的srt_url
                                        from app.models import VideoSubSlice
                                        sub_slice_record = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                                        if sub_slice_record:
                                            # 1. 先保存SRT URL
                                            sub_slice_record.srt_url = srt_url
                                            print(f"🔗 SRT URL已保存: sub_slice_id={sub_slice_id}, srt_url={srt_url}")

                                            # 2. 验证SRT URL确实有效后再设置状态为completed
                                            if srt_url:
                                                sub_slice_record.srt_processing_status = "completed"
                                                print(f"✅ 子切片状态已更新为completed: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                            else:
                                                print(f"⚠️ SRT URL为空，不更新状态: sub_slice_id={sub_slice_id}")
                                                sub_slice_record.srt_processing_status = "failed"
                                                sub_slice_record.srt_error_message = "SRT URL保存失败"
                                        else:
                                            print(f"未找到子切片记录: sub_slice_id={sub_slice_id}")
                                    else:
                                        print("警告: 既没有slice_id也没有sub_slice_id，无法保存srt_url")
                                except Exception as slice_error:
                                    print(f"更新切片srt_url失败: {slice_error}")

                                # 提交数据库更改
                                db.commit()
                                print(f"数据库提交完成")

                        except Exception as e:
                            print(f"保存SRT结果失败: {e}")

                        self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.GENERATE_SRT, 'message': '字幕生成完成'})
                        return {
                            'status': 'completed',
                            'video_id': video_id,
                            'srt_filename': custom_filename or result.get('srt_filename', f"{video_id}.srt"),
                            'minio_path': srt_url,
                            'object_name': srt_url,
                            'total_segments': result.get('total_segments', 0),
                            'processing_stats': result.get('processing_stats', {}),
                            'asr_params': result.get('asr_params', {})
                        }
                else:
                    if 'srt_content' in result and result['srt_content']:
                        # 如果有SRT内容，说明处理成功
                        logger.info(f"SRT生成成功，内容长度: {len(result['srt_content'])}")

                        # 为TUS处理构建标准返回结果
                        srt_content = result['srt_content']
                        srt_url = result.get('minio_path', result.get('srt_url'))
                        srt_filename = result.get('srt_filename', f"{video_id}.srt")
                        srt_object_name = result.get('object_name', f"users/{user_id}/projects/{project_id}/subtitles/{srt_filename}")

                        # 更新任务状态
                        self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.GENERATE_SRT, 'message': '字幕生成完成'})

                        # 计算SRT内容的实际字幕条数
                        # 使用标准ASR处理的相同方法：从SRT内容解析字幕段落数
                        srt_lines = srt_content.strip().split('\n')
                        total_segments_count = sum(1 for line in srt_lines if line.strip() and line.isdigit()) if len(srt_content.strip()) >= 10 else 1

                        # 构造处理统计信息，使其与标准ASR处理保持一致
                        processing_stats = {
                            'success_count': 1,
                            'fail_count': 0,
                            'total_files': 1,
                            'tus_processing': {
                                'strategy': 'tus',
                                'srt_content_length': len(srt_content),
                                'processing_time': time.time() - processing_start_time if 'processing_start_time' in locals() else 0,
                                'file_size_info': result.get('file_size_info', {}),
                                'task_id': result.get('task_id')
                            }
                        }

                        # 更新数据库中的任务状态
                        try:
                            with get_sync_db() as db:
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
                                        message="字幕生成完成 (策略: tus)",
                                        output_data={
                                            'srt_filename': srt_filename,
                                            'minio_path': srt_url,
                                            'srt_url': srt_url,  # 确保数据库也有srt_url字段
                                            'object_name': srt_object_name,
                                            'total_segments': total_segments_count,
                                            'processing_stats': processing_stats,
                                            'asr_params': {
                                                'strategy': 'tus',
                                                'model': result.get('asr_params', {}).get('model', asr_model_type),
                                                'processing_time': time.time() - processing_start_time if 'processing_start_time' in locals() else 0
                                            },
                                            'strategy': 'tus',
                                            'task_id': result.get('task_id'),
                                            'srt_content': srt_content,
                                            'file_size_info': result.get('file_size_info', {})
                                        },
                                        stage=ProcessingStage.GENERATE_SRT
                                    )

                                    # 注意：切片/子切片的SRT任务不应该更新原视频的处理状态
                                    # 只有当这是原视频的SRT任务时（不是切片或子切片），才更新视频状态
                                    if not slice_id and not sub_slice_id:
                                        # 这是原视频的SRT任务，可以更新视频记录
                                        video = db.query(Video).filter(Video.id == task.video_id).first()
                                        if video:
                                            video.processing_progress = 100
                                            video.processing_stage = ProcessingStage.GENERATE_SRT.value
                                            video.processing_message = "字幕生成完成 (策略: tus)"
                                            video.processing_completed_at = datetime.utcnow()
                                            print(f"已更新原视频记录: video_id={video.id}")

                                        # 更新processing_status表 - 仅限原视频SRT任务
                                        try:
                                            from app.models.processing_task import ProcessingStatus
                                            processing_status = db.query(ProcessingStatus).filter(
                                                ProcessingStatus.video_id == task.video_id
                                            ).first()
                                            if processing_status:
                                                # 只更新SRT相关状态，不改变整体状态
                                                processing_status.generate_srt_status = ProcessingTaskStatus.SUCCESS
                                                processing_status.generate_srt_progress = 100
                                                print(f"已更新原视频SRT状态(TUS): video_id={task.video_id}")
                                        except Exception as status_error:
                                            print(f"更新processing_status失败: {status_error}")
                                    else:
                                        # 这是切片或子切片的SRT任务，绝对不能更新原视频状态
                                        print(f"TUS切片/子切片SRT任务完成，不更新原视频状态: slice_id={slice_id}, sub_slice_id={sub_slice_id}")
                                        # 确保不会意外影响到原视频的状态记录
                                        try:
                                            from app.models.processing_task import ProcessingStatus
                                            processing_status = db.query(ProcessingStatus).filter(
                                                ProcessingStatus.video_id == task.video_id
                                            ).first()
                                            if processing_status:
                                                # 检查并确保不会修改原视频的SRT状态
                                                print(f"检查原视频processing_status(TUS) - 当前SRT状态: {processing_status.generate_srt_status}")
                                                # 不做任何修改，只记录日志
                                        except Exception as check_error:
                                            print(f"检查原视频状态失败: {check_error}")

                                    # 如果是子切片处理，更新子切片记录
                                    if sub_slice_id:
                                        try:
                                            from app.models import VideoSubSlice
                                            sub_slice_record = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                                            if sub_slice_record:
                                                # 1. 先保存SRT URL
                                                sub_slice_record.srt_url = srt_url
                                                print(f"DEBUG: 设置子切片SRT URL: sub_slice_id={sub_slice_id}, srt_url={srt_url}")

                                                # 2. 验证SRT URL确实有效后再设置状态为completed
                                                if srt_url:
                                                    sub_slice_record.srt_processing_status = "completed"
                                                    print(f"✅ TUS子切片状态已更新为completed: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                                else:
                                                    print(f"⚠️ TUS SRT URL为空，不更新状态: sub_slice_id={sub_slice_id}")
                                                    sub_slice_record.srt_processing_status = "failed"
                                                    sub_slice_record.srt_error_message = "TUS SRT URL保存失败"

                                                print(f"已更新子切片: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                                            else:
                                                print(f"DEBUG: 未找到子切片记录: sub_slice_id={sub_slice_id}")
                                                print(f"未找到子切片记录: sub_slice_id={sub_slice_id}")
                                        except Exception as slice_error:
                                            print(f"更新子切片srt_url失败: {slice_error}")
                                            import traceback
                                            print(f"详细错误信息: {traceback.format_exc()}")

                        except Exception as db_error:
                            print(f"更新数据库任务状态失败: {db_error}")

                        return {
                            'success': True,
                            'strategy': 'tus',
                            'srt_filename': srt_filename,
                            'minio_path': srt_url,
                            'srt_url': srt_url,  # 添加srt_url字段确保兼容性
                            'object_name': srt_object_name,
                            'total_segments': total_segments_count,
                            'processing_stats': processing_stats,
                            'asr_params': {
                                'strategy': 'tus',
                                'model': result.get('asr_params', {}).get('model', asr_model_type),
                                'processing_time': time.time() - processing_start_time if 'processing_start_time' in locals() else 0
                            },
                            'srt_content': srt_content,
                            'project_id': project_id,
                            'user_id': user_id,
                            'file_path': audio_info['audio_path'] if audio_info else None,
                            'processing_info': result
                        }

                    elif 'error' in result and result['error']:
                        # 只有在有明确的错误信息时才认为失败
                        logger.error(f"SRT生成失败: {result['error']}")
                        raise Exception(result['error'])
                    else:
                        # 没有明确的错误，但也没有SRT内容，认为是部分成功
                        logger.warning(f"SRT生成可能不完整，但未明确失败: {result}")
                        # 如果有处理统计信息，仍认为成功
                        if 'processing_stats' in result:
                            logger.info(f"使用处理统计信息判断为成功")
                        else:
                            raise Exception("SRT生成结果不完整，也未提供错误信息")
            
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


