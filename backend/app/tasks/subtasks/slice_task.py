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
from app.services.video_slicing_service import video_slicing_service
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.core.database import get_sync_db
from app.core.config import settings
from app.models import Video, VideoSlice, VideoSubSlice, LLMAnalysis, ProcessingTask

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='app.tasks.video_tasks.process_video_slices')
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
        """同步Processing Clips"""
        try:
            
            def _submit_processing_tasks(video_slice: VideoSlice, user_id: int, project_id: int):
                """提交切片的音频提取和SRT任务"""
                try:
                    from app.tasks.subtasks.audio_task import extract_audio
                    from app.tasks.subtasks.slice_audio_task import extract_slice_audio
                    from app.tasks.subtasks.sub_slice_audio_task import extract_sub_slice_audio
                    from app.tasks.subtasks.srt_task import generate_srt
                    
                    if video_slice.type == "full":
                        # Full类型切片：直接提交音频和SRT任务
                        print(f"提交Full类型切片处理任务: slice_id={video_slice.id}")
                        
                        # 提交音频提取任务
                        audio_task = extract_slice_audio.delay(
                            video_id=str(video_slice.video_id),
                            project_id=project_id,
                            user_id=user_id,
                            video_minio_path=video_slice.sliced_file_path,
                            slice_id=video_slice.id,
                            create_processing_task=True,
                            trigger_srt_after_audio=True  # 启用SRT自动触发
                        )
                        video_slice.audio_processing_status = "processing"
                        video_slice.audio_task_id = audio_task.id
                        print(f"音频提取任务已提交: task_id={audio_task.id}")
                        print(f"Full类型切片将等待Audio Extraction Completed后自动触发SRT生成")
                        
                    elif video_slice.type == "fragment":
                        # Fragment类型切片：只为所有子切片提交音频提取任务
                        # SRT任务将在Audio Extraction Completed后触发
                        print(f"提交Fragment类型切片处理任务: slice_id={video_slice.id}, sub_slices_count={len(video_slice.sub_slices)}")
                        
                        for i, sub_slice in enumerate(video_slice.sub_slices):
                            try:
                                print(f"处理子切片 {i+1}/{len(video_slice.sub_slices)}: sub_slice_id={sub_slice.id}")
                                
                                # 提交子切片音频提取任务
                                # Audio Extraction Completed后将自动触发SRT任务
                                sub_audio_task = extract_sub_slice_audio.delay(
                                    video_id=str(video_slice.video_id),
                                    project_id=project_id,
                                    user_id=user_id,
                                    video_minio_path=sub_slice.sliced_file_path,
                                    sub_slice_id=sub_slice.id,
                                    create_processing_task=True,
                                    trigger_srt_after_audio=True  # 启用SRT自动触发
                                )
                                sub_slice.audio_processing_status = "processing"
                                sub_slice.audio_task_id = sub_audio_task.id
                                print(f"子切片音频提取任务已提交: sub_slice_id={sub_slice.id}, task_id={sub_audio_task.id}")
                                print(f"子切片Audio Extraction Completed后将自动触发SRT生成")
                                
                            except Exception as e:
                                print(f"提交子切片 {sub_slice.id} 处理任务失败: {str(e)}")
                                continue
                    
                    print(f"切片 {video_slice.id} 的处理任务提交完成")
                    
                except Exception as e:
                    print(f"提交切片处理任务时发生错误: {str(e)}")
                    import traceback
                    print(f"详细错误: {traceback.format_exc()}")
                    raise Exception(f"提交处理任务失败: {str(e)}")

            def _determine_slice_type(sub_slices_data, parent_start, parent_end):
                """
                判断切片类型：如果子切片在时间轴上连续则为full，否则为fragment
                """
                print(f"切片类型判断输入: parent_start={parent_start}, parent_end={parent_end}")
                print(f"子切片数据: {sub_slices_data}")
                
                if not sub_slices_data:
                    return "fragment"  # 没有子切片则认为是fragment
                
                # 按开始时间排序
                sorted_sub_slices = sorted(sub_slices_data, key=lambda x: x['start_time'])
                print(f"排序后的子切片: {sorted_sub_slices}")
                
                # 检查是否连续
                is_continuous = True
                previous_end = parent_start
                print(f"初始previous_end: {previous_end}")
                
                for sub_slice in sorted_sub_slices:
                    # 检查当前子切片的开始时间是否与前一个子切片的结束时间连续
                    # 正常情况下应该是相等的（连续），允许3秒以内的正向间隙，但不允许重叠（负值）
                    time_diff = sub_slice['start_time'] - previous_end
                    print(f"检查连续性: previous_end={previous_end}, sub_slice_start={sub_slice['start_time']}, time_diff={time_diff}")
                    if time_diff < -0.1 or time_diff > 3:
                        print(f"时间不连续: previous_end={previous_end}, sub_slice_start={sub_slice['start_time']}, time_diff={time_diff}")
                        is_continuous = False
                        break
                    previous_end = sub_slice['end_time']
                    print(f"更新previous_end为: {previous_end}")
                
                # 检查结尾是否匹配父切片的结束时间（允许3秒以内的误差）
                end_diff = abs(parent_end - previous_end)
                print(f"检查结尾匹配: parent_end={parent_end}, previous_end={previous_end}, end_diff={end_diff}")
                if end_diff > 3:
                    print(f"结尾不匹配: parent_end={parent_end}, previous_end={previous_end}, end_diff={end_diff}")
                    is_continuous = False
                
                slice_type = "full" if is_continuous else "fragment"
                print(f"切片类型判断: sub_slices_count={len(sub_slices_data)}, is_continuous={is_continuous}, type={slice_type}")
                return slice_type
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
                            message = f"Processing Clips {i+1}/{total_slices}: {slice_item.get('cover_title', 'N/A')}"
                            
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
                                description=slice_item.get('desc', ''),
                                tags=slice_item.get('tags', []),
                                start_time=start_time,
                                end_time=end_time,
                                duration=slice_result.get('duration', end_time - start_time),
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
                            sub_slices_data = []
                            for j, sub_slice in enumerate(slice_item.get('chapters', [])):
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
                                        duration=sub_result.get('duration', sub_end - sub_start),
                                        sliced_filename=sub_filename,
                                        sliced_file_path=sub_result['file_path'],
                                        file_size=sub_result['file_size'],
                                        status="completed"
                                    )
                                    
                                    db.add(video_sub_slice)
                                    sub_slices_data.append({
                                        'start_time': sub_start,
                                        'end_time': sub_end
                                    })
                                    
                                except Exception as e:
                                    print(f"处理子切片失败: {str(e)}")
                            
                            db.commit()
                            
                            # 判断切片类型（full 或 fragment）
                            slice_type = _determine_slice_type(sub_slices_data, start_time, end_time)
                            video_slice.type = slice_type
                            print(f"设置切片类型: slice_id={video_slice.id}, type={slice_type}")
                            
                            # 重新加载video_slice及其子切片以确保关联数据完整
                            db.commit()  # 先提交确保类型被保存
                            db.refresh(video_slice)
                            print(f"刷新后切片类型: slice_id={video_slice.id}, type={video_slice.type}")
                            
                            # 提交音频提取和SRT任务
                            try:
                                _submit_processing_tasks(video_slice, user_id, project_id)
                            except Exception as e:
                                print(f"提交处理任务失败: {str(e)}")
                                # 不影响切片创建，只记录错误
                            
                            db.commit()
                            processed_slices += 1
                            
                        except Exception as e:
                            print(f"Processing Clips失败: {str(e)}")
                            continue
                    
                    # 更新分析状态
                    analysis.is_applied = True
                    analysis.status = "applied"
                    db.commit()
                    
                    _update_task_status(self.request.id, ProcessingTaskStatus.SUCCESS, 100, f"Video Clip Processing Completed，成功处理 {processed_slices}/{total_slices} 个切片")
                    
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
            print(f"Processing Clips任务失败: {str(e)}")
            print(f"详细错误信息: {error_details}")
            raise Exception(f"视频切片任务失败: {str(e)}")
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "Start Processing Video Clips")
        self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.SLICE_VIDEO, 'message': 'Start Processing Video Clips'})
        
        # 运行同步处理
        result = _process_slices()
        _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "Video Clip Processing Completed")
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