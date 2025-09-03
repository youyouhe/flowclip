#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut导出任务模块
包含处理导出到CapCut的Celery任务
基于video_tasks.py中的稳定版本，增加了SRT和子切片文本功能
"""

import asyncio
import logging
import json
import time
from celery import shared_task
from typing import Dict, Any
from app.services.capcut_service import capcut_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingStage, ProcessingTaskStatus
from app.core.database import get_sync_db
from app.models.processing_task import ProcessingTask
from app.models.video_slice import VideoSlice, VideoSubSlice
from app.models.transcript import Transcript
from app.models.resource import Resource, ResourceTag
from app.models.video import Video
from app.models.project import Project
# 延迟导入minio_service以避免循环依赖
from app.core.config import settings
from app.services.minio_client import minio_service
from sqlalchemy import select

# 创建logger
logger = logging.getLogger(__name__)


@shared_task(bind=True)
def export_slice_to_capcut(self, slice_id: int, draft_folder: str, user_id: int = None) -> Dict[str, Any]:
    """导出切片到CapCut的Celery任务 - 基于稳定版本并增强新功能"""
    
    def _update_task_status(celery_task_id: str, status: str, progress: float, message: str = None, error: str = None):
        """更新任务状态 - 同步版本"""
        try:
            with get_sync_db() as db:
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
                            'stage': ProcessingStage.CAPCUT_EXPORT.value
                        }
                    )
                else:
                    # 如果记录不存在，只在日志中记录，不报错
                    print(f"Info: Processing task record not found for celery_task_id: {celery_task_id}")
        except Exception as e:
            print(f"Error updating task status: {e}")
    
    def _get_resource_by_tag_from_db(tag_name: str, resource_type: str = "audio") -> str:
        """根据标签从数据库获取资源URL"""
        try:
            with get_sync_db() as db:
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
                
                # 返回资源URL - 使用外部访问地址
                return f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{resource.file_path}"
        except Exception as e:
            print(f"从数据库获取资源失败: {e}")
            return None


    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
        _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 5, "开始CapCut导出任务")
        self.update_state(state='PROGRESS', meta={'progress': 5, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': '开始CapCut导出任务'})
        
        with get_sync_db() as db:
            # 获取切片信息
            slice_obj = db.get(VideoSlice, slice_id)
            if not slice_obj:
                raise Exception("切片不存在")
            
            # 更新切片的CapCut状态为处理中
            slice_obj.capcut_status = "processing"
            slice_obj.capcut_task_id = celery_task_id
            slice_obj.capcut_error_message = None
            db.commit()
            
            # 获取子切片并按开始时间排序
            sub_slices_result = db.execute(
                select(VideoSubSlice).where(VideoSubSlice.slice_id == slice_id).order_by(VideoSubSlice.start_time)
            )
            sub_slices = sub_slices_result.scalars().all()
            
            # 获取视频的转录信息（字幕）
            transcript_result = db.execute(
                select(Transcript).where(Transcript.video_id == slice_obj.video_id)
            )
            transcript = transcript_result.scalar_one_or_none()
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 10, "创建CapCut草稿")
            self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': '创建CapCut草稿'})
            
            # 创建草稿
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                draft_result = loop.run_until_complete(capcut_service.create_draft(max_retries=3))
                loop.close()
                
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
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 20, "处理子切片")
            self.update_state(state='PROGRESS', meta={'progress': 20, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': '处理子切片'})
            
            # 获取视频和项目信息用于SRT处理
            video_result = db.execute(select(Video).where(Video.id == slice_obj.video_id))
            video_obj = video_result.scalar_one()
            
            project_result = db.execute(select(Project).where(Project.id == video_obj.project_id))
            project_obj = project_result.scalar_one()
            
            # 按顺序处理子切片
            current_time = 0
            total_sub_slices = len(sub_slices)
            
            for i, sub_slice in enumerate(sub_slices):
                try:
                    progress = 20 + (i / total_sub_slices) * 50
                    message = f"处理子切片 {i+1}/{total_sub_slices}"
                    _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, progress, message)
                    self.update_state(state='PROGRESS', meta={'progress': progress, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': message})
                    
                    # 添加水波纹特效 (前3秒)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    effect_result = loop.run_until_complete(capcut_service.add_effect(
                        draft_id=draft_id,
                        effect_type="水波纹",
                        start=current_time,
                        end=current_time + 3,
                        track_name=f"effect_track_{i+1}",
                        max_retries=3
                    ))
                    loop.close()
                    
                    # 获取水波纹音频资源
                    audio_url = _get_resource_by_tag_from_db("水波纹", "audio")
                    if not audio_url:
                        # 如果获取失败，使用默认音频
                        audio_url = "http://tmpfiles.org/dl/9816523/mixkit-liquid-bubble-3000.wav"
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    audio_result = loop.run_until_complete(capcut_service.add_audio(
                        draft_id=draft_id,
                        audio_url=audio_url,
                        start=0,
                        end=3,
                        track_name=f"bubble_audio_track_{i+1}",
                        volume=0.5,
                        target_start=current_time,
                        max_retries=3
                    ))
                    loop.close()
                    
                    # 添加视频
                    video_url = f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/{sub_slice.sliced_file_path}"
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    video_result = loop.run_until_complete(capcut_service.add_video(
                        draft_id=draft_id,
                        video_url=video_url,
                        start=0,
                        end=sub_slice.duration,
                        track_name=f"video_track_{i+1}",
                        target_start=current_time,
                        max_retries=3
                    ))
                    loop.close()
                    
                    # 添加子切片标题文本（与特效同步开始，持续2秒）
                    if sub_slice.cover_title:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        text_result = loop.run_until_complete(capcut_service.add_text(
                            draft_id=draft_id,
                            text=sub_slice.cover_title,
                            start=current_time,  # 与特效同时开始
                            end=current_time + 2,  # 持续2秒
                            font="挥墨体",
                            font_color="#ffde00",
                            font_size=12.0,
                            track_name=f"subslice_title_{sub_slice.id}",
                            transform_x=0.0,
                            transform_y=0.0,  # 画布中心位置
                            font_alpha=1.0,
                            border_alpha=1.0,
                            border_color="#000000",
                            border_width=15.0,
                            width=1080,
                            height=1920,
                            max_retries=3
                        ))
                        loop.close()
                        
                        if text_result.get("success"):
                            print(f"子切片 {sub_slice.id} 标题添加成功")
                        else:
                            print(f"子切片 {sub_slice.id} 标题添加失败: {text_result.get('error')}")
                    
                    # 添加子切片SRT字幕（如果有）
                    if sub_slice.srt_processing_status == "completed" and sub_slice.srt_url:
                        try:
                            print(f"子切片 {sub_slice.id} SRT处理状态: {sub_slice.srt_processing_status}")
                            print(f"SRT URL: {sub_slice.srt_url}")
                            
                            # 从srt_url中提取文件路径（类似于视频URL的处理方式）
                            srt_path = sub_slice.srt_url
                            if settings.minio_public_endpoint in srt_path:
                                # 移除URL前缀，只保留文件路径
                                srt_path = srt_path.replace(f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/", "")
                            
                            print(f"提取的SRT文件路径: {srt_path}")
                            
                            # 直接使用数据库中的路径获取文件内容
                            response = minio_service.internal_client.get_object(settings.minio_bucket_name, srt_path)
                            content_bytes = response.read()
                            response.close()
                            response.release_conn()
                            
                            # 尝试多种编码解码，优先处理BOM
                            srt_content = None
                            try:
                                # 优先使用utf-8-sig，它会自动处理BOM
                                srt_content = content_bytes.decode('utf-8-sig')
                            except UnicodeDecodeError:
                                try:
                                    srt_content = content_bytes.decode('utf-8')
                                except UnicodeDecodeError:
                                    try:
                                        srt_content = content_bytes.decode('gbk')
                                    except UnicodeDecodeError:
                                        srt_content = content_bytes.decode('latin-1')
                            
                            # 额外清理：移除可能残留的BOM字符
                            if srt_content:
                                # BOM字符为 '\ufeff'
                                srt_content = srt_content.replace('\ufeff', '')
                                # 同时清理其他可能的不可见字符
                                srt_content = srt_content.strip()
                            
                            print(f"成功读取子切片 {sub_slice.id} 的SRT内容，长度: {len(srt_content)}")
                            
                            if srt_content and srt_content.strip():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                subtitle_response = loop.run_until_complete(capcut_service.add_subtitle(
                                    draft_id=draft_id,
                                    srt_path=srt_content,
                                    time_offset=current_time,  # 使用当前时间轴位置作为偏移
                                    font="HarmonyOS_Sans_SC_Regular",
                                    font_size=8.0,
                                    font_color="#ffde00",
                                    transform_x=0.0,
                                    transform_y=-0.8,
                                    border_alpha=1.0,
                                    border_color="#000000",
                                    border_width=15.0,
                                    width=1080,
                                    height=1920
                                ))
                                loop.close()
                                
                                if subtitle_response.get("success"):
                                    print(f"子切片 {sub_slice.id} 字幕添加成功")
                                else:
                                    print(f"子切片 {sub_slice.id} 字幕添加失败: {subtitle_response.get('error')}")
                            else:
                                print(f"子切片 {sub_slice.id} SRT内容为空")
                                
                        except Exception as e:
                            print(f"添加子切片 {sub_slice.id} 字幕失败: {str(e)}")
                    else:
                        if sub_slice.srt_processing_status != "completed":
                            print(f"子切片 {sub_slice.id} SRT处理状态未完成: {sub_slice.srt_processing_status}")
                        if not sub_slice.srt_url:
                            print(f"子切片 {sub_slice.id} 没有SRT URL")
                    
                    current_time += sub_slice.duration
                except Exception as e:
                    print(f"处理子切片 {i+1} 失败: {str(e)}")
                    # 继续处理其他子切片
                    continue
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 80, "添加文本和字幕")
            self.update_state(state='PROGRESS', meta={'progress': 80, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': '添加文本和字幕'})
            
            # 添加覆盖文本
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            text_result = loop.run_until_complete(capcut_service.add_text(
                draft_id=draft_id,
                text=slice_obj.cover_title,
                start=0,
                end=current_time,
                max_retries=3
            ))
            loop.close()
            
            # 子切片SRT字幕和标题文本已在主循环中添加，这里不需要重复添加
            
            _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, 90, "保存草稿")
            self.update_state(state='PROGRESS', meta={'progress': 90, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': '保存草稿'})
            
            # 保存草稿
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                save_result = loop.run_until_complete(capcut_service.save_draft(
                    draft_id=draft_id,
                    draft_folder=draft_folder,
                    max_retries=3
                ))
                loop.close()
                
                # 解析CapCut服务返回的数据结构
                if save_result.get("success") and save_result.get("output"):
                    draft_url = save_result["output"].get("draft_url")
                    if not draft_url:
                        raise Exception(f"保存草稿失败: 返回数据中缺少draft_url: {save_result}")
                else:
                    raise Exception(f"保存草稿失败: 服务返回错误: {save_result}")
                
                print(f"草稿保存成功: {draft_url}")
                
                # 更新切片的CapCut导出状态
                slice_obj.capcut_draft_url = draft_url
                slice_obj.capcut_status = "completed"
                db.commit()
                
                _update_task_status(celery_task_id, ProcessingTaskStatus.SUCCESS, 100, "CapCut导出完成")
                self.update_state(state='SUCCESS', meta={'progress': 100, 'stage': ProcessingStage.CAPCUT_EXPORT.value, 'message': 'CapCut导出完成'})
                
                return {
                    "success": True,
                    "message": "导出成功",
                    "draft_url": save_result.get("draft_url"),
                    "slice_id": slice_id
                }
            except Exception as e:
                print(f"保存草稿失败: {e}")
                raise Exception(f"保存草稿失败: {e}")
            
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_details = traceback.format_exc()
        print(f"CapCut导出任务执行失败: {error_msg}")
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