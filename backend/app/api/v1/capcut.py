from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import RedirectResponse, Response
from typing import List, Dict, Any, Optional
import os
import requests
import json
import time
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel, field_validator

from app.core.database import get_db
from app.models.video_slice import VideoSlice, VideoSubSlice
from app.models.transcript import Transcript
from app.schemas.video_slice import VideoSlice as VideoSliceSchema
from app.models.video import Video
from app.models.project import Project
from app.core.config import settings
from app.models.resource import Resource, ResourceTag
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.models.processing_task import ProcessingTask
# 避免循环导入 - 导入Celery任务对象
from app.tasks.video_tasks import export_slice_to_capcut as celery_export_slice_to_capcut

router = APIRouter(
    tags=["capcut"],
    responses={404: {"description": "未找到"}},
)

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

@router.post("/export-slice/{slice_id}",
    summary="导出视频切片到CapCut",
    description="将指定的视频切片导出到CapCut应用。该操作会启动一个异步Celery任务来处理导出过程。",
    responses={
        200: {
            "description": "成功启动导出任务",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "CapCut导出任务已启动",
                        "task_id": "string",
                        "processing_task_id": 1
                    }
                }
            }
        },
        404: {"description": "切片不存在"},
        500: {"description": "服务器内部错误"}
    }
, operation_id="export_slice")
async def export_slice_to_capcut(
    slice_id: int,
    request: ExportSliceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    导出视频切片到CapCut (异步Celery任务)
    
    将指定的视频切片导出到CapCut应用。该操作会启动一个异步Celery任务来处理导出过程。
    
    Args:
        slice_id (int): 视频切片的ID
        request (ExportSliceRequest): 导出请求参数，包含目标文件夹路径
        db (AsyncSession): 数据库会话依赖
        
    Returns:
        dict: 导出任务启动结果
            - success (bool): 是否成功启动
            - message (str): 操作结果消息
            - task_id (str): CeleryTaskID
            - processing_task_id (int): 处理TaskID
            
    Raises:
        HTTPException: 当切片不存在或启动任务失败时抛出异常
    """
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
        
        # 更新处理任务记录的CeleryTaskID
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

@router.get("/proxy-resource/{resource_path:path}",
    summary="代理MinIO资源",
    description="为CapCut服务器提供可访问的MinIO资源代理，允许CapCut服务访问存储在MinIO中的资源文件。",
    responses={
        200: {"description": "成功返回资源内容"},
        404: {"description": "资源未找到"},
        500: {"description": "服务器内部错误"}
    }
)
async def proxy_minio_resource(resource_path: str):
    """
    为CapCut服务器提供可访问的MinIO资源代理
    
    允许CapCut服务访问存储在MinIO中的资源文件。该端点会从MinIO获取指定路径的资源并直接返回给请求方。
    
    Args:
        resource_path (str): MinIO中的资源路径
        
    Returns:
        Response: 包含资源内容的HTTP响应，带有适当的内容类型和缓存头
        
    Raises:
        HTTPException: 当资源未找到或访问失败时抛出异常
    """
    try:
        logger.info(f"代理MinIO资源请求: {resource_path}")
        
        # 从MinIO获取资源内容并直接返回
        from app.services.minio_client import minio_service
        from fastapi import Response
        import mimetypes
        
        # 获取文件内容
        response = minio_service.internal_client.get_object(
            settings.minio_bucket_name, 
            resource_path
        )
        
        # 读取内容
        content = response.read()
        response.close()
        response.release_conn()
        
        # 确定内容类型
        content_type, _ = mimetypes.guess_type(resource_path)
        if content_type is None:
            content_type = "application/octet-stream"
        
        logger.info(f"成功代理资源 {resource_path}, 大小: {len(content)} 字节")
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Length": str(len(content)),
                "Cache-Control": "public, max-age=3600"  # 1小时缓存
            }
        )
    except Exception as e:
        logger.error(f"代理MinIO资源失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"代理资源失败: {str(e)}")


@router.get("/status",
    summary="检查CapCut服务状态",
    description="通过向CapCut服务发送健康检查请求来验证服务是否在线。该端点会尝试连接到配置的CapCut服务URL并检查其健康状态。",
    responses={
        200: {
            "description": "成功返回CapCut服务状态",
            "content": {
                "application/json": {
                    "example": {
                        "status": "online"
                    }
                }
            }
        },
        503: {"description": "服务不可用"}
    }
, operation_id="capcut_status")
async def get_capcut_status():
    """
    获取CapCut服务状态
    
    通过向CapCut服务发送健康检查请求来验证服务是否在线。
    该端点会尝试连接到配置的CapCut服务URL并检查其健康状态。
    
    Returns:
        dict: 包含服务状态的字典
            - status (str): 服务状态，"online"表示在线，"offline"表示离线
            
    Example:
        {
            "status": "online"
        }
    """
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


@router.get("/slice-info/{filename}",
    summary="通过CapCut文件名查询切片信息",
    description="根据CapCut导出的文件名精确匹配对应的切片信息，返回完整的切片数据包括视频和项目信息。",
    responses={
        200: {
            "description": "成功返回切片信息",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "slice_id": 217,
                            "video_id": 76,
                            "project_id": 2,
                            "project_name": "示例项目",
                            "video_title": "示例视频标题",
                            "cover_title": "灭毒战争",
                            "title": "委内瑞拉战争前夜",
                            "description": "美国对委内瑞拉的军事行动...",
                            "tags": ["委内瑞拉", "川普", "南方之谋"],
                            "start_time": 3074.97,
                            "end_time": 3450.31,
                            "duration": 375.611,
                            "status": "completed",
                            "capcut_status": "completed",
                            "capcut_draft_url": "http://107.173.223.214:9000/capcut-drafts/dfd_cat_1763276651_78e06300.zip",
                            "file_size": 86068223,
                            "created_at": "2025-11-16T07:00:28",
                            "updated_at": "2025-11-16T07:05:10"
                        }
                    }
                }
            }
        },
        404: {"description": "未找到匹配的切片"},
        422: {"description": "文件名格式无效"}
    },
    operation_id="get_slice_info_by_capcut_filename"
)
async def get_slice_info_by_capcut_filename(
    filename: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    通过CapCut文件名查询切片信息

    根据CapCut导出的文件名（如 dfd_cat_1763276651_78e06300.zip）精确匹配对应的切片，
    返回完整的切片信息包括视频信息、项目信息等。

    Args:
        filename (str): CapCut文件名，不包含路径前缀
        db (AsyncSession): 数据库会话依赖

    Returns:
        Dict[str, Any]: 包含切片信息的响应
            - success (bool): 查询是否成功
            - data (Dict): 切片详细信息
            - message (str): 操作结果描述

    Raises:
        HTTPException: 当文件名格式无效或未找到匹配切片时抛出异常

    Examples:
        >>> GET /api/v1/capcut/slice-info/dfd_cat_1763276651_78e06300.zip
    """
    try:
        # 验证文件名格式
        if not _is_valid_capcut_filename(filename):
            raise HTTPException(
                status_code=422,
                detail=f"无效的CapCut文件名格式: {filename}。期望格式: dfd_cat_{timestamp}_{hash}.zip"
            )

        # 标准化文件名（移除路径前缀）
        clean_filename = _extract_filename(filename)

        # 查询匹配的切片 - 使用验证过的raw SQL方式
        pattern = f"%{clean_filename}%"
        query = text("""
            SELECT vs.*, v.title as video_title, p.name as project_name
            FROM video_slices vs
            LEFT JOIN videos v ON vs.video_id = v.id
            LEFT JOIN projects p ON v.project_id = p.id
            WHERE vs.capcut_draft_url LIKE :pattern
            LIMIT 1
        """)

        result = await db.execute(query, {"pattern": pattern})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"未找到匹配CapCut文件名 '{clean_filename}' 的切片"
            )

        # 构建完整响应数据 - 直接从row构建
        slice_info = {
            "id": row.id,
            "video_id": row.video_id,
            "cover_title": row.cover_title,
            "title": row.title,
            "description": row.description,
            "tags": row.tags,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "duration": row.duration,
            "status": row.status,
            "capcut_status": row.capcut_status,
            "capcut_draft_url": row.capcut_draft_url,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "video_info": {
                "id": row.video_id,
                "title": row.video_title,
                "project_name": row.project_name
            }
        }

        return {
            "success": True,
            "data": slice_info,
            "message": f"成功找到切片信息: {slice_info['cover_title']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询CapCut切片信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ===== 辅助函数 =====

def _is_valid_capcut_filename(filename: str) -> bool:
    """验证CapCut文件名格式"""
    # CapCut文件名正则表达式: dfd_cat_{timestamp}_{hash}.zip
    pattern = r'^dfd_cat_\d+_[a-f0-9]+\.zip$'
    return bool(re.match(pattern, filename, re.IGNORECASE))

def _extract_filename(url_or_filename: str) -> str:
    """从URL或路径中提取文件名"""
    # 移除URL前缀，只保留文件名部分
    if '/' in url_or_filename:
        return url_or_filename.split('/')[-1]
    return url_or_filename

async def _build_slice_info_response(
    db: AsyncSession,
    slice_obj: VideoSlice
) -> Dict[str, Any]:
    """构建切片信息响应"""
    try:
        # 获取视频信息
        video_result = await db.execute(select(Video).where(Video.id == slice_obj.video_id))
        video_obj = video_result.scalar_one_or_none()

        # 获取项目信息
        project_name = None
        if video_obj:
            project_result = await db.execute(select(Project).where(Project.id == video_obj.project_id))
            project_obj = project_result.scalar_one_or_none()
            project_name = project_obj.name if project_obj else None

        # 提取文件名
        capcut_filename = None
        if slice_obj.capcut_draft_url:
            capcut_filename = _extract_filename(slice_obj.capcut_draft_url)

        # 构建响应数据
        slice_info = {
            "slice_id": slice_obj.id,
            "video_id": slice_obj.video_id,
            "project_id": video_obj.project_id if video_obj else None,
            "project_name": project_name,
            "video_title": video_obj.title if video_obj else None,
            "cover_title": slice_obj.cover_title,
            "title": slice_obj.title,
            "description": slice_obj.description,
            "tags": slice_obj.tags or [],
            "start_time": slice_obj.start_time,
            "end_time": slice_obj.end_time,
            "duration": slice_obj.duration,
            "status": slice_obj.status,
            "capcut_status": slice_obj.capcut_status,
            "capcut_draft_url": slice_obj.capcut_draft_url,
            "file_size": slice_obj.file_size,
            "created_at": slice_obj.created_at,
            "updated_at": slice_obj.updated_at
        }

        # 添加文件名（如果存在）
        if capcut_filename:
            slice_info["capcut_filename"] = capcut_filename

        return slice_info

    except Exception as e:
        logger.error(f"构建切片响应失败: {str(e)}")
        # 返回基础信息
        return {
            "slice_id": slice_obj.id,
            "video_id": slice_obj.video_id,
            "project_id": None,
            "project_name": None,
            "video_title": None,
            "cover_title": slice_obj.cover_title,
            "title": slice_obj.title,
            "description": slice_obj.description,
            "tags": slice_obj.tags or [],
            "start_time": slice_obj.start_time,
            "end_time": slice_obj.end_time,
            "duration": slice_obj.duration,
            "status": slice_obj.status,
            "capcut_status": slice_obj.capcut_status,
            "capcut_draft_url": slice_obj.capcut_draft_url,
            "file_size": slice_obj.file_size,
            "created_at": slice_obj.created_at,
            "updated_at": slice_obj.updated_at
        }