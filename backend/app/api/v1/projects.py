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

@router.get("/", response_model=List[ProjectWithStats], summary="获取项目列表", description="获取当前用户的所有项目，支持多种筛选和分页功能", operation_id="list_projects")
async def get_projects(
    status: Optional[str] = Query(None, description="项目状态筛选 (active, completed, archived)"),
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
    """获取项目列表
    
    获取当前用户的所有项目列表，包含每个项目的视频统计信息。支持多种筛选条件和分页。
    
    Args:
        status (Optional[str]): 项目状态筛选，可选值: "active", "completed", "archived"
        search (Optional[str]): 搜索关键词，匹配项目名称或描述
        start_date (Optional[str]): 创建时间起始日期 (格式: YYYY-MM-DD)
        end_date (Optional[str]): 创建时间结束日期 (格式: YYYY-MM-DD)
        min_video_count (Optional[int]): 最小视频数量筛选
        max_video_count (Optional[int]): 最大视频数量筛选
        page (int): 页码，从1开始，默认为1
        page_size (int): 每页项目数量，范围1-100，默认为10
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        List[ProjectWithStats]: 项目列表，每个项目包含视频统计信息
            - id (int): 项目ID
            - name (str): 项目名称
            - description (Optional[str]): 项目描述
            - user_id (int): 用户ID
            - status (str): 项目状态
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            - video_count (int): 视频总数
            - completed_videos (int): 已完成视频数
            - total_slices (int): 总切片数
    
    Examples:
        获取所有项目: GET /api/v1/projects/
        搜索项目: GET /api/v1/projects/?search=测试
        状态筛选: GET /api/v1/projects/?status=active
        分页查询: GET /api/v1/projects/?page=2&page_size=20
    """
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

@router.post("/", response_model=ProjectResponse, summary="创建项目", description="创建一个新的项目", operation_id="create_project")
async def create_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建新项目
    
    创建一个新的项目。每个项目都属于当前用户。
    
    Args:
        project (ProjectCreate): 项目创建信息
            - name (str): 项目名称，必须唯一
            - description (Optional[str]): 项目描述
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        ProjectResponse: 创建成功的项目信息
            - id (int): 项目ID
            - name (str): 项目名称
            - description (Optional[str]): 项目描述
            - user_id (int): 用户ID
            - status (str): 项目状态，默认为"active"
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
    
    Raises:
        HTTPException:
            - 400: 项目名称已存在
            - 422: 请求参数验证失败
    """
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

@router.get("/{project_id}", response_model=ProjectWithStats, operation_id="get_project")
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

@router.put("/{project_id}", response_model=ProjectResponse, summary="更新项目", description="更新指定项目的名称或描述信息", operation_id="update_project")
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新项目
    
    更新指定项目的名称或描述信息。只有项目所有者可以更新项目。
    
    Args:
        project_id (int): 项目ID
        project_update (ProjectUpdate): 项目更新信息
            - name (Optional[str]): 新的项目名称
            - description (Optional[str]): 新的项目描述
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        ProjectResponse: 更新后的项目信息
            - id (int): 项目ID
            - name (str): 项目名称
            - description (Optional[str]): 项目描述
            - user_id (int): 用户ID
            - status (str): 项目状态
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
    
    Raises:
        HTTPException:
            - 404: 项目不存在或无权限访问
            - 422: 请求参数验证失败
    
    Examples:
        更新项目名称: PUT /api/v1/projects/1
        {
            "name": "更新后的项目名称"
        }
    """
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

@router.delete("/{project_id}", summary="删除项目", description="删除指定项目及其关联的所有视频和数据1", operation_id="delete_project")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除项目
    
    删除指定项目及其关联的所有视频和数据。这是一个不可逆操作，请谨慎使用。
    只有项目所有者可以删除项目。
    
    Args:
        project_id (int): 要删除的项目ID
        current_user (User): 当前认证用户依赖
        db (AsyncSession): 数据库会话依赖
    
    Returns:
        dict: 删除成功消息
            - message (str): 删除成功提示信息
    
    Raises:
        HTTPException:
            - 404: 项目不存在或无权限访问
    
    Examples:
        删除项目: DELETE /api/v1/projects/1
    """
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

@router.get("/{project_id}/videos", response_model=List[VideoResponse], operation_id="get_project_videos")
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