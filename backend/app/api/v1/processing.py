from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask, ProcessingTaskLog
from app.schemas.processing import ProcessingTaskLogResponse, ProcessingTaskResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# === 日志管理 API 端点 ===

@router.get("/logs", response_model=Dict[str, Any])
async def get_processing_logs(
    video_id: Optional[int] = Query(None, description="视频ID过滤"),
    task_id: Optional[int] = Query(None, description="任务ID过滤"),
    task_type: Optional[str] = Query(None, description="任务类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    level: Optional[str] = Query("INFO", description="日志级别过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=1000, description="每页大小"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取处理任务日志列表"""
    
    try:
        # 构建查询条件
        query_conditions = []
        
        # 如果指定了video_id，需要验证权限
        if video_id:
            # 验证视频权限
            stmt = select(Video).join(Project).where(
                Video.id == video_id,
                Project.user_id == current_user.id
            )
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="视频不存在或无权限访问"
                )
            
            query_conditions.append(ProcessingTask.video_id == video_id)
        
        # 如果没有指定video_id，获取用户所有视频的日志
        else:
            # 获取用户的所有视频ID
            stmt = select(Video.id).join(Project).where(
                Project.user_id == current_user.id
            )
            result = await db.execute(stmt)
            video_ids = [row[0] for row in result.fetchall()]
            
            if video_ids:
                query_conditions.append(ProcessingTask.video_id.in_(video_ids))
        
        # 任务ID过滤
        if task_id:
            query_conditions.append(ProcessingTaskLog.task_id == task_id)
        
        # 任务类型过滤
        if task_type:
            query_conditions.append(ProcessingTask.task_type == task_type)
        
        # 状态过滤
        if status:
            query_conditions.append(ProcessingTaskLog.new_status == status)
        
        # 时间范围过滤
        if start_date:
            query_conditions.append(ProcessingTaskLog.created_at >= start_date)
        if end_date:
            query_conditions.append(ProcessingTaskLog.created_at <= end_date)
        
        # 搜索过滤
        if search:
            search_conditions = or_(
                ProcessingTaskLog.message.ilike(f"%{search}%"),
                ProcessingTaskLog.details.ilike(f"%{search}%"),
                ProcessingTask.task_name.ilike(f"%{search}%")
            )
            query_conditions.append(search_conditions)
        
        # 构建基础查询
        base_query = select(
            ProcessingTaskLog,
            ProcessingTask.task_name,
            ProcessingTask.task_type,
            ProcessingTask.video_id,
            Video.title.label("video_title")
        ).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        ).join(
            Video,
            ProcessingTask.video_id == Video.id
        )
        
        # 应用查询条件
        if query_conditions:
            base_query = base_query.where(and_(*query_conditions))
        
        # 获取总数
        count_query = select(func.count(ProcessingTaskLog.id)).select_from(
            ProcessingTaskLog
        ).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        )
        
        if query_conditions:
            count_query = count_query.where(and_(*query_conditions))
        
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # 分页查询
        offset = (page - 1) * page_size
        logs_query = base_query.order_by(
            ProcessingTaskLog.created_at.desc()
        ).offset(offset).limit(page_size)
        
        result = await db.execute(logs_query)
        logs_data = result.fetchall()
        
        # 转换结果
        logs = []
        for row in logs_data:
            log = row[0]
            logs.append({
                "id": log.id,
                "task_id": log.task_id,
                "task_name": row.task_name,
                "task_type": row.task_type,
                "video_id": row.video_id,
                "video_title": row.video_title,
                "old_status": log.old_status,
                "new_status": log.new_status,
                "message": log.message,
                "details": log.details,
                "created_at": log.created_at,
                "level": log.details.get("level", "INFO") if log.details else "INFO"
            })
        
        return {
            "logs": logs,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            },
            "filters": {
                "video_id": video_id,
                "task_id": task_id,
                "task_type": task_type,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "level": level,
                "search": search
            }
        }
        
    except Exception as e:
        logger.error(f"获取处理日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日志失败: {str(e)}"
        )

@router.get("/logs/task/{task_id}", response_model=List[ProcessingTaskLogResponse])
async def get_task_logs(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取特定任务的所有日志"""
    
    try:
        # 验证任务权限
        stmt = select(ProcessingTask).join(Video).join(Project).where(
            ProcessingTask.id == task_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权限访问"
            )
        
        # 获取任务日志
        stmt = select(ProcessingTaskLog).where(
            ProcessingTaskLog.task_id == task_id
        ).order_by(ProcessingTaskLog.created_at.desc())
        
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        return logs
        
    except Exception as e:
        logger.error(f"获取任务日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务日志失败: {str(e)}"
        )

@router.get("/logs/video/{video_id}", response_model=Dict[str, Any])
async def get_video_logs_summary(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的日志汇总"""
    
    try:
        # 验证视频权限
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="视频不存在或无权限访问"
            )
        
        # 获取任务统计
        stmt = select(
            ProcessingTask.task_type,
            ProcessingTask.status,
            func.count(ProcessingTask.id).label("count"),
            func.max(ProcessingTask.updated_at).label("last_updated")
        ).where(
            ProcessingTask.video_id == video_id
        ).group_by(
            ProcessingTask.task_type,
            ProcessingTask.status
        )
        
        result = await db.execute(stmt)
        task_stats = result.fetchall()
        
        # 获取最近的日志
        stmt = select(
            ProcessingTaskLog,
            ProcessingTask.task_name,
            ProcessingTask.task_type
        ).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        ).where(
            ProcessingTask.video_id == video_id
        ).order_by(
            ProcessingTaskLog.created_at.desc()
        ).limit(50)
        
        result = await db.execute(stmt)
        recent_logs = result.fetchall()
        
        # 构建汇总数据
        summary = {
            "video_id": video_id,
            "video_title": video.title,
            "task_statistics": [
                {
                    "task_type": row.task_type,
                    "status": row.status,
                    "count": row.count,
                    "last_updated": row.last_updated
                }
                for row in task_stats
            ],
            "recent_logs": [
                {
                    "id": log.id,
                    "task_id": log.task_id,
                    "task_name": task_name,
                    "task_type": task_type,
                    "old_status": log.old_status,
                    "new_status": log.new_status,
                    "message": log.message,
                    "details": log.details,
                    "created_at": log.created_at
                }
                for log, task_name, task_type in recent_logs
            ]
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"获取视频日志汇总失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日志汇总失败: {str(e)}"
        )

@router.delete("/logs/{log_id}")
async def delete_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除特定日志"""
    
    try:
        # 验证日志权限
        stmt = select(ProcessingTaskLog).join(ProcessingTask).join(Video).join(Project).where(
            ProcessingTaskLog.id == log_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        log = result.scalar_one_or_none()
        
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="日志不存在或无权限访问"
            )
        
        # 删除日志
        await db.delete(log)
        await db.commit()
        
        return {"message": "日志删除成功"}
        
    except Exception as e:
        logger.error(f"删除日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除日志失败: {str(e)}"
        )

@router.delete("/logs/task/{task_id}")
async def delete_task_logs(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除任务的所有日志"""
    
    try:
        # 验证任务权限
        stmt = select(ProcessingTask).join(Video).join(Project).where(
            ProcessingTask.id == task_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在或无权限访问"
            )
        
        # 删除任务的所有日志
        stmt = select(ProcessingTaskLog).where(
            ProcessingTaskLog.task_id == task_id
        )
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        for log in logs:
            await db.delete(log)
        
        await db.commit()
        
        return {"message": f"已删除 {len(logs)} 条日志"}
        
    except Exception as e:
        logger.error(f"删除任务日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除任务日志失败: {str(e)}"
        )

@router.delete("/logs/video/{video_id}")
async def delete_video_logs(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除视频的所有日志"""
    
    try:
        # 验证视频权限
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="视频不存在或无权限访问"
            )
        
        # 获取视频的所有任务ID
        stmt = select(ProcessingTask.id).where(
            ProcessingTask.video_id == video_id
        )
        result = await db.execute(stmt)
        task_ids = [row[0] for row in result.fetchall()]
        
        # 删除所有相关日志
        if task_ids:
            stmt = select(ProcessingTaskLog).where(
                ProcessingTaskLog.task_id.in_(task_ids)
            )
            result = await db.execute(stmt)
            logs = result.scalars().all()
            
            for log in logs:
                await db.delete(log)
        
        await db.commit()
        
        return {"message": f"已删除视频 {video_id} 的所有日志"}
        
    except Exception as e:
        logger.error(f"删除视频日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除视频日志失败: {str(e)}"
        )

@router.get("/logs/statistics", response_model=Dict[str, Any])
async def get_logs_statistics(
    video_id: Optional[int] = Query(None, description="视频ID过滤"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取日志统计信息"""
    
    try:
        # 构建查询条件
        query_conditions = []
        
        # 如果指定了video_id，需要验证权限
        if video_id:
            # 验证视频权限
            stmt = select(Video).join(Project).where(
                Video.id == video_id,
                Project.user_id == current_user.id
            )
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="视频不存在或无权限访问"
                )
            
            query_conditions.append(ProcessingTask.video_id == video_id)
        
        # 如果没有指定video_id，获取用户所有视频的统计
        else:
            # 获取用户的所有视频ID
            stmt = select(Video.id).join(Project).where(
                Project.user_id == current_user.id
            )
            result = await db.execute(stmt)
            video_ids = [row[0] for row in result.fetchall()]
            
            if video_ids:
                query_conditions.append(ProcessingTask.video_id.in_(video_ids))
        
        # 时间范围过滤
        if start_date:
            query_conditions.append(ProcessingTaskLog.created_at >= start_date)
        if end_date:
            query_conditions.append(ProcessingTaskLog.created_at <= end_date)
        
        # 获取日志统计
        base_query = select(ProcessingTaskLog).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        )
        
        if query_conditions:
            base_query = base_query.where(and_(*query_conditions))
        
        # 按状态统计
        status_stats_query = select(
            ProcessingTaskLog.new_status,
            func.count(ProcessingTaskLog.id).label("count")
        ).select_from(
            ProcessingTaskLog
        ).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        )
        
        if query_conditions:
            status_stats_query = status_stats_query.where(and_(*query_conditions))
        
        status_stats_query = status_stats_query.group_by(ProcessingTaskLog.new_status)
        
        result = await db.execute(status_stats_query)
        status_stats = result.fetchall()
        
        # 按任务类型统计
        type_stats_query = select(
            ProcessingTask.task_type,
            func.count(ProcessingTaskLog.id).label("count")
        ).select_from(
            ProcessingTaskLog
        ).join(
            ProcessingTask,
            ProcessingTaskLog.task_id == ProcessingTask.id
        )
        
        if query_conditions:
            type_stats_query = type_stats_query.where(and_(*query_conditions))
        
        type_stats_query = type_stats_query.group_by(ProcessingTask.task_type)
        
        result = await db.execute(type_stats_query)
        type_stats = result.fetchall()
        
        # 按日期统计（最近7天）
        date_stats = []
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            next_date = date + timedelta(days=1)
            
            date_query = select(func.count(ProcessingTaskLog.id)).select_from(
                ProcessingTaskLog
            ).join(
                ProcessingTask,
                ProcessingTaskLog.task_id == ProcessingTask.id
            ).where(
                ProcessingTaskLog.created_at >= date,
                ProcessingTaskLog.created_at < next_date
            )
            
            if query_conditions:
                date_query = date_query.where(and_(*query_conditions))
            
            result = await db.execute(date_query)
            count = result.scalar()
            
            date_stats.append({
                "date": date.strftime("%Y-%m-%d"),
                "count": count
            })
        
        return {
            "statistics": {
                "by_status": [
                    {"status": row.new_status, "count": row.count}
                    for row in status_stats
                ],
                "by_task_type": [
                    {"task_type": row.task_type, "count": row.count}
                    for row in type_stats
                ],
                "by_date": date_stats,
                "total_logs": sum(row.count for row in status_stats)
            },
            "filters": {
                "video_id": video_id,
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
    except Exception as e:
        logger.error(f"获取日志统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取日志统计失败: {str(e)}"
        )