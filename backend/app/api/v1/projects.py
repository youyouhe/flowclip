from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, cast, Date
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.video import Video
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectWithStats
from app.schemas.video import VideoResponse

router = APIRouter()

@router.get("/", response_model=List[ProjectWithStats])
async def get_projects(
    status: Optional[str] = Query(None, description="项目状态筛选"),
    search: Optional[str] = Query(None, description="搜索项目名称或描述"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    min_video_count: Optional[int] = Query(None, description="最小视频数量"),
    max_video_count: Optional[int] = Query(None, description="最大视频数量"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的所有项目（包含视频统计和筛选功能）"""
    # 构建基础查询
    stmt = select(Project).where(Project.user_id == current_user.id)
    
    # 添加筛选条件
    if status:
        stmt = stmt.where(Project.status == status)
    
    if search:
        stmt = stmt.where(
            or_(
                Project.name.ilike(f"%{search}%"),
                Project.description.ilike(f"%{search}%")
            )
        )
    
    if start_date:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        stmt = stmt.where(Project.created_at >= start_datetime)
    
    if end_date:
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        stmt = stmt.where(Project.created_at <= end_datetime)
    
    # 获取总数
    count_stmt = select(func.count(Project.id)).where(Project.user_id == current_user.id)
    if status:
        count_stmt = count_stmt.where(Project.status == status)
    if search:
        count_stmt = count_stmt.where(
            or_(
                Project.name.ilike(f"%{search}%"),
                Project.description.ilike(f"%{search}%")
            )
        )
    if start_date:
        count_stmt = count_stmt.where(Project.created_at >= start_datetime)
    if end_date:
        count_stmt = count_stmt.where(Project.created_at <= end_datetime)
    
    count_result = await db.execute(count_stmt)
    total_count = count_result.scalar()
    
    # 添加分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    stmt = stmt.order_by(Project.created_at.desc())
    
    result = await db.execute(stmt)
    projects = result.scalars().all()
    
    # 为每个项目添加视频统计
    projects_with_stats = []
    for project in projects:
        # 统计视频数量
        video_count_stmt = select(func.count(Video.id)).where(Video.project_id == project.id)
        video_count_result = await db.execute(video_count_stmt)
        video_count = video_count_result.scalar()
        
        # 统计已完成视频数量
        completed_videos_stmt = select(func.count(Video.id)).where(
            Video.project_id == project.id,
            Video.status == "completed"
        )
        completed_videos_result = await db.execute(completed_videos_stmt)
        completed_videos = completed_videos_result.scalar()
        
        # 创建带统计信息的项目对象
        project_with_stats = ProjectWithStats(
            id=project.id,
            name=project.name,
            description=project.description,
            user_id=project.user_id,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
            video_count=video_count,
            completed_videos=completed_videos,
            total_slices=0  # 暂时设为0，后续可以添加切片统计
        )
        
        # 应用视频数量筛选
        if min_video_count is not None and video_count < min_video_count:
            continue
        if max_video_count is not None and video_count > max_video_count:
            continue
            
        projects_with_stats.append(project_with_stats)
    
    # 构建分页信息
    pagination = {
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": (total_count + page_size - 1) // page_size
    }
    
    return projects_with_stats

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新项目"""
    new_project = Project(
        name=project.name,
        description=project.description,
        user_id=current_user.id,
        status="active"
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project

@router.get("/{project_id}", response_model=ProjectWithStats)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取特定项目详情（包含视频统计）"""
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
    
    # 统计视频数量
    video_count_stmt = select(func.count(Video.id)).where(Video.project_id == project.id)
    video_count_result = await db.execute(video_count_stmt)
    video_count = video_count_result.scalar()
    
    # 统计已完成视频数量
    completed_videos_stmt = select(func.count(Video.id)).where(
        Video.project_id == project.id,
        Video.status == "completed"
    )
    completed_videos_result = await db.execute(completed_videos_stmt)
    completed_videos = completed_videos_result.scalar()
    
    # 创建带统计信息的项目对象
    project_with_stats = ProjectWithStats(
        id=project.id,
        name=project.name,
        description=project.description,
        user_id=project.user_id,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        video_count=video_count,
        completed_videos=completed_videos,
        total_slices=0  # 暂时设为0，后续可以添加切片统计
    )
    
    return project_with_stats

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新项目"""
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
    
    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description
    
    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除项目"""
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
    
    await db.delete(project)
    await db.commit()
    return {"message": "Project deleted successfully"}

@router.get("/{project_id}/videos", response_model=List[VideoResponse])
async def get_project_videos(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目内的所有视频"""
    # 验证项目所有权
    project_stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # 获取项目内的视频列表
    videos_stmt = select(Video).where(Video.project_id == project_id).order_by(Video.created_at.desc())
    videos_result = await db.execute(videos_stmt)
    videos = videos_result.scalars().all()
    
    return list(videos)