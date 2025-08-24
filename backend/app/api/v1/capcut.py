from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any, Optional
import os
import requests
import json
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator

from app.core.database import get_db
from app.models.video_slice import VideoSlice, VideoSubSlice
from app.models.transcript import Transcript
from app.schemas.video_slice import VideoSlice as VideoSliceSchema
from app.models.video import Video
from app.core.config import settings
from app.models.resource import Resource, ResourceTag
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.models.processing_task import ProcessingTask
# 避免循环导入 - 导入Celery任务对象
from app.tasks.video_tasks import export_slice_to_capcut as celery_export_slice_to_capcut

router = APIRouter(tags=["capcut"])

# CapCut API 服务器地址
CAPCUT_API_BASE_URL = settings.capcut_api_url

# 创建logger
logger = logging.getLogger(__name__)

# 从独立的CapCut服务模块导入
from app.services.capcut_service import CapCutService as CapCutServiceBase

class ExportSliceRequest(BaseModel):
    draft_folder: str
    
    @field_validator('draft_folder')
    @classmethod
    def validate_draft_folder(cls, v):
        if not v or not v.strip():
            raise ValueError('Draft folder path cannot be empty')
        
        # 支持Windows和Unix路径
        cleaned_path = v.strip()
        
        # 检查路径是否为空
        if not cleaned_path:
            raise ValueError('Draft folder path cannot be empty')
        
        # 只检查明显无效的字符（保留冒号和反斜杠以支持Windows路径）
        invalid_chars = ['<', '>', '"', '|', '?', '*']
        if any(char in cleaned_path for char in invalid_chars):
            raise ValueError('Draft folder path contains invalid characters')
        
        # 检查路径是否包含一些基本的路径结构
        # Windows路径 (e.g., C:\path 或 \\server\path)
        # Unix路径 (e.g., /home/user/path 或 ./path)
        if not (
            # Windows路径检查
            (len(cleaned_path) >= 2 and cleaned_path[1] == ':' and cleaned_path[0].isalpha()) or  # 盘符路径
            cleaned_path.startswith('\\\\') or  # 网络路径
            # Unix路径检查
            cleaned_path.startswith('/') or  # 绝对路径
            cleaned_path.startswith('./') or  # 相对路径
            cleaned_path.startswith('../') or  # 父目录路径
            # 纯目录名
            not any(char in cleaned_path for char in ['\\', '/', ':'])  # 纯目录名
        ):
            raise ValueError('Invalid draft folder path format')
        
        return cleaned_path

class CapCutServiceAPI:
    def __init__(self):
        self.base_url = CAPCUT_API_BASE_URL
    
    async def get_resource_by_tag(self, tag_name: str, resource_type: str = "audio") -> Optional[str]:
        """根据标签获取资源URL"""
        try:
            # 调用资源管理API获取资源
            # 这里应该调用实际的资源管理API端点
            # 暂时返回一个默认的音频资源作为示例
            if tag_name == "水波纹":
                # 从global-resources bucket获取资源
                return f"{settings.minio_public_endpoint}/{settings.minio_bucket_name}/global-resources/audio/bubble_sound.wav"
            return None
        except Exception as e:
            print(f"获取资源失败: {e}")
            return None
    
    async def get_resource_by_tag_from_db(self, db: AsyncSession, tag_name: str, resource_type: str = "audio") -> Optional[str]:
        """根据标签从数据库获取资源URL"""
        try:
            # 查询标签
            tag_result = await db.execute(
                select(ResourceTag).where(ResourceTag.name == tag_name, ResourceTag.tag_type == resource_type)
            )
            tag = tag_result.scalar_one_or_none()
            
            if not tag:
                print(f"标签 '{tag_name}' 未找到")
                return None
            
            # 查询关联的资源
            resource_result = await db.execute(
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
    
    async def create_draft(self, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """创建草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试创建草稿 (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/create_draft",
                    json={
                        "width": width,
                        "height": height
                    },
                    timeout=30
                )
                response.raise_for_status()  # 检查HTTP错误
                result = response.json()
                logger.info("草稿创建成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"创建草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise HTTPException(status_code=504, detail="创建草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"创建草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"创建草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"创建草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析草稿响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析草稿响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"创建草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"创建草稿失败: {str(e)}")
    
    async def add_effect(self, draft_id: str, effect_type: str, start: float, end: float, 
                        track_name: str, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加特效"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加特效 '{effect_type}' 到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_effect",
                    json={
                        "draft_id": draft_id,
                        "effect_type": effect_type,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "width": width,
                        "height": height
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"特效 '{effect_type}' 添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加特效超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="添加特效超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加特效连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加特效请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加特效请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析特效响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析特效响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加特效未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加特效失败: {str(e)}")
    
    async def add_audio(self, draft_id: str, audio_url: str, start: float, end: float,
                       track_name: str, volume: float = 0.5, target_start: float = 0,
                       width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加音频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加音频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_audio",
                    json={
                        "draft_id": draft_id,
                        "audio_url": audio_url,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "volume": volume,
                        "target_start": target_start,
                        "width": width,
                        "height": height
                    },
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("音频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加音频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="添加音频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加音频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加音频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加音频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析音频响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析音频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加音频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加音频失败: {str(e)}")
    
    async def add_video(self, draft_id: str, video_url: str, start: float, end: float,
                       track_name: str, width: int = 1080, height: int = 1920,
                       target_start: float = 0, max_retries: int = 3) -> Dict[str, Any]:
        """添加视频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加视频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_video",
                    json={
                        "draft_id": draft_id,
                        "video_url": video_url,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "width": width,
                        "height": height,
                        "target_start": target_start
                    },
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("视频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加视频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="添加视频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加视频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加视频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加视频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析视频响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析视频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加视频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加视频失败: {str(e)}")
    
    async def add_text(self, draft_id: str, text: str, start: float, end: float,
                      font: str = "挥墨体", font_color: str = "#ffde00", font_size: float = 12.0,
                      track_name: str = "text_track_1", transform_x: float = 0,
                      transform_y: float = 0.15, font_alpha: float = 1.0,
                      border_alpha: float = 1.0, border_color: str = "#000000",
                      border_width: float = 15.0, width: int = 1080, height: int = 1920,
                      intro_animation: str = None, intro_duration: float = 0.5,
                      outro_animation: str = None, outro_duration: float = 0.5,
                      max_retries: int = 3) -> Dict[str, Any]:
        """添加文本"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加文本到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                # 构建请求数据
                data = {
                    "draft_id": draft_id,
                    "text": text,
                    "start": start,
                    "end": end,
                    "font": font,
                    "font_color": font_color,
                    "font_size": font_size,
                    "track_name": track_name,
                    "transform_x": transform_x,
                    "transform_y": transform_y,
                    "font_alpha": font_alpha,
                    "border_alpha": border_alpha,
                    "border_color": border_color,
                    "border_width": border_width,
                    "width": width,
                    "height": height
                }
                
                # 添加可选的动画参数
                if intro_animation is not None:
                    data["intro_animation"] = intro_animation
                if intro_duration is not None:
                    data["intro_duration"] = intro_duration
                if outro_animation is not None:
                    data["outro_animation"] = outro_animation
                if outro_duration is not None:
                    data["outro_duration"] = outro_duration
                
                response = requests.post(
                    f"{self.base_url}/add_text",
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info("文本添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加文本超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="添加文本超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加文本连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加文本请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加文本请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析文本响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析文本响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加文本未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加文本失败: {str(e)}")
    
    async def save_draft(self, draft_id: str, draft_folder: str, max_retries: int = 3) -> Dict[str, Any]:
        """保存草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试保存草稿 {draft_id} 到文件夹 {draft_folder} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/save_draft",
                    json={
                        "draft_id": draft_id,
                        "draft_folder": draft_folder
                    },
                    timeout=120
                )
                response.raise_for_status()
                result = response.json()
                logger.info("草稿保存成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"保存草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="保存草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"保存草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"保存草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"保存草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析草稿保存响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析草稿保存响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"保存草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"保存草稿失败: {str(e)}")
    
    async def add_subtitle(self, draft_id: str, srt_path: str, font: str = "文轩体", 
                          font_size: float = 8.0, font_color: str = "#ffde00",
                          transform_x: float = 0, transform_y: float = -0.75,
                          border_alpha: float = 1.0, border_color: str = "#000000",
                          border_width: float = 15.0, width: int = 1080, height: int = 1920,
                          max_retries: int = 3) -> Dict[str, Any]:
        """添加字幕"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加字幕到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_subtitle",
                    json={
                        "draft_id": draft_id,
                        "srt": srt_path,
                        "font": font,
                        "font_size": font_size,
                        "font_color": font_color,
                        "transform_x": transform_x,
                        "transform_y": transform_y,
                        "border_alpha": border_alpha,
                        "border_color": border_color,
                        "border_width": border_width,
                        "width": width,
                        "height": height
                    },
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("字幕添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加字幕超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=504, detail="添加字幕超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加字幕连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=503, detail=f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加字幕请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加字幕请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析字幕响应JSON失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"解析字幕响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加字幕未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise HTTPException(status_code=500, detail=f"添加字幕失败: {str(e)}")

capcut_service = CapCutServiceAPI()

@router.post("/export-slice/{slice_id}")
async def export_slice_to_capcut(
    slice_id: int,
    request: ExportSliceRequest,
    db: AsyncSession = Depends(get_db)
):
    """导出切片到CapCut (异步Celery任务)"""
    # 添加详细的调试日志
    logger.info(f"收到CapCut导出请求 - slice_id: {slice_id}, request: {request}")
    
    # Validate slice_id
    if slice_id <= 0:
        logger.error(f"Invalid slice_id: {slice_id}")
        raise HTTPException(status_code=422, detail=f"Invalid slice ID: {slice_id}")
    
    try:
        # 获取切片信息
        slice_obj = await db.get(VideoSlice, slice_id)
        if not slice_obj:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        # 创建处理任务记录
        processing_task = ProcessingTask(
            video_id=slice_obj.video_id,
            task_type=ProcessingTaskType.CAPCUT_EXPORT,
            task_name="CapCut导出",
            status=ProcessingTaskStatus.PENDING,
            stage=ProcessingStage.CAPCUT_EXPORT,
            input_data={
                "slice_id": slice_id,
                "draft_folder": request.draft_folder
            }
        )
        db.add(processing_task)
        await db.commit()
        await db.refresh(processing_task)
        
        # 触发Celery任务
        celery_task = celery_export_slice_to_capcut.delay(
            slice_id=slice_id,
            draft_folder=request.draft_folder
        )
        
        # 更新处理任务记录的Celery任务ID
        processing_task.celery_task_id = celery_task.id
        await db.commit()
        
        return {
            "success": True,
            "message": "CapCut导出任务已启动",
            "task_id": celery_task.id,
            "processing_task_id": processing_task.id
        }
        
    except HTTPException as he:
        # 重新抛出HTTP异常，但先记录日志
        logger.error(f"CapCut导出HTTP异常: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        # 记录详细错误信息
        logger.error(f"CapCut导出任务启动失败 - 异常类型: {type(e).__name__}")
        logger.error(f"CapCut导出任务启动失败 - 异常信息: {str(e)}")
        logger.error(f"CapCut导出任务启动失败 - 异常详情: {repr(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"启动导出任务失败: {str(e)}")

@router.get("/status")
async def get_capcut_status():
    """获取CapCut服务状态"""
    try:
        # 从数据库获取最新的配置
        from app.core.database import get_db
        from app.services.system_config_service import SystemConfigService
        from app.core.config import settings
        
        # 获取数据库会话
        async for db in get_db():
            db_configs = await SystemConfigService.get_all_configs(db)
            capcut_api_url = db_configs.get("capcut_api_url", settings.capcut_api_url)
            break
        
        # 使用专门的健康检查端点
        response = requests.get(f"{capcut_api_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            if health_data.get("status") == "healthy":
                return {"status": "online"}
        return {"status": "offline"}
    except:
        return {"status": "offline"}