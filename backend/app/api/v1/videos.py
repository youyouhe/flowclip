from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Form, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
import uuid
import os
import time
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_from_token
from app.core.config import settings
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask, ProcessingStatus
from app.schemas.video import VideoResponse, VideoDownloadRequest, VideoUpdate, PaginatedVideoResponse
from app.services.youtube_downloader import downloader
from app.services.youtube_downloader_minio import downloader_minio
from app.services.minio_client import minio_service
from app.services.state_manager import get_state_manager
from app.core.constants import ProcessingTaskType
from app.tasks.video_tasks import extract_audio, generate_srt

# 简单的内存缓存，用于减少数据库查询
progress_cache = {}
CACHE_DURATION = 5  # 5秒缓存
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

@router.get("/active", response_model=List[VideoResponse])
async def get_active_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户所有非完成状态的视频"""
    # 查询所有非完成状态的视频
    stmt = select(Video, Project.name.label('project_name')).join(Project).where(
        Project.user_id == current_user.id,
        Video.status.notin_(['completed', 'failed'])
    ).order_by(Video.created_at.desc())
    
    result = await db.execute(stmt)
    videos_with_project = result.all()
    
    # 构建包含项目名称的视频列表
    videos = []
    for video, project_name in videos_with_project:
        # 检查processing_status以获取更准确的下载状态
        stmt_processing = select(ProcessingStatus).where(ProcessingStatus.video_id == video.id)
        result_processing = await db.execute(stmt_processing)
        processing_status = result_processing.scalar_one_or_none()
        
        # 确定实际的下载状态和进度
        actual_status = video.status
        actual_download_progress = video.download_progress or 0
        
        # 如果processing_status显示下载已完成，优先使用该状态
        if processing_status and processing_status.download_status == 'success':
            actual_download_progress = 100.0
            # 如果videos.status还是pending或downloading，更新为downloaded
            if actual_status in ['pending', 'downloading']:
                actual_status = 'downloaded'
        
        video_dict = {
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'url': video.url,
            'project_id': video.project_id,
            'filename': video.filename,
            'file_path': video.file_path,
            'duration': video.duration,
            'file_size': video.file_size,
            'thumbnail_url': video.thumbnail_url,
            'status': actual_status,
            'download_progress': actual_download_progress,
            'created_at': video.created_at,
            'updated_at': video.updated_at,
            'project_name': project_name
        }
        videos.append(video_dict)
    
    return videos

@router.get("/", response_model=PaginatedVideoResponse)
async def get_videos(
    project_id: Optional[int] = Query(None, description="项目ID筛选"),
    status: Optional[str] = Query(None, description="视频状态筛选"),
    srt_processed: Optional[bool] = Query(None, description="SRT处理是否完成"),
    search: Optional[str] = Query(None, description="搜索视频标题"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    min_duration: Optional[int] = Query(None, description="最小时长（秒）"),
    max_duration: Optional[int] = Query(None, description="最大时长（秒）"),
    min_file_size: Optional[int] = Query(None, description="最小文件大小（字节）"),
    max_file_size: Optional[int] = Query(None, description="最大文件大小（字节）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的所有视频（支持筛选功能）"""
    # 构建基础查询
    stmt = select(Video, Project.name.label('project_name')).join(Project).where(Project.user_id == current_user.id)
    
    # 添加筛选条件
    if project_id:
        stmt = stmt.where(Video.project_id == project_id)
    
    if status:
        stmt = stmt.where(Video.status == status)
    
    # 添加SRT处理状态筛选
    if srt_processed is not None:
        # 需要检查ProcessingTask表中是否有成功的SRT生成任务
        if srt_processed:
            # 只显示SRT处理成功的视频
            srt_subquery = select(ProcessingTask.video_id).where(
                ProcessingTask.task_type == ProcessingTaskType.GENERATE_SRT,
                ProcessingTask.status == "success"
            ).distinct()
            stmt = stmt.where(Video.id.in_(srt_subquery))
        else:
            # 只显示SRT处理未成功的视频（即没有成功任务的视频）
            srt_subquery = select(ProcessingTask.video_id).where(
                ProcessingTask.task_type == ProcessingTaskType.GENERATE_SRT,
                ProcessingTask.status == "success"
            ).distinct()
            stmt = stmt.where(~Video.id.in_(srt_subquery))
    
    if search:
        stmt = stmt.where(
            or_(
                Video.title.ilike(f"%{search}%"),
                Video.description.ilike(f"%{search}%")
            )
        )
    
    if start_date:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        stmt = stmt.where(Video.created_at >= start_datetime)
    
    if end_date:
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.where(Video.created_at <= end_datetime)
    
    if min_duration is not None:
        stmt = stmt.where(Video.duration >= min_duration)
    
    if max_duration is not None:
        stmt = stmt.where(Video.duration <= max_duration)
    
    if min_file_size is not None:
        stmt = stmt.where(Video.file_size >= min_file_size)
    
    if max_file_size is not None:
        stmt = stmt.where(Video.file_size <= max_file_size)
    
    # 获取总数
    count_stmt = select(func.count(Video.id)).join(Project).where(Project.user_id == current_user.id)
    if project_id:
        count_stmt = count_stmt.where(Video.project_id == project_id)
    if status:
        count_stmt = count_stmt.where(Video.status == status)
    
    # 添加SRT处理状态筛选到计数查询
    if srt_processed is not None:
        if srt_processed:
            # 只显示SRT处理成功的视频
            srt_subquery = select(ProcessingTask.video_id).where(
                ProcessingTask.task_type == ProcessingTaskType.GENERATE_SRT,
                ProcessingTask.status == "success"
            ).distinct()
            count_stmt = count_stmt.where(Video.id.in_(srt_subquery))
        else:
            # 只显示SRT处理未成功的视频
            srt_subquery = select(ProcessingTask.video_id).where(
                ProcessingTask.task_type == ProcessingTaskType.GENERATE_SRT,
                ProcessingTask.status == "success"
            ).distinct()
            count_stmt = count_stmt.where(~Video.id.in_(srt_subquery))
    
    if search:
        count_stmt = count_stmt.where(
            or_(
                Video.title.ilike(f"%{search}%"),
                Video.description.ilike(f"%{search}%")
            )
        )
    if start_date:
        count_stmt = count_stmt.where(Video.created_at >= start_datetime)
    if end_date:
        count_stmt = count_stmt.where(Video.created_at <= end_datetime)
    if min_duration is not None:
        count_stmt = count_stmt.where(Video.duration >= min_duration)
    if max_duration is not None:
        count_stmt = count_stmt.where(Video.duration <= max_duration)
    if min_file_size is not None:
        count_stmt = count_stmt.where(Video.file_size >= min_file_size)
    if max_file_size is not None:
        count_stmt = count_stmt.where(Video.file_size <= max_file_size)
    
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar()
    
    # 添加分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    stmt = stmt.order_by(Video.created_at.desc())
    
    result = await db.execute(stmt)
    videos_with_project = result.all()
    
    # 构建包含项目名称的视频列表
    videos = []
    for video, project_name in videos_with_project:
        video_dict = {
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'url': video.url,
            'project_id': video.project_id,
            'filename': video.filename,
            'file_path': video.file_path,
            'duration': video.duration,
            'file_size': video.file_size,
            'thumbnail_url': video.thumbnail_url,
            'status': video.status,
            'download_progress': video.download_progress,
            'created_at': video.created_at,
            'updated_at': video.updated_at,
            'project_name': project_name
        }
        videos.append(video_dict)
    
    # 构建分页信息
    pagination = {
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": (total_count + page_size - 1) // page_size
    }
    
    return {
        "videos": videos,
        "pagination": pagination,
        "total": total_count
    }

@router.post("/download", response_model=VideoResponse)
async def download_video(
    url: str = Form(...),
    project_id: int = Form(...),
    quality: str = 'best',  # 新增质量参数
    cookies_file: UploadFile = File(None),  # 新增cookie文件上传
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """下载YouTube视频"""
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
        from app.core.constants import ProcessingTaskType
        
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

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取特定视频详情"""
    stmt = select(Video, Project.name.label('project_name')).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video_with_project = result.first()
    if not video_with_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    video, project_name = video_with_project
    
    video_dict = {
        'id': video.id,
        'title': video.title,
        'description': video.description,
        'url': video.url,
        'project_id': video.project_id,
        'filename': video.filename,
        'file_path': video.file_path,
        'duration': video.duration,
        'file_size': video.file_size,
        'thumbnail_url': video.thumbnail_url,
        'status': video.status,
        'download_progress': video.download_progress,
        'created_at': video.created_at,
        'updated_at': video.updated_at,
        'project_name': project_name
    }
    
    return video_dict

@router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除视频及相关文件"""
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
    
    # 删除MinIO中的视频相关文件（如果存在）
    if video.file_path:
        # 从minio_path中提取对象名称
        object_name = video.file_path
        if object_name.startswith(f"{settings.minio_bucket_name}/"):
            object_name = object_name[len(f"{settings.minio_bucket_name}/"):]
        
        await minio_service.delete_file(object_name)
        
        # 删除相关的缩略图和音频文件
        video_id_str = video.filename.split('.')[0] if video.filename else str(video.id)
        
        # 删除缩略图
        thumbnail_object = f"users/{current_user.id}/projects/{video.project_id}/thumbnails/{video_id_str}.jpg"
        await minio_service.delete_file(thumbnail_object)
        
        # 删除音频文件（如果存在）
        audio_object = f"users/{current_user.id}/projects/{video.project_id}/audio/{video_id_str}.mp3"
        await minio_service.delete_file(audio_object)
        
        # 删除字幕文件（如果存在）
        srt_object = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video_id_str}.srt"
        await minio_service.delete_file(srt_object)
    
    # 删除相关的切片文件（MinIO中的文件）
    try:
        # 获取所有相关的切片和子切片
        from app.models import VideoSlice, VideoSubSlice
        
        # 获取主切片
        slices_stmt = select(VideoSlice).where(VideoSlice.video_id == video_id)
        slices_result = await db.execute(slices_stmt)
        slices = slices_result.scalars().all()
        
        # 删除每个切片的MinIO文件
        for slice in slices:
            if slice.sliced_file_path:
                await minio_service.delete_file(slice.sliced_file_path)
            
            # 获取并删除子切片的MinIO文件
            sub_slices_stmt = select(VideoSubSlice).where(VideoSubSlice.slice_id == slice.id)
            sub_slices_result = await db.execute(sub_slices_stmt)
            sub_slices = sub_slices_result.scalars().all()
            
            for sub_slice in sub_slices:
                if sub_slice.sliced_file_path:
                    await minio_service.delete_file(sub_slice.sliced_file_path)
        
        logger.info(f"已删除视频 {video_id} 的所有相关MinIO文件")
        
    except Exception as e:
        logger.warning(f"删除切片文件时出现错误: {str(e)}")
        # 继续执行数据库删除，不因为文件删除失败而阻止整个删除操作
    
    # 删除数据库记录（会自动级联删除相关的分析、切片等记录）
    await db.delete(video)
    await db.commit()
    
    logger.info(f"视频 {video_id} 及其所有相关数据已删除")
    
    return {"message": "Video and all related files deleted successfully"}

@router.put("/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: int,
    video_update: VideoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新视频信息"""
    stmt = select(Video, Project.name.label('project_name')).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video_with_project = result.first()
    if not video_with_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    video, project_name = video_with_project
    
    if video_update.title is not None:
        video.title = video_update.title
    if video_update.description is not None:
        video.description = video_update.description
    
    await db.commit()
    await db.refresh(video)
    
    video_dict = {
        'id': video.id,
        'title': video.title,
        'description': video.description,
        'url': video.url,
        'project_id': video.project_id,
        'filename': video.filename,
        'file_path': video.file_path,
        'duration': video.duration,
        'file_size': video.file_size,
        'thumbnail_url': video.thumbnail_url,
        'status': video.status,
        'download_progress': video.download_progress,
        'created_at': video.created_at,
        'updated_at': video.updated_at,
        'project_name': project_name
    }
    
    return video_dict

@router.get("/{video_id}/download-url")
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

@router.get("/{video_id}/stream")
async def stream_video(
    video_id: int,
    token: str = None,
    db: AsyncSession = Depends(get_db)
):
    """流式传输视频内容（避免CORS问题）"""
    # 如果提供了token参数，使用token验证
    if token:
        current_user = await get_current_user_from_token(token=token, db=db)
    else:
        # 否则使用标准的Authorization头验证
        current_user = await get_current_user(db=db)
    
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
    
    # 获取文件流
    try:
        def _get_file_stream():
            try:
                response = minio_service.internal_client.get_object(
                    settings.minio_bucket_name, 
                    object_name
                )
                return response
            except Exception as e:
                print(f"获取文件流失败: {e}")
                raise
        
        # 获取文件信息
        stat = minio_service.internal_client.stat_object(settings.minio_bucket_name, object_name)
        
        # 创建文件流响应
        from fastapi.responses import StreamingResponse
        
        file_stream = _get_file_stream()
        
        return StreamingResponse(
            file_stream,
            media_type=f"video/{object_name.split('.')[-1]}",
            headers={
                "Content-Disposition": f"inline; filename=\"{video.filename or 'video'}\"",
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"无法获取视频文件: {str(e)}"
        )


@router.post("/{video_id}/extract-audio")
async def extract_audio_endpoint(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提取视频音频"""
    
    logger.info(f"开始提取音频 - video_id: {video_id}, user_id: {current_user.id}")
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        logger.error(f"视频未找到 - video_id: {video_id}, user_id: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    logger.info(f"找到视频 - video_id: {video_id}, title: {video.title}, file_path: {video.file_path}")
    
    if not video.file_path:
        logger.error(f"视频文件路径为空 - video_id: {video_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video file not available"
        )
    
    # 启动音频提取任务
    try:
        logger.info(f"准备启动Celery任务 - video_id: {video.id}, project_id: {video.project_id}, user_id: {current_user.id}, video_minio_path: {video.file_path}")
        
        task = celery_app.send_task('app.tasks.video_tasks.extract_audio', 
            args=[str(video.id), video.project_id, current_user.id, video.file_path]
        )
        
        # 创建处理任务记录，使用实际的Celery任务ID
        state_manager = get_state_manager(db)
        processing_task = await state_manager.create_processing_task(
            video_id=video.id,
            task_type=ProcessingTaskType.EXTRACT_AUDIO,
            task_name="音频提取",
            celery_task_id=task.id,
            input_data={"video_minio_path": video.file_path}
        )
        
        await db.commit()
        
        logger.info(f"Celery任务已启动 - task_id: {task.id}, processing_task_id: {processing_task.id}")
        
    except Exception as e:
        logger.error(f"启动Celery任务失败 - video_id: {video_id}, error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start audio extraction task: {str(e)}"
        )
    
    response_data = {
        "task_id": task.id,
        "processing_task_id": processing_task.id,
        "message": "Audio extraction started",
        "status": "processing"
    }
    logger.info(f"返回响应数据: {response_data}")
    return response_data


@router.post("/{video_id}/generate-srt")
async def generate_srt_endpoint(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成SRT字幕文件"""
    
    logger.info(f"开始生成字幕 - video_id: {video_id}, user_id: {current_user.id}")
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        logger.error(f"视频未找到 - video_id: {video_id}, user_id: {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    logger.info(f"找到视频 - video_id: {video_id}, title: {video.title}")
    
    # 启动SRT生成任务（不再需要split_files参数）
    task = celery_app.send_task('app.tasks.video_tasks.generate_srt', 
        args=[str(video.id), video.project_id, current_user.id]  # 移除split_files参数
    )
    
    # 创建处理任务记录，使用实际的Celery任务ID
    state_manager = get_state_manager(db)
    processing_task = await state_manager.create_processing_task(
        video_id=video.id,
        task_type=ProcessingTaskType.GENERATE_SRT,
        task_name="字幕生成",
        celery_task_id=task.id,
        input_data={"direct_audio": True}  # 标记为直接使用音频文件
    )
    
    await db.commit()
    
    logger.info(f"Celery任务已启动 - task_id: {task.id}, processing_task_id: {processing_task.id}")
    
    return {
        "task_id": task.id,
        "processing_task_id": processing_task.id,
        "message": "SRT generation started",
        "status": "processing"
    }

@router.get("/{video_id}/task-status/{task_id}")
async def get_task_status(
    video_id: int,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取任务状态"""
    
    # 验证视频属于当前用户
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
    
    # 获取处理任务
    stmt = select(ProcessingTask).where(
        ProcessingTask.celery_task_id == task_id
    )
    result = await db.execute(stmt)
    processing_task = result.scalar_one_or_none()
    
    if not processing_task:
        # 回退到旧的任务状态查询
        from celery.result import AsyncResult
        task_result = AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task_result.status,
            "progress": 0,
            "stage": None,
            "message": None,
            "error": None,
            "result": task_result.result if task_result.ready() else None
        }
    
    # 映射数据库状态到前端期望的状态
    status_mapping = {
        "pending": "pending",
        "running": "running", 
        "success": "completed",
        "failure": "failed",
        "retry": "retrying",
        "revoked": "cancelled"
    }
    
    # 如果任务已经完成，确保状态正确映射
    actual_status = processing_task.status
    if processing_task.status == "success" and processing_task.progress == 100:
        actual_status = "completed"
    elif processing_task.status == "failure":
        actual_status = "failed"
    
    return {
        "task_id": task_id,
        "status": status_mapping.get(actual_status, actual_status),
        "progress": processing_task.progress,
        "stage": processing_task.stage,
        "stage_description": processing_task.stage_description,
        "message": processing_task.message,
        "error": processing_task.error_message,
        "result": processing_task.output_data if processing_task.is_completed else None,
        "is_completed": processing_task.is_completed
    }

@router.get("/{video_id}/audio-download-url")
async def get_audio_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取音频文件的预签名下载URL"""
    
    # 验证视频属于当前用户
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
    
    # 构建音频文件对象名称
    audio_object_name = f"users/{current_user.id}/projects/{video.project_id}/audio/{video.id}.wav"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(audio_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found"
        )
    
    # 生成预签名URL
    url = await minio_service.get_file_url(audio_object_name, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate audio download URL"
        )
    
    # 从处理元数据中获取音频时长
    duration = 0
    if video.processing_metadata and video.processing_metadata.get('audio_info'):
        audio_info = video.processing_metadata.get('audio_info', {})
        duration = audio_info.get('duration', 0)
    
    return {
        "download_url": url, 
        "expires_in": expiry, 
        "object_name": audio_object_name,
        "duration": duration,
        "content_type": "audio/wav"
    }

@router.get("/{video_id}/audio-download")
async def download_audio_direct(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """直接下载音频文件，确保正确的文件头和编码"""
    
    # 验证视频属于当前用户
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
    
    # 构建音频文件对象名称
    audio_object_name = f"users/{current_user.id}/projects/{video.project_id}/audio/{video.id}.wav"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(audio_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found"
        )
    
    # 获取文件内容
    try:
        response = minio_service.internal_client.get_object(
            settings.minio_bucket_name, 
            audio_object_name
        )
        content = response.read()
        response.close()
        response.release_conn()
        
        # 直接返回音频文件
        from fastapi.responses import StreamingResponse
        import io
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{video.title}_audio.wav",
                "Content-Type": "audio/wav",
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read audio content: {str(e)}"
        )

@router.get("/{video_id}/srt-download-url")
async def get_srt_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取SRT字幕文件的预签名下载URL"""
    
    # 验证视频属于当前用户
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
    
    # 构建SRT文件对象名称
    srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(srt_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT file not found"
        )
    
    # 生成预签名URL
    url = await minio_service.get_file_url(srt_object_name, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate SRT download URL"
        )
    
    # 对于SRT文件，返回直接下载接口而不是预签名URL
    # 确保通过我们自己的接口下载，避免MinIO编码问题
    from app.core.config import settings
    base_url = settings.api_base_url or "http://localhost:8001"
    return {
        "download_url": f"{base_url}/api/v1/videos/{video_id}/srt-download", 
        "expires_in": expiry, 
        "object_name": srt_object_name,
        "content_type": "text/plain; charset=utf-8"
    }

@router.get("/{video_id}/srt-download")
async def download_srt_direct(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """直接下载SRT文件，确保正确的UTF-8编码"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== SRT下载请求开始 ===")
    logger.info(f"用户ID: {current_user.id}, 视频ID: {video_id}")
    
    try:
        # 验证视频属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            logger.error(f"视频未找到: video_id={video_id}, user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        logger.info(f"找到视频: {video.title} (ID: {video.id})")
        
        # 构建SRT文件对象名称
        srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
        logger.info(f"SRT对象名称: {srt_object_name}")
        
        # 检查文件是否存在
        file_exists = await minio_service.file_exists(srt_object_name)
        if not file_exists:
            logger.error(f"SRT文件不存在: {srt_object_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SRT file not found"
            )
        
        logger.info(f"SRT文件存在: {srt_object_name}")
        
        # 获取文件内容
        try:
            response = minio_service.internal_client.get_object(
                settings.minio_bucket_name, 
                srt_object_name
            )
            content = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"成功读取SRT文件, 大小: {len(content)} 字节")
            
            # 确保内容以UTF-8编码返回
            from fastapi.responses import StreamingResponse
            import io
            
            try:
                # 直接使用UTF-8解码，因为SRT文件应该是UTF-8编码的
                try:
                    logger.info("尝试UTF-8解码SRT内容")
                    text_content = content.decode('utf-8')
                    # 检查是否已经包含BOM，如果包含则直接使用，否则添加
                    if text_content.startswith('\ufeff'):
                        utf8_content = text_content.encode('utf-8')
                        logger.info("SRT内容已包含BOM")
                    else:
                        utf8_content = text_content.encode('utf-8-sig')  # 带BOM的UTF-8
                        logger.info("添加UTF-8 BOM到SRT内容")
                    logger.info(f"成功解码UTF-8内容，长度: {len(text_content)} 字符")
                except UnicodeDecodeError as e:
                    logger.error(f"UTF-8解码失败，尝试GBK: {str(e)}")
                    try:
                        text_content = content.decode('gbk')
                        utf8_content = text_content.encode('utf-8-sig')
                        logger.info("使用GBK解码成功")
                    except UnicodeDecodeError as e2:
                        logger.error(f"GBK解码也失败，使用Latin-1: {str(e2)}")
                        text_content = content.decode('latin-1')
                        utf8_content = text_content.encode('utf-8-sig')
                        logger.info("使用Latin-1解码作为最后手段")
                
                # 安全处理文件名中的特殊字符 - 使用URL编码处理中文
                import urllib.parse
                safe_filename = urllib.parse.quote(video.title.replace(' ', '_').replace('/', '_').replace('\\', '_'), safe='')
                
                logger.info(f"准备返回SRT文件, 内容长度: {len(utf8_content)} 字节")
                
                return StreamingResponse(
                    io.BytesIO(utf8_content),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}.srt",
                        "Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-cache",
                    }
                )
                
            except UnicodeDecodeError as e:
                logger.error(f"Unicode解码错误: {str(e)}")
                # 如果解码失败，尝试用更宽松的方式处理
                text_content = content.decode('utf-8', errors='replace')
                utf8_content = text_content.encode('utf-8-sig')
                
                import urllib.parse
                safe_filename = urllib.parse.quote(video.title.replace(' ', '_').replace('/', '_').replace('\\', '_'), safe='')
                
                return StreamingResponse(
                    io.BytesIO(utf8_content),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}.srt",
                        "Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-cache",
                    }
                )
            except Exception as e:
                logger.error(f"SRT内容处理错误: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"从MinIO获取文件错误: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read SRT content: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SRT下载处理错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}"
        )

@router.get("/{video_id}/srt-content")
async def get_srt_content(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取SRT字幕文件内容用于预览"""
    
    # 验证视频属于当前用户
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
    
    # 构建SRT文件对象名称
    srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(srt_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT file not found"
        )
    
    # 获取文件内容
    try:
        response = minio_service.internal_client.get_object(
            settings.minio_bucket_name, 
            srt_object_name
        )
        content_bytes = response.read()
        response.close()
        response.release_conn()
        
        # 尝试多种编码解码字节内容
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode('gbk')
                except UnicodeDecodeError:
                    content = content_bytes.decode('latin-1')
        
        # 解析SRT内容
        import re
        subtitles = []
        
        # 按字幕块分割
        blocks = re.split(r'\n\s*\n', content.strip())
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                subtitle = {
                    'id': lines[0],
                    'time': lines[1],
                    'text': '\n'.join(lines[2:])
                }
                subtitles.append(subtitle)
        
        return {
            "content": content,
            "subtitles": subtitles,
            "total_subtitles": len(subtitles),
            "file_size": len(content.encode('utf-8'))
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read SRT content: {str(e)}"
        )

@router.get("/{video_id}/progress")
async def get_video_progress(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频下载和处理进度"""
    
    # 检查缓存
    cache_key = f"{current_user.id}_{video_id}"
    current_time = time.time()
    
    if cache_key in progress_cache:
        cached_data, cache_time = progress_cache[cache_key]
        if current_time - cache_time < CACHE_DURATION:
            # 返回缓存数据
            from fastapi.responses import JSONResponse
            response = JSONResponse(content=cached_data)
            response.headers["Cache-Control"] = "public, max-age=5"
            return response
    
    # 验证视频属于当前用户
    stmt = select(Video, Project.name.label('project_name')).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video_with_project = result.first()
    if not video_with_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    video, project_name = video_with_project
    
    # 获取相关的处理任务
    stmt = select(ProcessingTask).where(
        ProcessingTask.video_id == video_id
    ).order_by(ProcessingTask.created_at.desc())
    result = await db.execute(stmt)
    processing_tasks = result.scalars().all()
    
    # 构建进度信息
    progress_info = {
        'video_id': video.id,
        'title': video.title,
        'status': video.status,
        'download_progress': video.download_progress,
        'processing_progress': video.processing_progress,
        'processing_stage': video.processing_stage,
        'processing_message': video.processing_message,
        'processing_error': video.processing_error,
        'file_size': video.file_size,
        'duration': video.duration,
        'created_at': video.created_at,
        'updated_at': video.updated_at,
        'project_name': project_name,
        'processing_tasks': [
            {
                'id': task.id,
                'task_type': task.task_type,
                'status': task.status,
                'progress': task.progress,
                'stage': task.stage,
                'message': task.message,
                'error_message': task.error_message,
                'created_at': task.created_at,
                'updated_at': task.updated_at,
                'is_completed': task.is_completed
            }
            for task in processing_tasks
        ]
    }
    
    # 添加到缓存
    progress_cache[cache_key] = (progress_info, current_time)
    
    # 添加缓存头，减少频繁查询
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=progress_info)
    response.headers["Cache-Control"] = "public, max-age=5"  # 5秒缓存
    return response

@router.get("/{video_id}/processing-status")
async def get_video_processing_status(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的处理状态"""
    try:
        # 验证视频是否存在且属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")
        
        # 获取处理状态
        stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
        result = await db.execute(stmt)
        processing_status = result.scalar_one_or_none()
        
        # 初始化返回数据
        response_data = {
            "extract_audio_status": "pending",
            "extract_audio_progress": 0.0,
            "generate_srt_status": "pending",
            "generate_srt_progress": 0.0,
            "overall_status": "pending",
            "overall_progress": 0.0,
            "current_stage": None
        }
        
        if processing_status:
            response_data.update({
                "extract_audio_status": processing_status.extract_audio_status,
                "extract_audio_progress": processing_status.extract_audio_progress,
                "generate_srt_status": processing_status.generate_srt_status,
                "generate_srt_progress": processing_status.generate_srt_progress,
                "overall_status": processing_status.overall_status,
                "overall_progress": processing_status.overall_progress,
                "current_stage": processing_status.current_stage,
                "updated_at": processing_status.updated_at.isoformat() if processing_status.updated_at else None
            })
        
        # 获取音频时长和SRT字幕条数
        # 从最新的处理任务中获取详细信息
        task_stmt = select(ProcessingTask).where(
            ProcessingTask.video_id == video_id
        ).order_by(ProcessingTask.created_at.desc())
        task_result = await db.execute(task_stmt)
        processing_tasks = task_result.scalars().all()
        
        # 查找音频提取任务和SRT生成任务的输出数据
        for task in processing_tasks:
            if task.task_type == ProcessingTaskType.EXTRACT_AUDIO and task.is_completed:
                # 优先从output_data获取，如果没有则从duration_seconds字段获取
                if task.output_data and isinstance(task.output_data, dict) and task.output_data.get('duration'):
                    response_data["extract_audio_duration"] = task.output_data.get('duration', 0)
                elif task.duration_seconds:
                    response_data["extract_audio_duration"] = task.duration_seconds
                break
        
        for task in processing_tasks:
            if task.task_type == ProcessingTaskType.GENERATE_SRT and task.is_completed:
                # 优先从output_data获取total_segments
                if task.output_data and isinstance(task.output_data, dict) and task.output_data.get('total_segments'):
                    response_data["generate_srt_segments"] = task.output_data.get('total_segments', 0)
                break
        
        # 如果没有从任务输出数据中获取到，尝试从视频的processing_metadata中获取
        if "extract_audio_duration" not in response_data and video.processing_metadata:
            audio_info = video.processing_metadata.get('audio_info', {})
            if isinstance(audio_info, dict) and audio_info.get('duration'):
                response_data["extract_audio_duration"] = audio_info.get('duration', 0)
        
        if "generate_srt_segments" not in response_data and video.processing_metadata:
            srt_info = video.processing_metadata.get('srt_info', {})
            if isinstance(srt_info, dict) and srt_info.get('total_segments'):
                response_data["generate_srt_segments"] = srt_info.get('total_segments', 0)
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取处理状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{video_id}/thumbnail-download-url")
async def get_thumbnail_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取缩略图的预签名下载URL"""
    
    # 验证视频属于当前用户
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
    
    # 如果视频ID为空，返回错误
    if not video.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video URL is empty"
        )
    
    # 从YouTube URL中提取视频ID
    import re
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', video.url)
    if not video_id_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL"
        )
    
    youtube_video_id = video_id_match.group(1)
    
    # 生成缩略图对象名称
    thumbnail_object_name = minio_service.generate_thumbnail_object_name(
        current_user.id, 
        video.project_id, 
        youtube_video_id
    )
    
    # 检查缩略图是否存在
    thumbnail_exists = await minio_service.file_exists(thumbnail_object_name)
    if not thumbnail_exists:
        # 如果缩略图不存在，返回原始YouTube缩略图URL
        if video.thumbnail_url:
            return {"download_url": video.thumbnail_url, "expires_in": expiry, "object_name": None}
        else:
            # 如果也没有原始缩略图，返回默认缩略图
            default_thumbnail = f"https://img.youtube.com/vi/{youtube_video_id}/default.jpg"
            return {"download_url": default_thumbnail, "expires_in": expiry, "object_name": None}
    
    # 生成预签名URL
    url = await minio_service.get_file_url(thumbnail_object_name, expiry)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate thumbnail download URL"
        )
    
    return {"download_url": url, "expires_in": expiry, "object_name": thumbnail_object_name}

@router.get("/{video_id}/video-download")
async def download_video_direct(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """直接下载视频文件，通过后端代理避免MinIO直链问题"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== 视频下载请求开始 ===")
    logger.info(f"用户ID: {current_user.id}, 视频ID: {video_id}")
    
    try:
        # 验证视频属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            logger.error(f"视频未找到: video_id={video_id}, user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        logger.info(f"找到视频: {video.title} (ID: {video.id})")
        
        # 检查视频文件是否存在
        if not video.file_path:
            logger.error(f"视频文件路径为空: video_id={video_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not available"
            )
        
        # 从MinIO获取文件流
        file_stream = await minio_service.get_file_stream(video.file_path)
        if not file_stream:
            logger.error(f"无法从MinIO获取文件流: {video.file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found in storage"
            )
        
        # 获取文件信息
        file_stat = await minio_service.get_file_stat(video.file_path)
        if not file_stat:
            logger.error(f"无法获取文件统计信息: {video.file_path}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get file information"
            )
        
        logger.info(f"开始下载视频文件: {video.file_path}, 大小: {file_stat.size} bytes")
        
        # 返回文件流响应
        from fastapi.responses import StreamingResponse
        import io
        
        # 创建文件流生成器
        async def file_stream_generator():
            try:
                # 分块读取文件
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = await file_stream.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await file_stream.close()
        
        # 确定内容类型
        content_type = "video/mp4"  # 默认
        if video.filename:
            if video.filename.endswith('.webm'):
                content_type = "video/webm"
            elif video.filename.endswith('.mkv'):
                content_type = "video/x-matroska"
            elif video.filename.endswith('.avi'):
                content_type = "video/x-msvideo"
            elif video.filename.endswith('.mov'):
                content_type = "video/quicktime"
        
        # 设置下载文件名
        download_filename = video.filename or f"{video.title}.mp4"
        
        logger.info(f"返回视频文件流: {download_filename}, 内容类型: {content_type}")
        
        return StreamingResponse(
            file_stream_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{download_filename}",
                "Content-Length": str(file_stat.size),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"视频下载失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video download failed: {str(e)}"
        )