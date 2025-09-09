from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, and_, insert
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.models.resource import Resource, ResourceTag, resource_tags_mapping
from app.schemas.resource import Resource as ResourceSchema, ResourceCreate, ResourceUpdate, ResourceQuery, ResourceSearchResult
from fastapi import Depends
from app.core.security import get_current_user, oauth2_scheme
from app.models.user import User
from app.services.minio_client import MinioService
from app.core.config import settings
import os
import uuid
from datetime import datetime

class ResourceTagCreate(BaseModel):
    """资源标签创建请求模型"""
    name: str = Field(..., description="标签名，必须唯一")
    tag_type: str = Field(..., pattern="^(audio|video|image|general)$", description="标签类型，可选值：audio, video, image, general")
    description: Optional[str] = Field(None, description="标签描述")

router = APIRouter(tags=["resources"])

# 全局 MinIO 服务实例
_minio_service = None

def get_minio_service():
    global _minio_service
    if _minio_service is None:
        _minio_service = MinioService()
    return _minio_service

# ==================== 标签管理端点 ====================

@router.get("/tags",
    summary="获取资源标签列表",
    description="获取资源标签列表，支持分页、类型过滤和激活状态过滤。",
    responses={
        200: {
            "description": "成功返回资源标签列表",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "name": "示例标签",
                            "tag_type": "general"
                        }
                    ]
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
)
async def get_resource_tags(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数，最大1000"),
    tag_type: Optional[str] = Query(None, pattern="^(audio|video|image|general)$", description="标签类型过滤"),
    is_active: Optional[bool] = Query(None, description="激活状态过滤"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取资源标签列表
    
    获取资源标签列表，支持分页、类型过滤和激活状态过滤。
    
    Args:
        skip (int): 跳过的记录数，默认为0
        limit (int): 返回的记录数，默认为100，最大1000
        tag_type (Optional[str]): 标签类型过滤，可选值：audio, video, image, general
        is_active (Optional[bool]): 激活状态过滤
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        List[dict]: 资源标签列表
            - id (int): 标签ID
            - name (str): 标签名
            - tag_type (str): 标签类型
            
    Raises:
        HTTPException:
            - 500: 当获取标签列表失败时
    """
    query = select(ResourceTag)
    
    # 添加过滤条件
    if tag_type:
        query = query.where(ResourceTag.tag_type == tag_type)
    if is_active is not None:
        query = query.where(ResourceTag.is_active == is_active)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    tags = result.scalars().all()
    
    result = [{"id": tag.id, "name": tag.name, "tag_type": tag.tag_type} for tag in tags]
    print(f"🏷️ Returning {len(result)} tags:", result)
    return result

@router.post("/tags",
    summary="创建资源标签",
    description="创建一个新的资源标签。标签名必须唯一，不能与现有标签重复。",
    responses={
        200: {
            "description": "成功创建资源标签",
            "content": {
                "application/json": {
                    "example": {
                        "message": "标签创建成功",
                        "tag": {
                            "id": 1,
                            "name": "示例标签",
                            "tag_type": "general"
                        }
                    }
                }
            }
        },
        400: {"description": "标签名已存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def create_resource_tag(
    tag_data: ResourceTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建资源标签
    
    创建一个新的资源标签。标签名必须唯一，不能与现有标签重复。
    
    Args:
        tag_data (ResourceTagCreate): 标签创建数据
            - name (str): 标签名，必须唯一
            - tag_type (str): 标签类型，可选值：audio, video, image, general
            - description (Optional[str]): 标签描述
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 创建结果信息
            - message (str): 创建结果消息
            - tag (dict): 创建的标签信息
                - id (int): 标签ID
                - name (str): 标签名
                - tag_type (str): 标签类型
            
    Raises:
        HTTPException:
            - 400: 当标签名已存在时
            - 500: 当创建标签失败时
    """
    # 检查标签名是否已存在
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.name == tag_data.name)
    )
    existing_tag = result.scalar_one_or_none()
    if existing_tag:
        raise HTTPException(status_code=400, detail="标签名已存在")
    
    # 创建新标签
    db_tag = ResourceTag(
        name=tag_data.name,
        tag_type=tag_data.tag_type,
        description=tag_data.description
    )
    db.add(db_tag)
    await db.commit()
    await db.refresh(db_tag)
    
    return {"message": "标签创建成功", "tag": {"id": db_tag.id, "name": db_tag.name, "tag_type": db_tag.tag_type}}

@router.delete("/tags/{tag_id}",
    summary="删除资源标签",
    description="根据标签ID删除资源标签。该操作为软删除，将标签的is_active状态设置为False。",
    responses={
        200: {
            "description": "成功删除资源标签",
            "content": {
                "application/json": {
                    "example": {
                        "message": "标签删除成功"
                    }
                }
            }
        },
        404: {"description": "标签不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def delete_resource_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除资源标签
    
    根据标签ID删除资源标签。该操作为软删除，将标签的is_active状态设置为False。
    
    Args:
        tag_id (int): 标签ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 删除结果信息
            - message (str): 删除结果消息
            
    Raises:
        HTTPException:
            - 404: 当标签不存在时
            - 500: 当删除标签失败时
    """
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.id == tag_id)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    # 软删除
    tag.is_active = False
    await db.commit()
    
    return {"message": "标签删除成功"}

# ==================== 资源管理端点 ====================

@router.post("/",
    summary="创建资源",
    description="创建一个新的资源记录。",
    responses={
        200: {
            "description": "成功创建资源",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "filename": "example.mp4",
                        "original_filename": "example_video.mp4",
                        "description": "示例视频文件",
                        "is_public": True,
                        "file_path": "global-resources/video/1/example.mp4",
                        "file_size": 1024000,
                        "mime_type": "video/mp4",
                        "file_type": "video",
                        "duration": 120.5,
                        "width": 1920,
                        "height": 1080,
                        "download_count": 0,
                        "view_count": 0,
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-01T00:00:00",
                        "created_by": 1,
                        "tags": []
                    }
                }
            }
        },
        400: {"description": "文件路径已存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def create_resource(
    resource: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建资源
    
    创建一个新的资源记录。
    
    Args:
        resource (ResourceCreate): 资源创建请求数据
            - filename (str): 文件名
            - original_filename (str): 原始文件名
            - description (Optional[str]): 资源描述
            - is_public (bool): 是否公开
            - file_path (str): 文件路径
            - file_size (float): 文件大小
            - mime_type (str): MIME类型
            - file_type (str): 文件类型
            - duration (Optional[float]): 时长（秒）
            - width (Optional[int]): 宽度（像素）
            - height (Optional[int]): 高度（像素）
            - tag_ids (Optional[List[int]]): 标签ID列表
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceSchema: 创建的资源信息
            - id (int): 资源ID
            - filename (str): 文件名
            - original_filename (str): 原始文件名
            - description (Optional[str]): 资源描述
            - is_public (bool): 是否公开
            - file_path (str): 文件路径
            - file_size (float): 文件大小
            - mime_type (str): MIME类型
            - file_type (str): 文件类型
            - duration (Optional[float]): 时长（秒）
            - width (Optional[int]): 宽度（像素）
            - height (Optional[int]): 高度（像素）
            - download_count (int): 下载次数
            - view_count (int): 查看次数
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            - created_by (int): 创建者ID
            - tags (List[ResourceTagSchema]): 标签列表
            
    Raises:
        HTTPException:
            - 400: 当文件路径已存在时
            - 500: 当创建资源失败时
    """
    # 检查文件路径是否已存在
    result = await db.execute(
        select(Resource).where(Resource.file_path == resource.file_path)
    )
    existing_resource = result.scalar_one_or_none()
    if existing_resource:
        raise HTTPException(status_code=400, detail="文件路径已存在")
    
    # 创建资源
    db_resource = Resource(
        **resource.dict(exclude={"tag_ids"}),
        created_by=current_user.id
    )
    db.add(db_resource)
    await db.commit()
    await db.refresh(db_resource)
    
    # 添加标签关联
    if resource.tag_ids:
        for tag_id in resource.tag_ids:
            result = await db.execute(
                select(ResourceTag).where(ResourceTag.id == tag_id)
            )
            tag = result.scalar_one_or_none()
            if tag:
                db_resource.tags.append(tag)
        await db.commit()
        await db.refresh(db_resource)
    
    return db_resource

@router.get("/",
    summary="获取资源列表",
    description="获取资源列表，支持多种过滤条件和分页。",
    responses={
        200: {
            "description": "成功返回资源列表",
            "content": {
                "application/json": {
                    "example": {
                        "resources": [
                            {
                                "id": 1,
                                "filename": "example.mp4",
                                "original_filename": "example_video.mp4",
                                "description": "示例视频文件",
                                "is_public": True,
                                "file_path": "global-resources/video/1/example.mp4",
                                "file_size": 1024000,
                                "mime_type": "video/mp4",
                                "file_type": "video",
                                "duration": 120.5,
                                "width": 1920,
                                "height": 1080,
                                "download_count": 0,
                                "view_count": 0,
                                "is_active": True,
                                "created_at": "2023-01-01T00:00:00",
                                "updated_at": "2023-01-01T00:00:00",
                                "created_by": 1,
                                "tags": []
                            }
                        ],
                        "total": 1,
                        "page": 1,
                        "page_size": 20,
                        "total_pages": 1
                    }
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
)
async def get_resources(
    file_type: Optional[str] = Query(None, pattern="^(video|audio|image|all)$", description="文件类型过滤"),
    tag_id: Optional[int] = Query(None, ge=1, description="标签ID过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    tags: Optional[str] = Query(None, description="标签名称过滤（逗号分隔）"),
    is_public: Optional[bool] = Query(None, description="公开状态过滤"),
    created_by: Optional[int] = Query(None, ge=1, description="创建者ID过滤"),
    is_active: Optional[bool] = Query(None, description="激活状态过滤"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回的记录数，最大100"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取资源列表
    
    获取资源列表，支持多种过滤条件和分页。
    
    Args:
        file_type (Optional[str]): 文件类型过滤，可选值：video, audio, image, all
        tag_id (Optional[int]): 标签ID过滤
        search (Optional[str]): 搜索关键词
        tags (Optional[str]): 标签名称过滤（逗号分隔）
        is_public (Optional[bool]): 公开状态过滤
        created_by (Optional[int]): 创建者ID过滤
        is_active (Optional[bool]): 激活状态过滤
        skip (int): 跳过的记录数，默认为0
        limit (int): 返回的记录数，默认为20，最大100
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceSearchResult: 资源列表和分页信息
            - resources (List[ResourceSchema]): 资源列表
                - id (int): 资源ID
                - filename (str): 文件名
                - original_filename (str): 原始文件名
                - description (Optional[str]): 资源描述
                - is_public (bool): 是否公开
                - file_path (str): 文件路径
                - file_size (float): 文件大小
                - mime_type (str): MIME类型
                - file_type (str): 文件类型
                - duration (Optional[float]): 时长（秒）
                - width (Optional[int]): 宽度（像素）
                - height (Optional[int]): 高度（像素）
                - download_count (int): 下载次数
                - view_count (int): 查看次数
                - is_active (bool): 是否激活
                - created_at (datetime): 创建时间
                - updated_at (datetime): 更新时间
                - created_by (int): 创建者ID
                - tags (List[ResourceTagSchema]): 标签列表
            - total (int): 总记录数
            - page (int): 当前页码
            - page_size (int): 每页记录数
            - total_pages (int): 总页数
            
    Raises:
        HTTPException:
            - 500: 当获取资源列表失败时
    """
    query = select(Resource)
    count_query = select(func.count(Resource.id))
    
    # 构建过滤条件
    conditions = []
    
    # 根据参数过滤资源状态
    if is_active is not None:
        conditions.append(Resource.is_active == is_active)
    # 如果没有指定 is_active 参数，则显示所有资源（不添加过滤条件）
    
    if file_type and file_type != "all":
        conditions.append(Resource.file_type == file_type)
    
    if tag_id:
        conditions.append(
            Resource.id.in_(
                select(resource_tags_mapping.c.resource_id).where(
                    resource_tags_mapping.c.tag_id == tag_id
                )
            )
        )
    
    if search:
        conditions.append(
            func.or_(
                Resource.filename.ilike(f"%{search}%"),
                Resource.original_filename.ilike(f"%{search}%"),
                Resource.description.ilike(f"%{search}%")
            )
        )
    
    if tags:
        tag_names = [tag.strip() for tag in tags.split(",")]
        for tag_name in tag_names:
            conditions.append(
                Resource.id.in_(
                    select(resource_tags_mapping.c.resource_id).join(
                        ResourceTag, resource_tags_mapping.c.tag_id == ResourceTag.id
                    ).where(
                        and_(
                            ResourceTag.name.ilike(f"%{tag_name}%"),
                            ResourceTag.is_active == True
                        )
                    )
                )
            )
    
    if is_public is not None:
        conditions.append(Resource.is_public == is_public)
    
    if created_by:
        conditions.append(Resource.created_by == created_by)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # 获取总数
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # 分页查询
    query = query.offset(skip).limit(limit).order_by(Resource.created_at.desc())
    result = await db.execute(query)
    resources = result.scalars().all()
    
    # 为每个资源加载标签
    for resource in resources:
        await db.refresh(resource, attribute_names=['tags'])
    
    return ResourceSearchResult(
        resources=resources,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit
    )

@router.get("/{resource_id}",
    summary="获取特定资源",
    description="根据资源ID获取特定资源的详细信息，包括关联的标签信息。",
    responses={
        200: {
            "description": "成功返回资源信息",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "filename": "example.mp4",
                        "original_filename": "example_video.mp4",
                        "description": "示例视频文件",
                        "is_public": True,
                        "file_path": "global-resources/video/1/example.mp4",
                        "file_size": 1024000,
                        "mime_type": "video/mp4",
                        "file_type": "video",
                        "duration": 120.5,
                        "width": 1920,
                        "height": 1080,
                        "download_count": 0,
                        "view_count": 0,
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-01T00:00:00",
                        "created_by": 1,
                        "tags": []
                    }
                }
            }
        },
        404: {"description": "资源不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取特定资源
    
    根据资源ID获取特定资源的详细信息，包括关联的标签信息。
    
    Args:
        resource_id (int): 资源ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceSchema: 资源信息
            - id (int): 资源ID
            - filename (str): 文件名
            - original_filename (str): 原始文件名
            - description (Optional[str]): 资源描述
            - is_public (bool): 是否公开
            - file_path (str): 文件路径
            - file_size (float): 文件大小
            - mime_type (str): MIME类型
            - file_type (str): 文件类型
            - duration (Optional[float]): 时长（秒）
            - width (Optional[int]): 宽度（像素）
            - height (Optional[int]): 高度（像素）
            - download_count (int): 下载次数
            - view_count (int): 查看次数
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            - created_by (int): 创建者ID
            - tags (List[ResourceTagSchema]): 标签列表
            
    Raises:
        HTTPException:
            - 404: 当资源不存在时
            - 500: 当获取资源失败时
    """
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 加载标签
    await db.refresh(resource, attribute_names=['tags'])
    
    return resource

@router.put("/{resource_id}",
    summary="更新资源",
    description="根据资源ID更新资源信息，包括资源描述、公开状态等基本信息以及标签关联。",
    responses={
        200: {
            "description": "成功更新资源信息",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "filename": "example.mp4",
                        "original_filename": "example_video.mp4",
                        "description": "更新后的示例视频文件",
                        "is_public": False,
                        "file_path": "global-resources/video/1/example.mp4",
                        "file_size": 1024000,
                        "mime_type": "video/mp4",
                        "file_type": "video",
                        "duration": 120.5,
                        "width": 1920,
                        "height": 1080,
                        "download_count": 0,
                        "view_count": 0,
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-02T00:00:00",
                        "created_by": 1,
                        "tags": []
                    }
                }
            }
        },
        404: {"description": "资源不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def update_resource(
    resource_id: int,
    resource_update: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新资源
    
    根据资源ID更新资源信息，包括资源描述、公开状态等基本信息以及标签关联。
    
    Args:
        resource_id (int): 资源ID
        resource_update (ResourceUpdate): 资源更新请求数据
            - description (Optional[str]): 资源描述
            - is_public (Optional[bool]): 是否公开
            - tag_ids (Optional[List[int]]): 标签ID列表
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceSchema: 更新后的资源信息
            - id (int): 资源ID
            - filename (str): 文件名
            - original_filename (str): 原始文件名
            - description (Optional[str]): 资源描述
            - is_public (bool): 是否公开
            - file_path (str): 文件路径
            - file_size (float): 文件大小
            - mime_type (str): MIME类型
            - file_type (str): 文件类型
            - duration (Optional[float]): 时长（秒）
            - width (Optional[int]): 宽度（像素）
            - height (Optional[int]): 高度（像素）
            - download_count (int): 下载次数
            - view_count (int): 查看次数
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            - created_by (int): 创建者ID
            - tags (List[ResourceTagSchema]): 标签列表
            
    Raises:
        HTTPException:
            - 404: 当资源不存在时
            - 500: 当更新资源失败时
    """
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 更新资源信息
    update_data = resource_update.dict(exclude_unset=True, exclude={"tag_ids"})
    for field, value in update_data.items():
        setattr(resource, field, value)
    
    # 更新标签关联
    if resource_update.tag_ids is not None:
        # 清除现有标签
        resource.tags.clear()
        
        # 添加新标签
        if resource_update.tag_ids:
            for tag_id in resource_update.tag_ids:
                result = await db.execute(
                    select(ResourceTag).where(ResourceTag.id == tag_id)
                )
                tag = result.scalar_one_or_none()
                if tag:
                    resource.tags.append(tag)
    
    await db.commit()
    await db.refresh(resource, attribute_names=['tags'])
    
    return resource


@router.put("/{resource_id}/activate",
    summary="切换资源的激活状态",
    description="根据资源ID切换资源的激活状态（is_active字段），用于启用或禁用资源。",
    responses={
        200: {
            "description": "成功切换资源激活状态",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "filename": "example.mp4",
                        "original_filename": "example_video.mp4",
                        "description": "示例视频文件",
                        "is_public": True,
                        "file_path": "global-resources/video/1/example.mp4",
                        "file_size": 1024000,
                        "mime_type": "video/mp4",
                        "file_type": "video",
                        "duration": 120.5,
                        "width": 1920,
                        "height": 1080,
                        "download_count": 0,
                        "view_count": 0,
                        "is_active": False,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-02T00:00:00",
                        "created_by": 1,
                        "tags": []
                    }
                }
            }
        },
        404: {"description": "资源不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def toggle_resource_active_status(
    resource_id: int,
    is_active: bool = Body(..., embed=True, description="资源激活状态，true为激活，false为禁用"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    切换资源的激活状态
    
    根据资源ID切换资源的激活状态（is_active字段），用于启用或禁用资源。
    
    Args:
        resource_id (int): 资源ID
        is_active (bool): 资源激活状态，true为激活，false为禁用
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceSchema: 更新后的资源信息
            - id (int): 资源ID
            - filename (str): 文件名
            - original_filename (str): 原始文件名
            - description (Optional[str]): 资源描述
            - is_public (bool): 是否公开
            - file_path (str): 文件路径
            - file_size (float): 文件大小
            - mime_type (str): MIME类型
            - file_type (str): 文件类型
            - duration (Optional[float]): 时长（秒）
            - width (Optional[int]): 宽度（像素）
            - height (Optional[int]): 高度（像素）
            - download_count (int): 下载次数
            - view_count (int): 查看次数
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            - created_by (int): 创建者ID
            - tags (List[ResourceTagSchema]): 标签列表
            
    Raises:
        HTTPException:
            - 404: 当资源不存在时
            - 500: 当切换资源激活状态失败时
    """
    # 直接更新资源状态
    update_result = await db.execute(
        update(Resource)
        .where(Resource.id == resource_id)
        .values(is_active=is_active)
    )
    
    if update_result.rowcount == 0:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    await db.commit()
    
    # 重新查询资源并显式加载标签关系
    result = await db.execute(
        select(Resource)
        .where(Resource.id == resource_id)
        .options(selectinload(Resource.tags))  # 显式加载标签关系
    )
    resource = result.scalar_one_or_none()
    
    return resource

@router.delete("/{resource_id}",
    summary="删除资源",
    description="根据资源ID删除资源。该操作为软删除，将资源的is_active状态设置为False，但不会删除MinIO中的实际文件，以支持恢复功能。",
    responses={
        200: {
            "description": "成功删除资源",
            "content": {
                "application/json": {
                    "example": {
                        "message": "资源删除成功"
                    }
                }
            }
        },
        404: {"description": "资源不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除资源
    
    根据资源ID删除资源。该操作为软删除，将资源的is_active状态设置为False，
    但不会删除MinIO中的实际文件，以支持恢复功能。
    
    Args:
        resource_id (int): 资源ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 删除结果信息
            - message (str): 删除结果消息
            
    Raises:
        HTTPException:
            - 404: 当资源不存在时
            - 500: 当删除资源失败时
    """
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 软删除 - 只标记为非活跃，不删除MinIO文件
    # 这样可以支持恢复功能
    resource.is_active = False
    await db.commit()
    
    return {"message": "资源删除成功"}

@router.post("/upload",
    summary="上传资源文件",
    description="上传资源文件到系统中，支持视频、音频和图片文件。上传成功后会自动创建资源记录并关联指定标签。",
    responses={
        200: {
            "description": "成功上传资源文件",
            "content": {
                "application/json": {
                    "example": {
                        "message": "文件上传成功",
                        "resource": {
                            "id": 1,
                            "filename": "example.mp4",
                            "original_filename": "example_video.mp4",
                            "description": "示例视频文件",
                            "is_public": True,
                            "file_path": "global-resources/video/1/example.mp4",
                            "file_size": 1024000,
                            "mime_type": "video/mp4",
                            "file_type": "video",
                            "duration": 120.5,
                            "width": 1920,
                            "height": 1080,
                            "download_count": 0,
                            "view_count": 0,
                            "is_active": True,
                            "created_at": "2023-01-01T00:00:00",
                            "updated_at": "2023-01-01T00:00:00",
                            "created_by": 1,
                            "tags": []
                        }
                    }
                }
            }
        },
        400: {"description": "不支持的文件类型或文件无法读取"},
        500: {"description": "服务器内部错误，如文件上传失败"}
    }
)
async def upload_resource(
    file: UploadFile = File(..., description="要上传的文件，支持视频、音频和图片格式"),
    description: Optional[str] = Form(None, description="资源描述信息"),
    is_public: bool = Form(True, description="资源是否公开，默认为True"),
    tags: Optional[str] = Form(None, description="标签ID列表，用逗号分隔，如 '1,2,3'"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传资源文件
    
    上传资源文件到系统中，支持视频、音频和图片文件。上传成功后会自动创建资源记录并关联指定标签。
    
    支持的文件类型：
    - 视频：.mp4, .mov, .avi, .webm
    - 音频：.mp3, .wav, .ogg, .mpeg
    - 图片：.jpg, .jpeg, .png, .gif, .webp
    
    Args:
        file (UploadFile): 要上传的文件，支持视频、音频和图片格式
        description (Optional[str]): 资源描述信息
        is_public (bool): 资源是否公开，默认为True
        tags (Optional[str]): 标签ID列表，用逗号分隔，如 '1,2,3'
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 上传结果信息
            - message (str): 上传结果消息
            - resource (ResourceSchema): 创建的资源信息
                - id (int): 资源ID
                - filename (str): 文件名
                - original_filename (str): 原始文件名
                - description (Optional[str]): 资源描述
                - is_public (bool): 是否公开
                - file_path (str): 文件路径
                - file_size (float): 文件大小
                - mime_type (str): MIME类型
                - file_type (str): 文件类型
                - duration (Optional[float]): 时长（秒）
                - width (Optional[int]): 宽度（像素）
                - height (Optional[int]): 高度（像素）
                - download_count (int): 下载次数
                - view_count (int): 查看次数
                - is_active (bool): 是否激活
                - created_at (datetime): 创建时间
                - updated_at (datetime): 更新时间
                - created_by (int): 创建者ID
                - tags (List[ResourceTagSchema]): 标签列表
                
    Raises:
        HTTPException:
            - 400: 当文件类型不支持或文件无法读取时
            - 500: 当文件上传失败或服务器内部错误时
    """
    try:
        print("=" * 50)
        print("📁 UPLOAD START")
        print(f"📄 File received: {file.filename}")
        print(f"📋 Content type: {file.content_type}")
        print(f"📝 Description: {description}")
        print(f"🔓 Is public: {is_public}")
        print(f"🏷️ Tags: {tags}")
        print("=" * 50)
        
        # 验证文件类型
        allowed_types = {
            'video': ['.mp4', '.mov', '.avi', '.webm'],
            'audio': ['.mp3', '.wav', '.ogg', '.mpeg'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        }
        
        print(f"File content type: {file.content_type}")
        print(f"File name: {file.filename}")
        
        # 获取文件扩展名
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_type = None
        
        for ft, extensions in allowed_types.items():
            if file_extension in extensions:
                file_type = ft
                break
        
        # 如果扩展名不匹配，但内容类型是允许的，也可以接受
        if not file_type:
            fallback_types = {
                'video': ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'],
                'audio': ['audio/mp3', 'audio/wav', 'audio/ogg', 'audio/mpeg'],
                'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            }
            
            for ft, mime_types in fallback_types.items():
                if file.content_type in mime_types:
                    file_type = ft
                    break
        
        if not file_type:
            print(f"Unsupported file type: {file.content_type}, extension: {file_extension}")
            raise HTTPException(status_code=400, detail="不支持的文件类型")
            
        print(f"✅ File type detected: {file_type} (extension: {file_extension})")
        print(f"🔍 Checking file readability...")
        
        # 验证文件内容是否可读
        try:
            print(f"📖 Attempting to read file content...")
            file_content = await file.read()
            print(f"✅ File readable, size: {len(file_content)} bytes")
            print(f"📼 Resetting file pointer...")
            await file.seek(0)
            print(f"✅ File pointer reset successfully")
        except Exception as e:
            print(f"❌ Cannot read file: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=400, detail="文件无法读取")
        
        # 生成文件路径
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = f"global-resources/{file_type}/{current_user.id}/{unique_filename}"
        
        # 上传到MinIO
        try:
            print(f"Starting MinIO upload to: {file_path}")
            minio_service = MinioService()
            
            # 读取文件内容
            file_content = await file.read()
            await minio_service.upload_file_content(file_content, file_path, file.content_type)
            print("MinIO upload completed successfully")
        except Exception as e:
            print(f"❌ MinIO upload error: {e}")
            print(f"❌ Error type: {type(e)}")
            print(f"❌ Error details: {str(e)}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
        finally:
            # 重置文件指针
            await file.seek(0)
        
        # 获取文件大小
        file_size = len(file_content)
        
        # 创建资源记录
        resource_data = ResourceCreate(
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type,
            file_type=file_type,
            description=description,
            is_public=is_public
        )
        
        # 创建资源（不包含tag_ids）
        resource_dict = resource_data.dict(exclude={'tag_ids'})
        # 添加created_by字段（这是数据库字段，不是schema字段）
        resource_dict['created_by'] = current_user.id
        db_resource = Resource(**resource_dict)
        db.add(db_resource)
        await db.commit()
        await db.refresh(db_resource)
        
        # 处理标签关联
        if tags:
            tag_ids = [int(tag_id.strip()) for tag_id in tags.split(',') if tag_id.strip().isdigit()]
            if tag_ids:
                # 直接插入到resource_tags_mapping表中
                for tag_id in tag_ids:
                    # 检查标签是否存在
                    tag_check = await db.execute(
                        select(ResourceTag).where(ResourceTag.id == tag_id)
                    )
                    if tag_check.scalar_one_or_none():
                        # 插入关联记录到resource_tags_mapping表
                        await db.execute(
                            resource_tags_mapping.insert().values(
                                resource_id=db_resource.id,
                                tag_id=tag_id
                            )
                        )
                
                await db.commit()
                await db.refresh(db_resource)
        
        return {"message": "文件上传成功", "resource": db_resource}
        
    except Exception as e:
        print(f"Error in upload endpoint: {e}")
        print(f"Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{resource_id}/download-url",
    summary="获取资源下载链接",
    description="根据资源ID生成资源文件的下载链接。只有资源所有者或公开资源才能下载。",
    responses={
        200: {
            "description": "成功生成下载链接",
            "content": {
                "application/json": {
                    "example": {
                        "download_url": "https://minio.example.com/download-link",
                        "filename": "example_video.mp4"
                    }
                }
            }
        },
        403: {"description": "无权访问此资源"},
        404: {"description": "资源不存在"},
        500: {"description": "生成下载链接失败"}
    }
)
async def get_resource_download_url(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取资源下载链接
    
    根据资源ID生成资源文件的下载链接。只有资源所有者或公开资源才能下载。
    下载成功后会自动增加资源的下载次数统计。
    
    Args:
        resource_id (int): 资源ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 下载链接信息
            - download_url (str): 资源下载链接
            - filename (str): 原始文件名
                
    Raises:
        HTTPException:
            - 403: 当用户无权访问此资源时
            - 404: 当资源不存在时
            - 500: 当生成下载链接失败时
    """
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查资源是否活跃
    if not resource.is_active:
        # 允许下载，但可以记录日志
        print(f"⚠ Downloading inactive resource: {resource_id}")
    
    # 检查访问权限
    if not resource.is_public and resource.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
    
    # 生成下载链接
    try:
        minio_service = get_minio_service()
        download_url = await minio_service.get_file_url(resource.file_path)
        
        # 更新下载次数
        resource.download_count += 1
        await db.commit()
        
        return {"download_url": download_url, "filename": resource.original_filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成下载链接失败: {str(e)}")

@router.get("/{resource_id}/view-url",
    summary="获取资源查看链接",
    description="根据资源ID生成资源文件的查看链接。只有资源所有者或公开资源才能查看。",
    responses={
        200: {
            "description": "成功生成查看链接",
            "content": {
                "application/json": {
                    "example": {
                        "view_url": "https://minio.example.com/view-link",
                        "filename": "example_video.mp4"
                    }
                }
            }
        },
        403: {"description": "无权访问此资源"},
        404: {"description": "资源不存在"},
        500: {"description": "生成查看链接失败"}
    }
)
async def get_resource_view_url(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取资源查看链接
    
    根据资源ID生成资源文件的查看链接。只有资源所有者或公开资源才能查看。
    查看成功后会自动增加资源的查看次数统计。
    
    Args:
        resource_id (int): 资源ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 查看链接信息
            - view_url (str): 资源查看链接
            - filename (str): 原始文件名
                
    Raises:
        HTTPException:
            - 403: 当用户无权访问此资源时
            - 404: 当资源不存在时
            - 500: 当生成查看链接失败时
    """
    print(f"🔍 View URL requested for resource_id: {resource_id}")
    print(f"👤 Current user: {current_user.id}")
    
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    print(f"📄 Resource found: {resource}")
    
    if not resource:
        print(f"❌ Resource not found: {resource_id}")
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查资源是否活跃
    if not resource.is_active:
        print(f"⚠ Resource is inactive: {resource_id}")
        # 仍然允许查看，但给出警告信息
    
    print(f"📋 Resource details - file_path: {resource.file_path}, is_public: {resource.is_public}, created_by: {resource.created_by}")
    
    # 检查访问权限
    if not resource.is_public and resource.created_by != current_user.id:
        print(f"❌ Access denied - resource not public and not owned by user")
        raise HTTPException(status_code=403, detail="无权访问此资源")
    
    print(f"✅ Access granted for resource: {resource_id}")
    
    # 生成查看链接
    try:
        print(f"🔗 Generating MinIO presigned URL for: {resource.file_path}")
        try:
            minio_service = get_minio_service()
            print(f"🏗️ MinIOService created successfully: {type(minio_service)}")
        except Exception as e:
            print(f"❌ Failed to create MinIOService: {e}")
            raise HTTPException(status_code=500, detail=f"MinIO服务初始化失败: {str(e)}")
        
        print(f"🔗 Calling get_file_url method...")
        view_url_task = minio_service.get_file_url(resource.file_path)
        print(f"🔗 get_file_url task created: {type(view_url_task)}")
        
        view_url = await view_url_task
        print(f"✅ MinIO view URL generated: {view_url}")
        print(f"📄 View URL type: {type(view_url)}")
        
        if view_url is None:
            print(f"❌ MinIO view URL is None")
            raise HTTPException(status_code=500, detail="无法生成查看链接")
        
        # 更新查看次数
        resource.view_count += 1
        print(f"📊 Updating view_count from {resource.view_count - 1} to {resource.view_count}")
        await db.commit()
        print(f"✅ Database committed successfully")
        
        return {"view_url": view_url, "filename": resource.original_filename}
    
    except Exception as e:
        print(f"❌ Error generating view URL: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"生成查看链接失败: {str(e)}")


@router.get("/thumbnail-url",
    summary="获取缩略图预签名URL",
    description="根据缩略图路径生成预签名URL，用于安全访问缩略图文件。URL有效期为24小时。",
    responses={
        200: {
            "description": "成功生成缩略图预签名URL",
            "content": {
                "application/json": {
                    "example": {
                        "download_url": "https://minio.example.com/thumbnail-link"
                    }
                }
            }
        },
        400: {"description": "路径参数无效"},
        500: {"description": "生成缩略图URL失败"}
    }
)
async def get_thumbnail_url(
    path: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据缩略图路径生成预签名URL"""
    if not path:
        raise HTTPException(status_code=400, detail="路径参数不能为空")
    
    try:
        # 验证路径格式（基础验证）
        if not path.startswith("users/") and not path.startswith("global-resources/"):
            raise HTTPException(status_code=400, detail="无效的文件路径")
        
        # 生成预签名URL
        minio_service = get_minio_service()
        download_url = await minio_service.get_file_url(path, expiry=86400)  # 24小时有效期
        
        if not download_url:
            raise HTTPException(status_code=500, detail="无法生成缩略图URL")
        
        return {"download_url": download_url}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成缩略图URL失败: {str(e)}")
