from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Dict, Any
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.constants import ProcessingTaskType
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask, ProcessingTaskLog, ProcessingStatus
from app.models.video_slice import VideoSlice
from app.services.state_manager import get_state_manager
from app.schemas.processing import (
    ProcessingTaskResponse,
    ProcessingStatusResponse,
    ProcessingTaskLogResponse,
    TaskStatusResponse,
    VideoProcessingStatusResponse
)

router = APIRouter(tags=["status"])

@router.get("/videos/{video_id}", response_model=VideoProcessingStatusResponse)
async def get_video_processing_status(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的完整处理状态"""
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
        ProcessingTask.video_id == video_id
    ).order_by(ProcessingTask.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    # 获取整体状态
    state_manager = get_state_manager(db)
    overall_status = await state_manager.get_video_status(video_id)
    
    return {
        "video_id": video.id,
        "title": video.title,
        "status": video.status,
        "processing_stage": video.processing_stage,
        "processing_progress": video.processing_progress,
        "processing_message": video.processing_message,
        "processing_error": video.processing_error,
        "processing_started_at": video.processing_started_at,
        "processing_completed_at": video.processing_completed_at,
        "tasks": list(tasks),
        "overall_status": overall_status or {}
    }

@router.get("/tasks/{task_id}", response_model=ProcessingTaskResponse)
async def get_processing_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取处理任务详情"""
    stmt = select(ProcessingTask).join(Video).join(Project).where(
        ProcessingTask.id == task_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    return task

@router.get("/tasks/{task_id}/logs", response_model=List[ProcessingTaskLogResponse])
async def get_task_logs(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取任务状态变化日志"""
    stmt = select(ProcessingTaskLog).join(ProcessingTask).join(Video).join(Project).where(
        ProcessingTaskLog.task_id == task_id,
        Project.user_id == current_user.id
    ).order_by(ProcessingTaskLog.created_at.desc())
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    return list(logs)

@router.get("/videos/{video_id}/tasks", response_model=List[ProcessingTaskResponse])
async def get_video_tasks(
    video_id: int,
    task_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的所有处理任务"""
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
    
    # 构建查询
    stmt = select(ProcessingTask).where(ProcessingTask.video_id == video_id)
    
    if task_type:
        stmt = stmt.where(ProcessingTask.task_type == task_type)
    
    stmt = stmt.order_by(ProcessingTask.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    return list(tasks)

@router.get("/celery/{celery_task_id}", response_model=TaskStatusResponse)
async def get_celery_task_status(
    celery_task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取Celery任务状态"""
    from celery.result import AsyncResult
    
    task_result = AsyncResult(celery_task_id)
    
    # 获取对应的处理任务
    stmt = select(ProcessingTask).where(
        ProcessingTask.celery_task_id == celery_task_id
    )
    result = await db.execute(stmt)
    processing_task = result.scalar_one_or_none()
    
    if not processing_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    # 验证权限
    stmt = select(Video).join(Project).where(
        Video.id == processing_task.video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # 构建响应
    return {
        "task_id": celery_task_id,
        "status": task_result.status,
        "progress": processing_task.progress,
        "stage": processing_task.stage,
        "stage_description": processing_task.stage_description,
        "message": processing_task.message,
        "error": processing_task.error_message,
        "result": task_result.result if task_result.ready() else None
    }

@router.post("/videos/{video_id}/reset")
async def reset_video_status(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重置视频处理状态"""
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
    
    # 重置状态
    state_manager = get_state_manager(db)
    await state_manager.reset_video_status(video_id)
    
    return {"message": "Video processing status reset successfully"}

@router.get("/videos/{video_id}/status/summary", response_model=ProcessingStatusResponse)
async def get_video_status_summary(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频状态摘要"""
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
    
    # 获取状态记录
    stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
    result = await db.execute(stmt)
    status_record = result.scalar_one_or_none()
    
    if not status_record:
        # 初始化状态记录
        state_manager = get_state_manager(db)
        status_record = await state_manager.initialize_video_status(video_id)
    
    return {
        "video_id": video_id,
        "overall_status": status_record.overall_status,
        "overall_progress": status_record.overall_progress,
        "current_stage": status_record.current_stage,
        "download": {
            "status": status_record.download_status,
            "progress": status_record.download_progress
        },
        "extract_audio": {
            "status": status_record.extract_audio_status,
            "progress": status_record.extract_audio_progress
        },
        "split_audio": {
            "status": status_record.split_audio_status,
            "progress": status_record.split_audio_progress
        },
        "generate_srt": {
            "status": status_record.generate_srt_status,
            "progress": status_record.generate_srt_progress
        },
        "error_count": status_record.error_count,
        "last_error": status_record.last_error
    }

@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取仪表盘统计数据"""
    
    # 获取用户的项目总数
    project_count = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == current_user.id)
    )
    total_projects = project_count.scalar() or 0
    
    # 获取用户的视频统计
    video_stats = await db.execute(
        select(
            Video.status,
            func.count(Video.id).label('count')
        ).join(Project).where(
            Project.user_id == current_user.id
        ).group_by(Video.status)
    )
    
    video_counts = {row.status: row.count for row in video_stats.fetchall()}
    total_videos = sum(video_counts.values())
    completed_videos = video_counts.get('completed', 0)
    processing_videos = video_counts.get('downloading', 0) + video_counts.get('processing', 0)
    
    # 获取用户的切片总数
    slice_count = await db.execute(
        select(func.count(VideoSlice.id)).join(Video).join(Project).where(
            Project.user_id == current_user.id
        )
    )
    total_slices = slice_count.scalar() or 0
    
    # 获取最近的项目
    recent_projects = await db.execute(
        select(Project).where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc()).limit(5)
    )
    recent_projects_data = []
    for project in recent_projects.scalars().all():
        # 获取项目的视频数量
        video_count_result = await db.execute(
            select(func.count(Video.id)).where(Video.project_id == project.id)
        )
        video_count = video_count_result.scalar() or 0
        
        recent_projects_data.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at,
            "video_count": video_count
        })
    
    # 获取最近的处理任务
    recent_tasks = await db.execute(
        select(ProcessingTask, Video.title).join(Video).join(Project).where(
            Project.user_id == current_user.id
        ).order_by(ProcessingTask.created_at.desc()).limit(10)
    )
    
    recent_activities = []
    for task, video_title in recent_tasks:
        activity = {
            "id": task.id,
            "type": task.task_type,
            "status": task.status,
            "task_name": task.task_name,
            "video_title": video_title or "Unknown",
            "progress": task.progress,
            "created_at": task.created_at,
            "message": task.message,
            "error_message": task.error_message
        }
        recent_activities.append(activity)
    
    # 获取处理任务统计
    task_stats = await db.execute(
        select(
            ProcessingTask.status,
            func.count(ProcessingTask.id).label('count')
        ).join(Video).join(Project).where(
            Project.user_id == current_user.id
        ).group_by(ProcessingTask.status)
    )
    
    task_counts = {row.status: row.count for row in task_stats.fetchall()}
    
    return {
        "overview": {
            "total_projects": total_projects,
            "total_videos": total_videos,
            "completed_videos": completed_videos,
            "processing_videos": processing_videos,
            "total_slices": total_slices,
            "failed_videos": video_counts.get('failed', 0)
        },
        "task_stats": {
            "pending": task_counts.get('pending', 0),
            "running": task_counts.get('running', 0),
            "success": task_counts.get('success', 0),
            "failure": task_counts.get('failure', 0)
        },
        "recent_projects": recent_projects_data,
        "recent_activities": recent_activities
    }

@router.get("/videos/running", response_model=List[int])
async def get_running_video_ids(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取所有正在运行的视频IDs"""
    # 获取所有有运行中任务的视频
    stmt = select(Video.id).join(Project).join(ProcessingTask).where(
        Project.user_id == current_user.id,
        ProcessingTask.status.in_(['pending', 'running'])
    ).distinct()
    
    result = await db.execute(stmt)
    running_video_ids = [row[0] for row in result.fetchall()]
    
    return running_video_ids