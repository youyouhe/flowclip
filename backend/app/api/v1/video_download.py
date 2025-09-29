from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import os
import base64
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask
from app.schemas.video import VideoResponse, VideoDownloadRequest, VideoDownloadJsonRequest
from app.services.youtube_downloader_minio import downloader_minio
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType
from app.core.celery import celery_app

router = APIRouter()

import logging
logger = logging.getLogger(__name__)


async def download_video_task(
    video_id: int,
    url: str,
    project_id: int,
    user_id: int,
    quality: str,
    db: AsyncSession,
    cookies_path: str = None  # 新增cookie文件路径参数
):
    """后台下载视频任务（使用MinIO存储）"""
    logger.info(f"开始后台下载任务: video_id={video_id}, url={url}")
    
    try:
        # 获取视频实例
        stmt = select(Video).where(Video.id == video_id)
        result = await db.execute(stmt)
        video = result.scalar_one()
        
        # 更新进度
        video.download_progress = 10.0
        await db.commit()
        
        logger.info("开始下载视频...")
        # 下载并上传到MinIO
        download_result = await downloader_minio.download_and_upload_video(
            url=url,
            project_id=project_id,
            user_id=user_id,
            quality=quality,
            cookies_file=cookies_path  # 传递cookie文件路径
        )
        
        logger.info("视频下载完成，开始更新数据库...")
        # 更新视频记录
        video.status = "completed"
        video.download_progress = 100.0
        video.file_path = download_result['minio_path']
        video.filename = download_result['filename']
        video.file_size = download_result['filesize']
        video.thumbnail_url = download_result.get('thumbnail_url')
        
        await db.commit()
        logger.info("数据库更新完成")
        
    except Exception as e:
        logger.error(f"下载任务失败: {str(e)}", exc_info=True)
        # 更新失败状态
        try:
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one()
            video.status = "failed"
            video.download_progress = 0.0
            await db.commit()
            logger.error(f"失败状态已更新到数据库: {str(e)}")
        except Exception as db_error:
            logger.error(f"更新数据库失败状态失败: {str(db_error)}")
        
        # 清理cookie文件
        if cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
                logger.info(f"已清理cookie文件: {cookies_path}")
            except Exception as cleanup_error:
                logger.warning(f"清理cookie文件失败: {cleanup_error}")
        
        # 重新抛出异常让调用者知道
        raise
    finally:
        # 清理cookie文件（如果存在）
        if cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
                logger.info(f"已清理cookie文件: {cookies_path}")
            except Exception as cleanup_error:
                logger.warning(f"清理cookie文件失败: {cleanup_error}")


async def _process_video_download(
    url: str,
    project_id: int,
    quality: str,
    cookies_path: str,
    current_user: User,
    db: AsyncSession
):
    """处理视频下载的核心逻辑"""
    # 验证项目属于当前用户
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # 获取视频信息
    try:
        video_info = await downloader_minio.get_video_info(url, cookies_path)
    except Exception as e:
        # 清理cookie文件
        if cookies_path and os.path.exists(cookies_path):
            os.remove(cookies_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法获取视频信息: {str(e)}"
        )
    
    # 创建视频记录
    new_video = Video(
        title=video_info['title'],
        description=video_info['description'][:500] if video_info['description'] else None,
        url=url,
        project_id=project_id,
        filename=f"{video_info['title'][:50]}.mp4",
        duration=video_info['duration'],
        file_size=0,  # 将在下载完成后更新
        thumbnail_url=video_info['thumbnail'],
        status="downloading",
        download_progress=0.0
    )
    
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)
    
    # 启动Celery下载任务
    try:
        from app.tasks.video_tasks import download_video as celery_download_video
        
        task = celery_app.send_task('app.tasks.video_tasks.download_video', 
            args=[url, project_id, current_user.id, quality, cookies_path, new_video.id]
        )
        
        # 创建处理任务记录，使用实际的Celery任务ID
        state_manager = get_state_manager(db)
        processing_task = await state_manager.create_processing_task(
            video_id=new_video.id,
            task_type=ProcessingTaskType.DOWNLOAD,
            task_name="视频下载",
            celery_task_id=task.id,
            input_data={"url": url, "quality": quality, "cookies_path": cookies_path}
        )
        
        await db.commit()
        
        logger.info(f"Celery下载任务已启动 - task_id: {task.id}, processing_task_id: {processing_task.id}")
        
    except Exception as e:
        logger.error(f"启动Celery下载任务失败: {str(e)}")
        # 如果Celery启动失败，回退到原来的BackgroundTasks方式
        logger.info("回退到BackgroundTasks方式")
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            download_video_task,
            new_video.id,
            url,
            project_id,
            current_user.id,
            quality,
            db,
            cookies_path
        )
    
    # 返回包含项目名称的视频数据
    video_dict = {
        'id': new_video.id,
        'title': new_video.title,
        'description': new_video.description,
        'url': new_video.url,
        'project_id': new_video.project_id,
        'filename': new_video.filename,
        'file_path': new_video.file_path,
        'duration': new_video.duration,
        'file_size': new_video.file_size,
        'thumbnail_url': new_video.thumbnail_url,
        'status': new_video.status,
        'download_progress': new_video.download_progress,
        'created_at': new_video.created_at,
        'updated_at': new_video.updated_at,
        'project_name': project.name
    }
    
    return video_dict


@router.post("/download", response_model=VideoResponse, summary="下载YouTube视频", description="下载指定URL的YouTube视频到项目中", operation_id="download_video")
async def download_video(
    url: str = Form(..., description="YouTube视频URL"),
    project_id: int = Form(..., description="目标项目ID"),
    quality: str = Form('best', description="视频质量 (best, 720p, 480p等)"),
    cookies_file: UploadFile = File(None, description="可选的cookies文件，用于访问需要登录的视频"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """下载YouTube视频
    
    下载指定URL的YouTube视频到项目中，支持指定视频质量和使用cookies文件访问需要登录的视频。
    
    Args:
        url (str): YouTube视频URL
        project_id (int): 目标项目ID
        quality (str): 视频质量，可选值: "best", "720p", "480p"等，默认为"best"
        cookies_file (UploadFile): 可选的cookies文件，用于访问需要登录的视频
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        VideoResponse: 创建的视频信息
            - id (int): 视频ID
            - project_id (int): 项目ID
            - title (str): 视频标题
            - description (Optional[str]): 视频描述
            - url (Optional[str]): 视频URL
            - filename (Optional[str]): 视频文件名
            - file_path (Optional[str]): 视频文件路径
            - duration (Optional[float]): 视频时长（秒）
            - file_size (Optional[int]): 文件大小（字节）
            - thumbnail_url (Optional[str]): 缩略图URL
            - status (str): 视频处理状态
            - download_progress (float): 下载进度（0-100）
            - created_at (datetime): 创建时间
            - updated_at (Optional[datetime]): 更新时间
            - project_name (str): 项目名称
    
    Raises:
        HTTPException:
            - 400: 无效的视频URL或文件类型
            - 404: 项目不存在
            - 422: 请求参数验证失败
    
    Examples:
        下载视频: POST /api/v1/videos/download
        Form Data:
        - url: https://www.youtube.com/watch?v=xxxxxx
        - project_id: 1
        - quality: 720p
    """
    # 处理cookie文件
    cookies_path = None
    logger.info(f"收到cookie_file: {cookies_file}")
    
    if cookies_file:
        # 保存上传的cookie文件
        cookies_dir = "/tmp/cookies"
        os.makedirs(cookies_dir, exist_ok=True)
        cookies_path = os.path.join(cookies_dir, f"cookies_{current_user.id}_{uuid.uuid4()}.txt")
        
        try:
            content = await cookies_file.read()
            with open(cookies_path, "wb") as f:
                f.write(content)
            logger.info(f"已保存上传的cookie文件到: {cookies_path}, 大小: {len(content)} bytes")
            
            # 验证文件是否存在
            if os.path.exists(cookies_path):
                logger.info(f"cookie文件验证成功: {cookies_path}")
            else:
                logger.error(f"cookie文件保存失败: {cookies_path}")
                
        except Exception as e:
            logger.error(f"保存cookie文件失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"保存cookie文件失败: {str(e)}"
            )
    else:
        logger.info("未上传cookie文件")

    # 使用公共函数处理下载
    return await _process_video_download(url, project_id, quality, cookies_path, current_user, db)


@router.post("/download-json", response_model=VideoResponse, summary="下载YouTube视频(JSON)", description="使用JSON格式下载YouTube视频到项目中", operation_id="download_video_json")
async def download_video_json(
    request: VideoDownloadJsonRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """下载YouTube视频 (JSON格式)
    
    使用JSON格式下载指定URL的YouTube视频到项目中，支持指定视频质量和使用base64编码的cookies文件访问需要登录的视频。
    
    Args:
        request (VideoDownloadJsonRequest): JSON请求体
            - url (str): YouTube视频URL
            - project_id (int): 目标项目ID
            - quality (str): 视频质量，可选值: "best", "720p", "480p"等，默认为"best"
            - cookies_file (str): 可选的base64编码的cookies文件内容
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        VideoResponse: 创建的视频信息
            - id (int): 视频ID
            - project_id (int): 项目ID
            - title (str): 视频标题
            - description (Optional[str]): 视频描述
            - url (Optional[str]): 视频URL
            - filename (Optional[str]): 视频文件名
            - file_path (Optional[str]): 视频文件路径
            - duration (Optional[float]): 视频时长（秒）
            - file_size (Optional[int]): 文件大小（字节）
            - thumbnail_url (Optional[str]): 缩略图URL
            - status (str): 视频处理状态
            - download_progress (float): 下载进度（0-100）
            - created_at (datetime): 创建时间
            - updated_at (Optional[datetime]): 更新时间
            - project_name (str): 项目名称
    
    Raises:
        HTTPException:
            - 400: 无效的视频URL、cookies格式或文件类型
            - 404: 项目不存在
            - 422: 请求参数验证失败
    
    Examples:
        下载视频: POST /api/v1/videos/download-json
        JSON Body:
        {
            "url": "https://www.youtube.com/watch?v=xxxxxx",
            "project_id": 1,
            "quality": "720p",
            "cookies_file": "base64_encoded_cookies_content"
        }
    """
    # 处理base64编码的cookies
    cookies_path = None
    logger.info(f"收到JSON请求 - URL: {request.url}, Project ID: {request.project_id}, Quality: {request.quality}")
    
    if request.cookies_file:
        cookies_dir = "/tmp/cookies"
        os.makedirs(cookies_dir, exist_ok=True)
        cookies_path = os.path.join(cookies_dir, f"cookies_{current_user.id}_{uuid.uuid4()}.txt")
        
        try:
            # 解码base64 cookies
            cookies_data = base64.b64decode(request.cookies_file)
            with open(cookies_path, "wb") as f:
                f.write(cookies_data)
            logger.info(f"已保存base64编码的cookie文件到: {cookies_path}, 大小: {len(cookies_data)} bytes")
            
            # 验证文件是否存在
            if os.path.exists(cookies_path):
                logger.info(f"cookie文件验证成功: {cookies_path}")
            else:
                logger.error(f"cookie文件保存失败: {cookies_path}")
                
        except Exception as e:
            logger.error(f"处理base64 cookies失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"处理cookies失败: {str(e)}"
            )
    else:
        logger.info("未提供cookies文件")

    # 使用公共函数处理下载
    return await _process_video_download(request.url, request.project_id, request.quality, cookies_path, current_user, db)


@router.get("/{video_id}/download-url", operation_id="get_video_download_url")
async def get_video_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频文件的预签名下载URL"""
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    if not video.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not uploaded"
        )
    
    # 从minio_path中提取对象名称
    # 移除bucket名称前缀
    bucket_prefix = f"{settings.minio_bucket_name}/"
    if video.file_path.startswith(bucket_prefix):
        object_name = video.file_path[len(bucket_prefix):]
    else:
        object_name = video.file_path
    
    url = await minio_service.get_file_url(object_name, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )
    
    return {"download_url": url, "expires_in": expiry, "object_name": object_name}