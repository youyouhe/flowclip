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
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.core.database import get_sync_db
from app.core.config import settings
from app.models import VideoSlice, VideoSubSlice, Transcript, ProcessingTask, Resource, ResourceTag

# 创建logger
logger = logging.getLogger(__name__)

@shared_task(bind=True, name='app.tasks.video_tasks.export_slice_to_capcut')
def export_slice_to_capcut(self, slice_id: int, draft_folder: str, user_id: int = None) -> Dict[str, Any]:
    """导出切片到CapCut的Celery任务"""
    
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
                            'stage': ProcessingStage.CAPCUT_EXPORT
                        }
                    )
                else:
                    # 如果记录不存在，只在日志中记录，不报错
                    print(f"Info: Processing task record not found for celery_task_id: {celery_task_id}")
        except Exception as e:
            print(f"Error updating task status: {e}")
    
    # 在函数内部导入CapCutService以避免循环导入
    from app.services.capcut_service import CapCutService
    capcut_service = CapCutService()
    
    def _get_resource_by_tag_from_db(tag_name: str, resource_type: str = "audio") -> str:
        """根据标签从数据库获取资源URL"""
        try:
            with get_sync_db() as db:
                from sqlalchemy import select
                from app.core.config import settings
                
                # 查询标签
                tag_result = db.execute(
                    select(ResourceTag).where(ResourceTag.name == tag_name, ResourceTag.tag_type == resource_type)
                )
                tag = tag_result.scalar_one_or_none()
                
                if not tag:
                    print(f"标签 '{tag_name}' 未找到")
                    return None
                
                # 查询关联的资源
                resource_result = db.execute(
                    select(Resource).join(Resource.tags).where(
                        ResourceTag.id == tag.id,
                        Resource.file_type == resource_type,
                        Resource.is_active == True
                    ).order_by(Resource.created_at.desc())
                )
                resource = resource_result.scalar_one_or_none()
                
                if not resource:
                    print(f"标签 '{tag_name}' 下未找到资源")
                    return None
                
                # 返回资源URL
                return f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{resource.file_path}"
        except Exception as e:
            print(f"从数据库获取资源失败: {e}")
            return None
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        print(f"DEBUG: 开始CapCut导出任务 - 切片ID: {slice_id}, 类型: {slice_obj.type}")
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 5, "开始CapCut导出任务")
        self.update_state(state='PROGRESS', meta={'progress': 5, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': '开始CapCut导出任务'})
        
        # 初始化CapCut服务
        capcut_service = CapCutService()
        
        with get_sync_db() as db:
            from sqlalchemy import select
            
            # 获取切片信息
            slice_obj = db.get(VideoSlice, slice_id)
            if not slice_obj:
                raise Exception("切片不存在")
            
            # 更新切片的CapCut状态为处理中
            slice_obj.capcut_status = "processing"
            slice_obj.capcut_task_id = celery_task_id
            slice_obj.capcut_error_message = None
            db.commit()
            
            # 获取子切片
            sub_slices_result = db.execute(
                select(VideoSubSlice).where(VideoSubSlice.slice_id == slice_id)
            )
            sub_slices = sub_slices_result.scalars().all()
            
            # 获取视频的转录信息（字幕）
            transcript_result = db.execute(
                select(Transcript).where(Transcript.video_id == slice_obj.video_id)
            )
            transcript = transcript_result.scalar_one_or_none()
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "创建CapCut草稿")
            self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': '创建CapCut草稿'})
            
            # 创建草稿
            try:
                draft_result = asyncio.run(capcut_service.create_draft(max_retries=3))
                
                # 解析CapCut服务返回的数据结构
                if draft_result.get("success") and draft_result.get("output"):
                    draft_id = draft_result["output"].get("draft_id")
                    if not draft_id:
                        raise Exception(f"创建草稿失败: 返回数据中缺少draft_id: {draft_result}")
                else:
                    raise Exception(f"创建草稿失败: 服务返回错误: {draft_result}")
                    
                print(f"草稿创建成功: {draft_id}")
            except Exception as e:
                print(f"创建草稿失败: {e}")
                raise Exception(f"创建草稿失败: {e}")
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 20, "处理视频内容")
            self.update_state(state='PROGRESS', meta={'progress': 20, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': '处理视频内容'})
            
            current_time = 0
            
            # 根据切片类型进行不同的处理
            if slice_obj.type == "fragment":
                # 对于fragment切片，处理所有子切片
                total_sub_slices = len(sub_slices)
                
                for i, sub_slice in enumerate(sub_slices):
                    try:
                        progress = 20 + (i / total_sub_slices) * 50
                        message = f"处理子切片 {i+1}/{total_sub_slices}"
                        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, progress, message)
                        self.update_state(state='PROGRESS', meta={'progress': progress, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': message})
                        
                        # 添加水波纹特效 (前3秒)
                        print(f"DEBUG: 添加水波纹特效 - 时间轴起始: {current_time}秒, 时间轴结束: {current_time + 3}秒")
                        effect_result = asyncio.run(capcut_service.add_effect(
                            draft_id=draft_id,
                            effect_type="水波纹",
                            start=current_time,
                            end=current_time + 3,
                            track_name=f"effect_track_{i+1}",
                            max_retries=3
                        ))
                        
                        # 获取水波纹音频资源
                        audio_url = _get_resource_by_tag_from_db("水波纹", "audio")
                        if not audio_url:
                            # 如果获取失败，使用默认音频
                            audio_url = "http://tmpfiles.org/dl/9816523/mixkit-liquid-bubble-3000.wav"
                        
                        print(f"DEBUG: 添加水波纹音频 - URL: {audio_url}, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + 3}秒")
                        audio_result = asyncio.run(capcut_service.add_audio(
                            draft_id=draft_id,
                            audio_url=audio_url,
                            start=0,
                            end=3,
                            track_name=f"bubble_audio_track_{i+1}",
                            volume=0.5,
                            target_start=current_time,
                            max_retries=3
                        ))
                        
                        # 添加子切片标题文本（与水波纹特效同步显示）
                        if sub_slice.cover_title:
                            print(f"DEBUG: 添加子切片标题 - 文本: {sub_slice.cover_title}, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + 3}秒")
                            text_result = asyncio.run(capcut_service.add_text(
                                draft_id=draft_id,
                                text=sub_slice.cover_title,
                                start=current_time,
                                end=current_time + 3,
                                track_name=f"title_track_{i+1}",
                                transform_y=0.75,  # 标题位置在屏幕上部
                                max_retries=3
                            ))
                        
                        # 添加视频
                        video_url = f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{sub_slice.sliced_file_path}"
                        print(f"DEBUG: 添加子切片视频 - URL: {video_url}, 长度: {sub_slice.duration}秒, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + sub_slice.duration}秒")
                        video_result = asyncio.run(capcut_service.add_video(
                            draft_id=draft_id,
                            video_url=video_url,
                            start=0,
                            end=sub_slice.duration,
                            track_name=f"video_track_{i+1}",
                            target_start=current_time,
                            max_retries=3
                        ))
                        
                        # 添加子切片字幕（如果有）
                        if sub_slice.srt_url:
                            srt_path = f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{sub_slice.srt_url}"
                            print(f"DEBUG: 添加子切片字幕 - URL: {srt_path}, 时间偏移: {current_time}秒")
                            subtitle_result = asyncio.run(capcut_service.add_subtitle(
                                draft_id=draft_id,
                                srt_path=srt_path,
                                time_offset=current_time,
                                max_retries=3
                            ))
                        
                        current_time += sub_slice.duration
                    except Exception as e:
                        print(f"处理子切片 {i+1} 失败: {str(e)}")
                        # 继续处理其他子切片
                        continue
            else:
                # 对于full切片，直接添加整个切片视频，不添加特效和音效
                try:
                    progress = 45
                    message = "处理完整切片"
                    _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, progress, message)
                    self.update_state(state='PROGRESS', meta={'progress': progress, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': message})
                    
                    # 添加完整切片视频
                    video_url = f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{slice_obj.sliced_file_path}"
                    print(f"DEBUG: 添加完整切片视频 - URL: {video_url}, 长度: {slice_obj.duration}秒, 时间轴起始: 0秒, 时间轴结束: {slice_obj.duration}秒")
                    video_result = asyncio.run(capcut_service.add_video(
                        draft_id=draft_id,
                        video_url=video_url,
                        start=0,
                        end=slice_obj.duration,
                        track_name="video_track_main",
                        target_start=0,
                        max_retries=3
                    ))
                    
                    current_time = slice_obj.duration
                except Exception as e:
                    print(f"处理完整切片失败: {str(e)}")
                    raise Exception(f"处理完整切片失败: {str(e)}")
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 80, "添加文本和字幕")
            self.update_state(state='PROGRESS', meta={'progress': 80, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': '添加文本和字幕'})
            
            # 添加覆盖文本
            print(f"DEBUG: 添加切片覆盖标题 - 文本: {slice_obj.cover_title}, 时间轴起始: 0秒, 时间轴结束: {current_time}秒")
            text_result = asyncio.run(capcut_service.add_text(
                draft_id=draft_id,
                text=slice_obj.cover_title,
                start=0,
                end=current_time,
                max_retries=3
            ))
            
            # 添加字幕（仅对full切片添加完整视频的字幕，fragment切片已在子切片处理中添加）
            if slice_obj.type != "fragment":
                # 对于full切片，添加完整视频的字幕
                if transcript and transcript.file_path:
                    srt_path = f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{transcript.file_path}"
                    print(f"DEBUG: 添加完整切片字幕 - URL: {srt_path}")
                    subtitle_result = asyncio.run(capcut_service.add_subtitle(
                        draft_id=draft_id,
                        srt_path=srt_path,
                        max_retries=3
                    ))
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 90, "保存草稿")
            self.update_state(state='PROGRESS', meta={'progress': 90, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': '保存草稿'})
            
            # 保存草稿
            try:
                save_result = asyncio.run(capcut_service.save_draft(
                    draft_id=draft_id,
                    draft_folder=draft_folder,
                    max_retries=3
                ))
                
                # 解析CapCut服务返回的数据结构
                if save_result.get("success") and save_result.get("output"):
                    draft_url = save_result["output"].get("draft_url")
                    # 检查draft_url是否存在且非空
                    if not draft_url or draft_url == "":
                        # 如果draft_url为空，记录警告但不抛出异常
                        print(f"警告: 返回的draft_url为空: {save_result}")
                        draft_url = None
                else:
                    raise Exception(f"保存草稿失败: 服务返回错误: {save_result}")
                
                print(f"草稿保存成功: {draft_url}")
                # 更新切片的CapCut导出状态
                slice_obj.capcut_draft_url = draft_url
                slice_obj.capcut_status = "completed"
                db.commit()
                
                print(f"DEBUG: CapCut导出任务完成 - 切片ID: {slice_id}")
                _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "CapCut导出完成")
                self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': 'CapCut导出完成'})
                
                return {
                    "success": True,
                    "message": "导出成功",
                    "draft_url": draft_url,
                    "slice_id": slice_id
                }
            except Exception as e:
                print(f"保存草稿失败: {e}")
                raise Exception(f"保存草稿失败: {e}")
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_details = traceback.format_exc()
        print(f"DEBUG: CapCut导出任务执行失败 - 切片ID: {slice_id}, 错误: {error_msg}")
        print(f"详细错误栈: {error_details}")
        
        # 更新切片的CapCut导出状态为失败
        try:
            with get_sync_db() as db:
                slice_obj = db.get(VideoSlice, slice_id)
                if slice_obj:
                    slice_obj.capcut_status = "failed"
                    slice_obj.capcut_error_message = error_msg
                    db.commit()
        except Exception as db_error:
            print(f"更新切片失败状态失败: {db_error}")
        
        try:
            _update_task_status(self.request.id, ProcessingTaskStatus.FAILURE, 0, error_msg)
        except Exception as status_error:
            print(f"更新任务状态失败: {status_error}")
        
        raise Exception(error_msg)