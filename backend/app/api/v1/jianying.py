"""
Jianying API 路由模块
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import Dict, Any, Optional
import logging
import re
from datetime import datetime

# 导入依赖
from app.core.database import get_db, get_sync_db_context
from app.models.video_slice import VideoSlice, VideoSubSlice
from app.models.transcript import Transcript
from app.models.video import Video
from app.schemas.video_slice import VideoSlice as VideoSliceSchema
from app.models.resource import Resource, ResourceTag
from app.core.config import settings
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage
from app.models.processing_task import ProcessingTask
from app.tasks.video_tasks import export_slice_to_jianying as celery_export_slice_to_jianying
from app.services.minio_client import minio_service
from pydantic import BaseModel, Field

# 创建logger
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["Jianying"])

# Pydantic 模型
class JianyingExportRequest(BaseModel):
    draft_folder: str = Field(..., description="Jianying草稿保存文件夹路径")

class JianyingExportResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None
    processing_task_id: Optional[int] = None
    draft_url: Optional[str] = None

def validate_draft_folder_path(draft_folder: str) -> str:
    """验证 draft_folder 路径格式

    Args:
        draft_folder: 用户提供的路径字符串

    Returns:
        str: 验证并清理后的路径字符串

    Raises:
        ValueError: 如果路径格式无效
    """
    if not draft_folder or not draft_folder.strip():
        raise ValueError("draft_folder 不能为空")

    draft_folder = draft_folder.strip()

    # 检查路径长度 (Windows MAX_PATH 限制约为 260 字符，但现代Windows支持更长的路径)
    if len(draft_folder) > 1024:
        raise ValueError("draft_folder 路径长度不能超过 1024 个字符")

    # Windows 路径验证
    if re.match(r'^[A-Za-z]:\\', draft_folder):
        # Windows 绝对路径 (例如: C:\Users\username\Documents)
        # 检查非法字符 (除了路径分隔符和冒号)
        illegal_chars = r'[<>"|?*]'
        if re.search(illegal_chars, draft_folder):
            raise ValueError("Windows 路径包含非法字符: < > \" | ? *")

        # 检查保留名称 (针对路径中的每个部分)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }

        # 分割路径并检查每个部分
        path_parts = draft_folder.split('\\')
        for part in path_parts:
            if part in reserved_names:
                raise ValueError(f"Windows 路径包含保留名称: {part}")

        return draft_folder

    # Unix/Linux/macOS 路径验证
    elif draft_folder.startswith('/'):
        # Unix 绝对路径
        illegal_chars = r'[<>:"|?]'
        if re.search(illegal_chars, draft_folder):
            raise ValueError("Unix 路径包含非法字符: < > : \" | ?")

        # 检查路径不能包含 null 字符
        if '\x00' in draft_folder:
            raise ValueError("路径不能包含 null 字符")

        return draft_folder

    # 相对路径验证
    else:
        # 相对路径，检查基本的安全性
        illegal_chars = r'[<>:"|?*\x00]'
        if re.search(illegal_chars, draft_folder):
            raise ValueError("路径包含非法字符: < > : \" | ? * 或 null 字符")

        # 防止路径遍历攻击
        normalized_path = draft_folder.replace('\\', '/')
        if '..' in normalized_path.split('/'):
            raise ValueError("路径不能包含 '..' 以防止路径遍历攻击")

        return draft_folder

class JianyingServiceAPI:
    """Jianying 服务 API 类"""
    def __init__(self):
        self.base_url = None
        self.api_key = None
        self._load_config()

    def _load_config(self):
        """从配置或数据库加载设置"""
        try:
            from app.services.system_config_service import SystemConfigService

            # 尝试从数据库获取配置
            with get_sync_db_context() as db:
                configs = SystemConfigService.get_all_configs_sync(db)
                self.base_url = configs.get("jianying_api_url", settings.jianying_api_url)
                self.api_key = configs.get("jianying_api_key", settings.jianying_api_key)
        except Exception as e:
            logger.warning(f"无法从数据库获取Jianying配置，使用默认配置: {e}")
            self.base_url = settings.jianying_api_url
            self.api_key = settings.jianying_api_key

    def get_resource_by_tag(self, tag_name: str, resource_type: str = "audio") -> Optional[str]:
        """获取资源URL"""
        # 硬编码的资源映射（保持与原CapCut API一致）
        resource_map = {
            ("水波纹", "audio"): "http://192.168.8.107:9001/youtube-videos/audio-effects/droplet.mp3",
            ("片尾", "video"): "http://192.168.8.107:9001/youtube-videos/video-effects/end.mp4"
        }

        return resource_map.get((tag_name, resource_type))

    def get_resource_by_tag_from_db(self, db: Session, tag_name: str, resource_type: str = "audio") -> Optional[str]:
        """从数据库根据标签查询资源URL"""
        try:
            # 查询标签
            tag_result = db.execute(
                select(ResourceTag).where(ResourceTag.name == tag_name, ResourceTag.tag_type == resource_type)
            )
            tag = tag_result.scalar_one_or_none()

            if not tag:
                logger.warning(f"标签 '{tag_name}' 未找到")
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
                logger.warning(f"标签 '{tag_name}' 下未找到资源")
                return None

            # 返回资源URL
            return f"http://{settings.minio_endpoint}/{settings.minio_bucket_name}/{resource.file_path}"
        except Exception as e:
            logger.error(f"从数据库获取资源失败: {e}")
            return None

# 创建Jianying服务实例
jianying_service = JianyingServiceAPI()

@router.post("/export-slice-jianying/{slice_id}", response_model=JianyingExportResponse)
async def export_slice_to_jianying(
    slice_id: int = Path(..., description="视频切片ID", gt=0),
    request: JianyingExportRequest = ...,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
):
    """导出视频切片到Jianying"""
    try:
        # 验证 draft_folder 路径
        validated_draft_folder = validate_draft_folder_path(request.draft_folder)

        # 获取切片信息
        slice_obj = await db.get(VideoSlice, slice_id)
        if not slice_obj:
            raise HTTPException(status_code=404, detail="切片不存在")

        # 添加调试日志
        logger.info(f"开始Jianying导出任务 - 切片ID: {slice_id}, 类型: {slice_obj.type}, draft_folder: {validated_draft_folder}")

        # 创建处理任务记录
        processing_task = ProcessingTask(
            task_type=ProcessingTaskType.JIANYING_EXPORT,
            status=ProcessingTaskStatus.PENDING,
            progress=0.0,
            input_data={
                "slice_id": slice_id,
                "draft_folder": validated_draft_folder
            },
            video_id=slice_obj.video_id,
            user_id=getattr(background_tasks, 'user_id', None),
            created_at=datetime.utcnow()
        )
        db.add(processing_task)
        await db.commit()
        await db.refresh(processing_task)

        # 更新切片的Jianying状态
        slice_obj.jianying_status = "pending"
        slice_obj.jianying_task_id = processing_task.celery_task_id
        slice_obj.jianying_error_message = None
        await db.commit()

        # 触发Celery异步任务
        try:
            celery_task = celery_export_slice_to_jianying.delay(
                slice_id=slice_id,
                draft_folder=validated_draft_folder,
                user_id=getattr(background_tasks, 'user_id', None)
            )

            # 更新处理任务记录中的Celery任务ID
            processing_task.celery_task_id = celery_task.id
            await db.commit()

            logger.info(f"Jianying Celery任务已提交 - Celery任务ID: {celery_task.id}, 处理任务ID: {processing_task.id}")

        except Exception as e:
            logger.error(f"提交Jianying Celery任务失败: {str(e)}")
            # 更新处理任务状态为失败
            processing_task.status = ProcessingTaskStatus.FAILURE
            processing_task.error_message = f"提交Celery任务失败: {str(e)}"
            await db.commit()
            raise HTTPException(status_code=500, detail=f"提交Jianying导出任务失败: {str(e)}")

        return JianyingExportResponse(
            success=True,
            message="Jianying导出任务已启动",
            task_id=celery_task.id,
            processing_task_id=processing_task.id
        )

    except ValueError as e:
        # 处理路径验证错误
        logger.error(f"Jianying导出参数验证失败 - 切片ID: {slice_id}, 错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 处理其他异常
        logger.error(f"Jianying导出任务启动失败 - 切片ID: {slice_id}, 错误: {str(e)}")
        import traceback
        logger.error(f"详细错误栈: {traceback.format_exc()}")

        # 尝试回滚数据库操作
        try:
            await db.rollback()
        except:
            pass

        raise HTTPException(status_code=500, detail="Jianying导出任务启动失败")

@router.get("/proxy-resource/{resource_path:path}")
async def proxy_jianying_resource(resource_path: str, db: AsyncSession = Depends(get_db)):
    """为Jianying服务器提供MinIO资源访问代理"""
    try:
        logger.info(f"Jianying资源代理请求 - 资源路径: {resource_path}")

        # 从MinIO获取资源文件
        try:
            response = minio_service.internal_client.get_object(settings.minio_bucket_name, resource_path)
            file_data = response.read()
            response.close()
            response.release_conn()
        except Exception as e:
            logger.error(f"从MinIO获取资源失败: {str(e)}")
            raise HTTPException(status_code=404, detail="资源文件不存在")

        # 确定文件的MIME类型
        import mimetypes
        mime_type, _ = mimetypes.guess_type(resource_path)
        if mime_type is None:
            # 如果无法猜测MIME类型，使用默认值
            if resource_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                mime_type = 'video/mp4'
            elif resource_path.lower().endswith(('.mp3', '.wav', '.aac', '.m4a')):
                mime_type = 'audio/mpeg'
            elif resource_path.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif resource_path.lower().endswith(('.png')):
                mime_type = 'image/png'
            else:
                mime_type = 'application/octet-stream'

        # 返回文件内容，设置适当的缓存头
        from fastapi.responses import Response
        return Response(
            content=file_data,
            media_type=mime_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # 缓存1小时
                "Access-Control-Allow-Origin": "*",  # 允许跨域访问
                "Content-Disposition": f"inline; filename=\"{resource_path.split('/')[-1]}\""
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Jianying资源代理失败: {str(e)}")
        raise HTTPException(status_code=500, detail="资源代理服务失败")

@router.get("/status")
async def check_jianying_status(db: AsyncSession = Depends(get_db)):
    """检查Jianying服务状态"""
    try:
        # 从数据库获取最新的Jianying API URL配置
        try:
            from app.services.system_config_service import SystemConfigService
            configs = await SystemConfigService.get_all_configs(db)
            jianying_api_url = configs.get("jianying_api_url", settings.jianying_api_url)
        except Exception as e:
            logger.warning(f"无法从数据库获取Jianying配置，使用默认配置: {e}")
            jianying_api_url = settings.jianying_api_url

        if not jianying_api_url:
            return {
                "status": "offline",
                "message": "Jianying API URL未配置",
                "api_url": None,
                "timestamp": datetime.utcnow().isoformat()
            }

        # 尝试向Jianying服务发送健康检查请求
        import requests
        try:
            health_url = f"{jianying_api_url.rstrip('/')}/health"
            response = requests.get(health_url, timeout=10)

            if response.status_code == 200:
                return {
                    "status": "online",
                    "message": "Jianying服务运行正常",
                    "api_url": jianying_api_url,
                    "timestamp": datetime.utcnow().isoformat(),
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                return {
                    "status": "error",
                    "message": f"Jianying服务返回错误状态码: {response.status_code}",
                    "api_url": jianying_api_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except requests.exceptions.Timeout:
            return {
                "status": "timeout",
                "message": "Jianying服务连接超时",
                "api_url": jianying_api_url,
                "timestamp": datetime.utcnow().isoformat()
            }
        except requests.exceptions.ConnectionError:
            return {
                "status": "offline",
                "message": "无法连接到Jianying服务",
                "api_url": jianying_api_url,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"检查Jianying服务时发生错误: {str(e)}",
                "api_url": jianying_api_url,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error(f"检查Jianying状态失败: {str(e)}")
        return {
            "status": "error",
            "message": f"检查服务状态失败: {str(e)}",
            "api_url": None,
            "timestamp": datetime.utcnow().isoformat()
        }