from celery import shared_task
from app.core.celery import celery_app  # 确保Celery应用被初始化
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
from app.services.video_slicing_service import video_slicing_service
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.core.database import get_sync_db
from app.core.config import settings
from app.models import Video, VideoSlice, VideoSubSlice, LLMAnalysis, ProcessingTask

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True)
def process_video_slices(self, analysis_id: int, video_id: int, project_id: int, user_id: int, slice_items: list) -> Dict[str, Any]:
    """处理视频切片任务"""
    
    def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
        """更新任务状态 - 同步版本"""
        try:
            with get_sync_db() as db:
                from sqlalchemy import select
                from app.models.processing_task import ProcessingTask
                
                # 检查处理任务记录是否存在
                stmt = select(ProcessingTask).where(ProcessingTask.celery_task_id == celery_task_id)
                result = db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    state_manager = get_state_manager(db)
                    state_manager.update_celery_task_status_sync(
                        celery_task_id=celery_task_id,
                        celery_status=status,
                        meta={
                            'progress': progress,
                            'message': message,
                            'error': error,
                            'stage': ProcessingStage.SLICE_VIDEO
                        }
                    )
                else:
                    # 如果记录不存在，只在日志中记录，不报错
                    print(f"Info: Processing task record not found for celery_task_id: {celery_task_id}")
        except Exception as e:
            print(f"Error updating task status: {e}")
    
    def _process_slices():
        """同步处理切片"""
        try:
            # 获取分析数据和视频信息
            with get_sync_db() as db:
                from sqlalchemy import select
                      
                # 获取分析数据
                stmt = select(LLMAnalysis).where(LLMAnalysis.id == analysis_id)
                result = db.execute(stmt)
                analysis = result.first()
                
                if not analysis:
                    raise Exception("分析数据不存在")
                
                analysis = analysis[0]  # Extract from tuple
                
                # 获取视频信息
                stmt = select(Video).where(Video.id == video_id)
                result = db.execute(stmt)
                video = result.first()
                if video:
                    video = video[0]  # Extract from tuple
                
                if not video:
                    raise Exception("视频不存在")
                
                # 获取原始视频文件
                if not video.file_path:
                    raise Exception("视频文件不存在")
                
                # 下载原始视频到临时文件
                import tempfile
                
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    # 从MinIO下载视频
                    video_data = minio_service.internal_client.get_object(
                        settings.minio_bucket_name,
                        video.file_path
                    )
                    
                    content = video_data.read()
                    temp_file.write(content)
                    temp_file.flush()
                    
                    temp_video_path = temp_file.name
                
                try:
                    total_slices = len(slice_items)
                    processed_slices = 0
                    
                    for i, slice_item in enumerate(slice_items):
                        try:
                            progress = 20 + (i / total_slices) * 70
                            message = f"处理切片 {i+1}/{total_slices}: {slice_item.get('cover_title', 'N/A')}"
                            
                            _update_task_status(self.request.id, ProcessingTaskStatus.RUNNING, progress, message)
                            
                            # 只更新数据库，不发送WebSocket通知
                            # 前端会通过定时查询获取最新状态
                            
                            # 解析时间
                            start_time = video_slicing_service._parse_time_str_sync(slice_item.get('start', '00:00:00,000'))
                            end_time = video_slicing_service._parse_time_str_sync(slice_item.get('end', '00:00:00,000'))
                            
                            if start_time is None or end_time is None:
                                print(f"时间解析失败: {slice_item}")
                                continue
                            
                            # 生成文件名
                            filename = video_slicing_service.generate_filename(
                                slice_item.get('cover_title', 'slice'),
                                i + 1
                            )
                            
                            # 执行视频切割 - 使用同步版本
                            slice_result = video_slicing_service.slice_video_sync(
                                temp_video_path,
                                start_time,
                                end_time,
                                filename,
                                slice_item.get('cover_title', 'slice'),
                                user_id,
                                project_id,
                                video_id
                            )
                            
                            # 创建切片记录
                            video_slice = VideoSlice(
                                video_id=video_id,
                                llm_analysis_id=analysis_id,
                                cover_title=slice_item.get('cover_title', 'slice'),
                                title=slice_item.get('title', 'slice'),
                                description=slice_item.get('description', ''),
                                tags=slice_item.get('tags', []),
                                start_time=start_time,
                                end_time=end_time,
                                duration=end_time - start_time,
                                original_filename=filename,
                                sliced_filename=filename,
                                sliced_file_path=slice_result['file_path'],
                                file_size=slice_result['file_size'],
                                status="completed"
                            )
                            
                            db.add(video_slice)
                            db.commit()
                            db.refresh(video_slice)
                            
                            # 处理子切片
                            for j, sub_slice in enumerate(slice_item.get('subtitles', [])):
                                try:
                                    sub_start = video_slicing_service._parse_time_str_sync(sub_slice.get('start', '00:00:00,000'))
                                    sub_end = video_slicing_service._parse_time_str_sync(sub_slice.get('end', '00:00:00,000'))
                                    
                                    if sub_start is None or sub_end is None:
                                        print(f"子切片时间解析失败: {sub_slice}")
                                        continue
                                    
                                    # 生成子切片文件名
                                    sub_filename = video_slicing_service.generate_filename(
                                        sub_slice.get('cover_title', 'sub_slice'),
                                        j + 1,
                                        is_sub_slice=True
                                    )
                                    
                                    # 执行子切片切割 - 使用同步版本
                                    sub_result = video_slicing_service.slice_video_sync(
                                        temp_video_path,
                                        sub_start,
                                        sub_end,
                                        sub_filename,
                                        sub_slice.get('cover_title', 'sub_slice'),
                                        user_id,
                                        project_id,
                                        video_id
                                    )
                                    
                                    # 创建子切片记录
                                    video_sub_slice = VideoSubSlice(
                                        slice_id=video_slice.id,
                                        cover_title=sub_slice.get('cover_title', 'sub_slice'),
                                        start_time=sub_start,
                                        end_time=sub_end,
                                        duration=sub_end - sub_start,
                                        sliced_filename=sub_filename,
                                        sliced_file_path=sub_result['file_path'],
                                        file_size=sub_result['file_size'],
                                        status="completed"
                                    )
                                    
                                    db.add(video_sub_slice)
                                    
                                except Exception as e:
                                    print(f"处理子切片失败: {str(e)}")
                            
                            db.commit()
                            processed_slices += 1
                            
                        except Exception as e:
                            print(f"处理切片失败: {str(e)}")
                            continue
                    
                    # 更新分析状态
                    analysis.is_applied = True
                    analysis.status = "applied"
                    db.commit()
                    
                    _update_task_status(self.request.id, ProcessingTaskStatus.SUCCESS, 100, f"视频切片处理完成，成功处理 {processed_slices}/{total_slices} 个切片")
                    
                    # 只更新数据库，不发送WebSocket通知
                    # 前端会通过定时查询获取最新状态
                    
                    return {
                        'status': 'completed',
                        'analysis_id': analysis_id,
                        'video_id': video_id,
                        'total_slices': total_slices,
                        'processed_slices': processed_slices,
                        'message': f"成功处理 {processed_slices}/{total_slices} 个切片"
                    }
                    
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_video_path)
                    except:
                        pass
              
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"处理切片任务失败: {str(e)}")
            print(f"详细错误信息: {error_details}")
            raise Exception(f"视频切片任务失败: {str(e)}")
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "开始处理视频切片")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.SLICE_VIDEO, 'message': '开始处理视频切片'})
        
        # 运行同步处理
        result = _process_slices()
        _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "视频切片处理完成")
        return result
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_details = traceback.format_exc()
        print(f"视频切片任务执行失败: {error_msg}")
        print(f"详细错误栈: {error_details}")
        
        try:
            _update_task_status(self.request.id, ProcessingTaskStatus.FAILURE, 0, error_msg)
        except Exception as status_error:
            print(f"更新任务状态失败: {status_error}")
        
        raise Exception(error_msg)