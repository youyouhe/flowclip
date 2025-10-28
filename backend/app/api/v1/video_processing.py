from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask, ProcessingStatus
from app.core.constants import ProcessingTaskType
from app.core.celery import celery_app
from app.services.state_manager import get_state_manager

router = APIRouter()

import logging
logger = logging.getLogger(__name__)


@router.post("/{video_id}/extract-audio", summary="提取视频音频", description="从指定视频中提取音频文件", operation_id="extract_audio")
async def extract_audio_endpoint(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """提取视频音频
    
    从指定视频中提取音频文件，生成WAV格式的音频文件并存储到MinIO中。
    
    Args:
        video_id (int): 视频ID
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        dict: 音频提取任务信息
            - task_id (str): CeleryTaskID
            - processing_task_id (int): 处理TaskID
            - message (str): 任务启动消息
            - status (str): 任务状态
    
    Raises:
        HTTPException:
            - 404: 视频不存在或无权限访问
            - 400: 视频文件不可用
            - 500: 启动音频提取任务失败
    
    Examples:
        提取音频: POST /api/v1/videos/1/extract-audio
    """
    from app.services.minio_client import minio_service
    
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
        
        # 创建处理任务记录，使用实际的CeleryTaskID
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


@router.post("/{video_id}/generate-srt", summary="生成SRT字幕文件", description="为指定视频生成SRT字幕文件", operation_id="generate_srt")
async def generate_srt_endpoint(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """生成SRT字幕文件
    
    为指定视频生成SRT字幕文件，使用ASR服务进行语音识别并生成字幕。
    
    Args:
        video_id (int): 视频ID
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        dict: 字幕生成任务信息
            - task_id (str): CeleryTaskID
            - processing_task_id (int): 处理TaskID
            - message (str): 任务启动消息
            - status (str): 任务状态
    
    Raises:
        HTTPException:
            - 404: 视频不存在或无权限访问
            - 500: 启动字幕生成任务失败
    
    Examples:
        生成字幕: POST /api/v1/videos/1/generate-srt
    """
    logger.info(f"Start Generating Subtitles - video_id: {video_id}, user_id: {current_user.id}")
    
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
    logger.info(f"准备发送Celery任务 - video_id: {video.id}, project_id: {video.project_id}, user_id: {current_user.id}")
    task = celery_app.send_task('app.tasks.video_tasks.generate_srt', 
        args=[str(video.id), video.project_id, current_user.id]  # 移除split_files参数
    )
    logger.info(f"Celery任务已发送 - task_id: {task.id}")
    
    # 创建处理任务记录，使用实际的CeleryTaskID
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


@router.get("/{video_id}/task-status/{task_id}", operation_id="get_task_status")
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


@router.get("/{video_id}/processing-status", operation_id="get_processing_status")
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