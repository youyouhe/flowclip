from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingStatus
from app.schemas.video import VideoResponse, PaginatedVideoResponse
from app.core.config import settings

router = APIRouter()

import logging
logger = logging.getLogger(__name__)


@router.get("/active", response_model=List[VideoResponse], summary="获取活动视频列表", description="获取当前用户所有非完成状态的视频", operation_id="list_active_videos")
async def get_active_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户所有非完成状态的视频
    
    获取当前用户所有非完成状态的视频列表，按创建时间倒序排列。包括正在下载、处理中的视频。
    
    Args:
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        List[VideoResponse]: 视频列表
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
    
    Examples:
        获取活动视频: GET /api/v1/videos/active
    """
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


@router.get("/", response_model=PaginatedVideoResponse, summary="获取视频列表", description="获取当前用户的所有视频，支持多种筛选和分页功能", operation_id="list_videos")
async def get_videos(
    project_id: Optional[int] = Query(None, description="项目ID筛选"),
    status: Optional[str] = Query(None, description="视频状态筛选 (pending, downloading, downloaded, processing, completed, failed)"),
    srt_processed: Optional[bool] = Query(None, description="SRT处理是否完成"),
    search: Optional[str] = Query(None, description="搜索视频标题或描述"),
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
    """获取当前用户的所有视频（支持筛选功能）
    
    获取当前用户的所有视频列表，支持多种筛选条件和分页功能。
    
    Args:
        project_id (Optional[int]): 项目ID筛选
        status (Optional[str]): 视频状态筛选，可选值: "pending", "downloading", "downloaded", "processing", "completed", "failed"
        srt_processed (Optional[bool]): SRT处理是否完成筛选
        search (Optional[str]): 搜索关键词，匹配视频标题或描述
        start_date (Optional[str]): 创建时间起始日期 (格式: YYYY-MM-DD)
        end_date (Optional[str]): 创建时间结束日期 (格式: YYYY-MM-DD)
        min_duration (Optional[int]): 最小时长筛选（秒）
        max_duration (Optional[int]): 最大时长筛选（秒）
        min_file_size (Optional[int]): 最小文件大小筛选（字节）
        max_file_size (Optional[int]): 最大文件大小筛选（字节）
        page (int): 页码，从1开始，默认为1
        page_size (int): 每页视频数量，范围1-100，默认为10
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        PaginatedVideoResponse: 分页视频列表响应
            - videos (List[VideoResponse]): 视频列表
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
            - pagination (dict): 分页信息
                - page (int): 当前页码
                - page_size (int): 每页数量
                - total (int): 总记录数
                - total_pages (int): 总页数
            - total (int): 总记录数
    
    Examples:
        获取所有视频: GET /api/v1/videos/
        搜索视频: GET /api/v1/videos/?search=测试
        状态筛选: GET /api/v1/videos/?status=completed
        分页查询: GET /api/v1/videos/?page=2&page_size=20
    """
    from app.core.constants import ProcessingTaskType
    from app.models.processing_task import ProcessingTask
    
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


@router.get("/{video_id}", response_model=VideoResponse, operation_id="get_video")
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


@router.delete("/{video_id}", operation_id="delete_video")
async def delete_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除视频及相关文件"""
    from app.services.minio_client import minio_service
    from app.models import VideoSlice, VideoSubSlice
    
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


@router.put("/{video_id}", response_model=VideoResponse, operation_id="update_video")
async def update_video(
    video_id: int,
    video_update: VideoResponse,  # 注意：这里应该是VideoUpdate而不是VideoResponse
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