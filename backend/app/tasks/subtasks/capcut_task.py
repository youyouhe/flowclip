from celery import shared_task
import asyncio
import tempfile
import os
import requests
import json
import time
import logging
import subprocess
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

def _get_proxy_url(resource_path: str) -> str:
    """生成资源的签名URL，供CapCut服务器访问"""
    # 使用配置的minio_public_endpoint生成可访问的URL
    from app.services.minio_client import minio_service
    from app.core.config import settings
    import asyncio
    from urllib.parse import urlparse
    
    # 打印当前的配置信息
    print(f"DEBUG: 当前settings.minio_public_endpoint: {settings.minio_public_endpoint}")
    print(f"DEBUG: 当前minio_service.public_client._endpoint_url: {minio_service.public_client._base_url.host}")
    
    # 异步获取签名URL
    async def get_signed_url():
        try:
            print(f"DEBUG: _get_proxy_url 开始处理资源路径: {resource_path}")
            print(f"DEBUG: 当前minio_public_endpoint配置: {settings.minio_public_endpoint}")
            # 首先尝试使用minio_service的公共客户端生成URL
            # 这会使用配置的minio_public_endpoint
            url = await minio_service.get_file_url(resource_path, expiry=3600)  # 1小时有效期
            if url:
                print(f"DEBUG: 公共客户端生成的URL: {url}")
                return url
        except Exception as e:
            print(f"使用公共客户端生成签名URL失败: {e}")
        
        try:
            # 如果公共客户端失败，使用内部客户端生成URL，然后替换端点
            internal_url = minio_service.internal_client.get_presigned_url(
                method='GET',
                bucket_name=settings.minio_bucket_name,
                object_name=resource_path,
                expires=3600  # 1小时有效期
            )
            print(f"DEBUG: 内部客户端生成的URL: {internal_url}")
            
            # 如果配置了minio_public_endpoint，则替换URL中的端点
            if settings.minio_public_endpoint:
                # 解析内部URL，提取路径和查询参数
                parsed_internal = urlparse(internal_url)
                # 构造新的URL，使用公共端点
                public_endpoint = settings.minio_public_endpoint
                if not public_endpoint.startswith(('http://', 'https://')):
                    public_endpoint = f"http://{public_endpoint}"
                
                # 移除末尾的斜杠
                public_endpoint = public_endpoint.rstrip('/')
                
                # 构造最终URL
                final_url = f"{public_endpoint}{parsed_internal.path}"
                if parsed_internal.query:
                    final_url = f"{final_url}?{parsed_internal.query}"
                
                print(f"DEBUG: 将内部URL {internal_url} 替换为公共URL {final_url}")
                return final_url
            else:
                # 如果没有配置公共端点，直接返回内部URL
                return internal_url
        except Exception as e:
            print(f"使用内部客户端生成签名URL失败: {e}")
        
        # 最后的备用方案：使用minio_public_endpoint构造URL
        if settings.minio_public_endpoint:
            endpoint = settings.minio_public_endpoint
            print(f"DEBUG: 使用备用方案，当前endpoint: {endpoint}")
            if not endpoint.startswith(('http://', 'https://')):
                endpoint = f"http://{endpoint}"
            endpoint = endpoint.rstrip('/')
            final_url = f"{endpoint}/{settings.minio_bucket_name}/{resource_path}"
            print(f"DEBUG: 备用方案生成的URL: {final_url}")
            return final_url
        else:
            # 如果完全没有配置，使用默认值
            return f"http://localhost:9000/{settings.minio_bucket_name}/{resource_path}"
    
    # 在事件循环中运行异步函数
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 如果没有运行中的事件循环，创建一个新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(get_signed_url())
    print(f"DEBUG: _get_proxy_url 最终返回的URL: {result}")
    return result

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
                
                # 使用_get_proxy_url函数生成可访问的URL
                proxy_url = _get_proxy_url(resource.file_path)
                print(f"DEBUG: 生成的资源代理URL: {proxy_url}")
                return proxy_url
        except Exception as e:
            print(f"从数据库获取资源失败: {e}")
            return None
    
    try:
        celery_task_id = self.request.id
        if not celery_task_id:
            celery_task_id = "unknown"
            
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
            
            # 添加调试信息
            print(f"DEBUG: 开始CapCut导出任务 - 切片ID: {slice_id}, 类型: {slice_obj.type}")
            
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
                        
                        # 添加电视彩虹屏特效 (从水波纹结束后持续到子切片结束)
                        print(f"DEBUG: 添加电视彩虹屏特效 - 时间轴起始: {current_time + 3}秒, 时间轴结束: {current_time + sub_slice.duration}秒")
                        rainbow_effect_result = asyncio.run(capcut_service.add_effect(
                            draft_id=draft_id,
                            effect_type="电视彩虹屏",
                            start=current_time + 3,
                            end=current_time + sub_slice.duration,
                            track_name=f"rainbow_effect_track_{i+1}",
                            max_retries=3
                        ))
                        
                        # 获取水波纹音频资源
                        audio_url = _get_resource_by_tag_from_db("水波纹", "audio")
                        print(f"DEBUG: 从数据库获取的水波纹音频URL: {audio_url}")
                        if audio_url:
                            # 如果是从数据库获取的URL，提取资源路径并生成代理URL
                            from urllib.parse import urlparse
                            parsed_url = urlparse(audio_url)
                            resource_path = parsed_url.path.lstrip('/')
                            # 移除bucket名称前缀
                            if resource_path.startswith(settings.minio_bucket_name + '/'):
                                resource_path = resource_path[len(settings.minio_bucket_name) + 1:]
                            proxy_audio_url = _get_proxy_url(resource_path)
                            print(f"DEBUG: 处理后的水波纹音频代理URL: {proxy_audio_url}")
                        else:
                            # 如果获取失败，使用默认音频
                            proxy_audio_url = "http://tmpfiles.org/dl/9816523/mixkit-liquid-bubble-3000.wav"
                            print(f"DEBUG: 使用默认水波纹音频URL: {proxy_audio_url}")
                        
                        print(f"DEBUG: 添加水波纹音频 - URL: {proxy_audio_url}, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + 3}秒")
                        audio_result = asyncio.run(capcut_service.add_audio(
                            draft_id=draft_id,
                            audio_url=proxy_audio_url,
                            start=0,
                            end=3,
                            track_name=f"bubble_audio_track_{i+1}",
                            volume=0.5,
                            target_start=current_time,
                            max_retries=3
                        ))
                        
                        # 添加子切片标题文本（与水波纹特效同步显示，不带年月信息）
                        if sub_slice.cover_title:
                            print(f"DEBUG: 添加子切片标题 - 文本: {sub_slice.cover_title}, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + 3}秒")
                            text_result = asyncio.run(capcut_service.add_text(
                                draft_id=draft_id,
                                text=sub_slice.cover_title,
                                start=current_time,
                                end=current_time + 3,
                                font="挥墨体",
                                font_color="#ffde00",
                                font_size=8.0,
                                track_name=f"title_track_{i+1}",
                                transform_x=0.0,
                                transform_y=0.0,  # 标题位置在屏幕中心
                                font_alpha=1.0,
                                border_alpha=1.0,
                                border_color="#000000",
                                border_width=15.0,
                                width=1080,
                                height=1920,
                                intro_animation="收拢",
                                max_retries=3
                            ))
                        
                        # 添加视频
                        print(f"DEBUG: 子切片文件路径: {sub_slice.sliced_file_path}")
                        proxy_video_url = _get_proxy_url(sub_slice.sliced_file_path)
                        print(f"DEBUG: 添加子切片视频 - URL: {proxy_video_url}, 长度: {sub_slice.duration}秒, 时间轴起始: {current_time}秒, 时间轴结束: {current_time + sub_slice.duration}秒")
                        video_result = asyncio.run(capcut_service.add_video(
                            draft_id=draft_id,
                            video_url=proxy_video_url,
                            start=0,
                            end=sub_slice.duration,
                            track_name=f"video_track_{i+1}",
                            target_start=current_time,
                            max_retries=3
                        ))
                        
                        # 添加子切片字幕（如果有）
                        print(f"DEBUG: 检查子切片 {sub_slice.id} 是否需要添加字幕 - SRT URL: {sub_slice.srt_url}")
                        if sub_slice.srt_url:
                            try:
                                # 从MinIO读取SRT文件内容并处理编码
                                print(f"DEBUG: 从MinIO读取子切片 {sub_slice.id} 的SRT文件内容")
                                response = minio_service.internal_client.get_object(settings.minio_bucket_name, sub_slice.srt_url)
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
                                
                                print(f"DEBUG: 成功读取子切片 {sub_slice.id} 的SRT内容，长度: {len(srt_content)}")
                                
                                if srt_content and srt_content.strip():
                                    print(f"DEBUG: 添加子切片字幕 - 内容长度: {len(srt_content)}, 时间偏移: {current_time}秒")
                                    subtitle_result = asyncio.run(capcut_service.add_subtitle(
                                        draft_id=draft_id,
                                        srt_path=srt_content,  # 传递实际内容而不是URL
                                        time_offset=current_time,
                                        font="HarmonyOS_Sans_SC_Regular",
                                        font_size=8.0,
                                        font_color="#ffde00",
                                        bold=False,
                                        italic=False,
                                        underline=False,
                                        vertical=False,
                                        alpha=1.0,
                                        border_alpha=1.0,
                                        border_color="#000000",
                                        border_width=15.0,
                                        background_color="#000000",
                                        background_style=0,
                                        background_alpha=0.0,
                                        transform_x=0.0,
                                        transform_y=-0.8,
                                        scale_x=1.0,
                                        scale_y=1.0,
                                        rotation=0.0,
                                        track_name=f"subtitle_{sub_slice.id}",
                                        width=1080,
                                        height=1920,
                                        max_retries=3
                                    ))
                                    print(f"DEBUG: 子切片 {sub_slice.id} 字幕添加结果: {subtitle_result}")
                                    if subtitle_result and subtitle_result.get("success"):
                                        print(f"DEBUG: 子切片 {sub_slice.id} 字幕成功添加到草稿 {draft_id}")
                                    else:
                                        print(f"DEBUG: 子切片 {sub_slice.id} 字幕添加失败: {subtitle_result.get('error') if subtitle_result else '未知错误'}")
                                else:
                                    print(f"DEBUG: 子切片 {sub_slice.id} SRT内容为空")
                            except Exception as e:
                                print(f"DEBUG: 读取或添加子切片 {sub_slice.id} 字幕失败: {str(e)}")
                        else:
                            print(f"DEBUG: 子切片 {sub_slice.id} 没有SRT URL，跳过字幕添加")
                        
                        current_time += sub_slice.duration
                    except Exception as e:
                        print(f"处理子切片 {i+1} 失败: {str(e)}")
                        # 继续处理其他子切片
                        continue
            else:
                # 对于full切片，添加水波纹特效和音效，然后添加整个切片视频
                try:
                    progress = 45
                    message = "处理完整切片"
                    _update_task_status(celery_task_id, ProcessingTaskStatus.RUNNING, progress, message)
                    self.update_state(state='PROGRESS', meta={'progress': progress, 'stage': ProcessingStage.CAPCUT_EXPORT, 'message': message})
                    
                    # 添加水波纹特效 (前3秒)
                    print(f"DEBUG: 添加水波纹特效 - 时间轴起始: 0秒, 时间轴结束: 3秒")
                    effect_result = asyncio.run(capcut_service.add_effect(
                        draft_id=draft_id,
                        effect_type="水波纹",
                        start=0,
                        end=3,
                        track_name="effect_track_main",
                        max_retries=3
                    ))
                    
                    # 添加电视彩虹屏特效 (从水波纹结束后持续到视频结束)
                    print(f"DEBUG: 添加电视彩虹屏特效 - 时间轴起始: 3秒, 时间轴结束: {slice_obj.duration}秒")
                    rainbow_effect_result = asyncio.run(capcut_service.add_effect(
                        draft_id=draft_id,
                        effect_type="电视彩虹屏",
                        start=3,
                        end=slice_obj.duration,
                        track_name="rainbow_effect_track_main",
                        max_retries=3
                    ))
                    
                    # 获取水波纹音频资源
                    audio_url = _get_resource_by_tag_from_db("水波纹", "audio")
                    if audio_url:
                        # 如果是从数据库获取的URL，提取资源路径并生成代理URL
                        from urllib.parse import urlparse
                        parsed_url = urlparse(audio_url)
                        resource_path = parsed_url.path.lstrip('/')
                        # 移除bucket名称前缀
                        if resource_path.startswith(settings.minio_bucket_name + '/'):
                            resource_path = resource_path[len(settings.minio_bucket_name) + 1:]
                        proxy_audio_url = _get_proxy_url(resource_path)
                    else:
                        # 如果获取失败，使用默认音频
                        proxy_audio_url = "http://tmpfiles.org/dl/9816523/mixkit-liquid-bubble-3000.wav"
                    
                    print(f"DEBUG: 添加水波纹音频 - URL: {proxy_audio_url}, 时间轴起始: 0秒, 时间轴结束: 3秒")
                    audio_result = asyncio.run(capcut_service.add_audio(
                        draft_id=draft_id,
                        audio_url=proxy_audio_url,
                        start=0,
                        end=3,
                        track_name="bubble_audio_track_main",
                        volume=0.5,
                        target_start=0,
                        max_retries=3
                    ))
                    
                    # 添加完整切片视频
                    print(f"DEBUG: 完整切片文件路径: {slice_obj.sliced_file_path}")
                    proxy_video_url = _get_proxy_url(slice_obj.sliced_file_path)
                    print(f"DEBUG: 添加完整切片视频 - URL: {proxy_video_url}, 长度: {slice_obj.duration}秒, 时间轴起始: 0秒, 时间轴结束: {slice_obj.duration}秒")
                    video_result = asyncio.run(capcut_service.add_video(
                        draft_id=draft_id,
                        video_url=proxy_video_url,
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
            
            # 添加覆盖文本（带年月信息）
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            cover_title_with_date = f"{slice_obj.cover_title}({current_date})"
            print(f"DEBUG: 添加切片覆盖标题 - 文本: {cover_title_with_date}, 时间轴起始: 0秒, 时间轴结束: {current_time}秒")
            text_result = asyncio.run(capcut_service.add_text(
                draft_id=draft_id,
                text=cover_title_with_date,
                start=0,
                end=current_time,
                font="挥墨体",
                font_color="#ffde00",
                font_size=8.0,
                track_name="cover_title_track",
                transform_x=0.0,
                transform_y=0.75,
                font_alpha=1.0,
                border_alpha=1.0,
                border_color="#000000",
                border_width=15.0,
                width=1080,
                height=1920,
                max_retries=3
            ))
            
            # 添加字幕（仅对full切片添加完整视频的字幕，fragment切片已在子切片处理中添加）
            print(f"DEBUG: 检查是否需要添加字幕 - 切片类型: {slice_obj.type}, 切片SRT URL: {slice_obj.srt_url}")
            if slice_obj.type != "fragment":
                print("DEBUG: 切片类型为full，准备添加完整视频字幕")
                # 对于full切片，添加完整视频的字幕
                if slice_obj.srt_url:
                    try:
                        # 从MinIO读取SRT文件内容并处理编码
                        print(f"DEBUG: 从MinIO读取完整切片的SRT文件内容")
                        response = minio_service.internal_client.get_object(settings.minio_bucket_name, slice_obj.srt_url)
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
                        
                        print(f"DEBUG: 成功读取完整切片的SRT内容，长度: {len(srt_content)}")
                        
                        if srt_content and srt_content.strip():
                            print(f"DEBUG: 添加完整切片字幕 - 内容长度: {len(srt_content)}")
                            subtitle_result = asyncio.run(capcut_service.add_subtitle(
                                draft_id=draft_id,
                                srt_path=srt_content,  # 传递实际内容而不是URL
                                font="HarmonyOS_Sans_SC_Regular",
                                font_size=8.0,
                                font_color="#ffde00",
                                bold=False,
                                italic=False,
                                underline=False,
                                vertical=False,
                                alpha=1.0,
                                border_alpha=1.0,
                                border_color="#000000",
                                border_width=15.0,
                                background_color="#000000",
                                background_style=0,
                                background_alpha=0.0,
                                transform_x=0.0,
                                transform_y=-0.8,
                                scale_x=1.0,
                                scale_y=1.0,
                                rotation=0.0,
                                track_name="subtitle",
                                width=1080,
                                height=1920,
                                max_retries=3
                            ))
                            print(f"DEBUG: 字幕添加结果: {subtitle_result}")
                            if subtitle_result and subtitle_result.get("success"):
                                print(f"DEBUG: 字幕成功添加到草稿 {draft_id}")
                            else:
                                print(f"DEBUG: 字幕添加失败: {subtitle_result.get('error') if subtitle_result else '未知错误'}")
                        else:
                            print(f"DEBUG: 完整切片SRT内容为空")
                    except Exception as e:
                        print(f"DEBUG: 读取或添加完整切片字幕失败: {str(e)}")
                else:
                    print("DEBUG: 没有可用的切片SRT文件，跳过字幕添加")
            else:
                print("DEBUG: 切片类型为fragment，字幕将在子切片处理中添加")
            
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