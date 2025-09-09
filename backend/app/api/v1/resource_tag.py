from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from typing import List, Optional
from app.core.database import get_db
from app.models.resource_tag import ResourceTag
from app.schemas.resource import ResourceTag as ResourceTagSchema, ResourceTagCreate, ResourceTagUpdate
from fastapi import Depends
from app.core.security import get_current_user, oauth2_scheme
from app.models.user import User

router = APIRouter(prefix="/resource-tags", tags=["resource-tags"])

@router.post("/",
    summary="创建资源标签",
    description="创建一个新的资源标签。标签名必须唯一，不能与现有标签重复。",
    responses={
        200: {
            "description": "成功创建资源标签",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "示例标签",
                        "tag_type": "general",
                        "description": "这是一个示例标签",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-01T00:00:00"
                    }
                }
            }
        },
        400: {"description": "标签名已存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def create_resource_tag(
    tag: ResourceTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建资源标签
    
    创建一个新的资源标签。标签名必须唯一，不能与现有标签重复。
    
    Args:
        tag (ResourceTagCreate): 资源标签创建请求数据
            - name (str): 标签名，必须唯一
            - tag_type (str): 标签类型，可选值：audio, video, image, general
            - description (Optional[str]): 标签描述
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceTagSchema: 创建的资源标签信息
            - id (int): 标签ID
            - name (str): 标签名
            - tag_type (str): 标签类型
            - description (Optional[str]): 标签描述
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            
    Raises:
        HTTPException:
            - 400: 当标签名已存在时
            - 500: 当创建标签失败时
    """
    # 检查标签名是否已存在
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.name == tag.name)
    )
    existing_tag = result.scalar_one_or_none()
    if existing_tag:
        raise HTTPException(status_code=400, detail="标签名已存在")
    
    # 创建新标签
    db_tag = ResourceTag(**tag.dict())
    db.add(db_tag)
    await db.commit()
    await db.refresh(db_tag)
    
    return db_tag

@router.get("/",
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
                            "tag_type": "general",
                            "description": "这是一个示例标签",
                            "is_active": True,
                            "created_at": "2023-01-01T00:00:00",
                            "updated_at": "2023-01-01T00:00:00"
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
        List[ResourceTagSchema]: 资源标签列表
            - id (int): 标签ID
            - name (str): 标签名
            - tag_type (str): 标签类型
            - description (Optional[str]): 标签描述
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            
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
    
    return tags

@router.get("/{tag_id}",
    summary="获取特定资源标签",
    description="根据标签ID获取特定资源标签的详细信息。",
    responses={
        200: {
            "description": "成功返回资源标签信息",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "示例标签",
                        "tag_type": "general",
                        "description": "这是一个示例标签",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-01T00:00:00"
                    }
                }
            }
        },
        404: {"description": "标签不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def get_resource_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取特定资源标签
    
    根据标签ID获取特定资源标签的详细信息。
    
    Args:
        tag_id (int): 标签ID
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceTagSchema: 资源标签信息
            - id (int): 标签ID
            - name (str): 标签名
            - tag_type (str): 标签类型
            - description (Optional[str]): 标签描述
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            
    Raises:
        HTTPException:
            - 404: 当标签不存在时
            - 500: 当获取标签失败时
    """
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.id == tag_id)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    return tag

@router.put("/{tag_id}",
    summary="更新资源标签",
    description="根据标签ID更新资源标签的信息。支持部分更新，只更新提供的字段。",
    responses={
        200: {
            "description": "成功更新资源标签",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "更新后的标签",
                        "tag_type": "general",
                        "description": "这是更新后的标签描述",
                        "is_active": True,
                        "created_at": "2023-01-01T00:00:00",
                        "updated_at": "2023-01-02T00:00:00"
                    }
                }
            }
        },
        400: {"description": "标签名已存在"},
        404: {"description": "标签不存在"},
        500: {"description": "服务器内部错误"}
    }
)
async def update_resource_tag(
    tag_id: int,
    tag_update: ResourceTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新资源标签
    
    根据标签ID更新资源标签的信息。支持部分更新，只更新提供的字段。
    
    Args:
        tag_id (int): 标签ID
        tag_update (ResourceTagUpdate): 资源标签更新请求数据
            - name (Optional[str]): 标签名
            - tag_type (Optional[str]): 标签类型
            - description (Optional[str]): 标签描述
            - is_active (Optional[bool]): 是否激活
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        ResourceTagSchema: 更新后的资源标签信息
            - id (int): 标签ID
            - name (str): 标签名
            - tag_type (str): 标签类型
            - description (Optional[str]): 标签描述
            - is_active (bool): 是否激活
            - created_at (datetime): 创建时间
            - updated_at (datetime): 更新时间
            
    Raises:
        HTTPException:
            - 400: 当标签名已存在时
            - 404: 当标签不存在时
            - 500: 当更新标签失败时
    """
    # 获取现有标签
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.id == tag_id)
    )
    existing_tag = result.scalar_one_or_none()
    if not existing_tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    # 检查标签名是否冲突
    if tag_update.name and tag_update.name != existing_tag.name:
        result = await db.execute(
            select(ResourceTag).where(ResourceTag.name == tag_update.name, ResourceTag.id != tag_id)
        )
        conflicting_tag = result.scalar_one_or_none()
        if conflicting_tag:
            raise HTTPException(status_code=400, detail="标签名已存在")
    
    # 更新标签
    update_data = tag_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing_tag, field, value)
    
    await db.commit()
    await db.refresh(existing_tag)
    
    return existing_tag

@router.delete("/{tag_id}",
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

@router.post("/batch-create",
    summary="批量创建资源标签",
    description="批量创建资源标签。如果标签名已存在，则跳过该标签的创建。",
    responses={
        200: {
            "description": "成功批量创建资源标签",
            "content": {
                "application/json": {
                    "example": {
                        "message": "成功创建 2 个标签",
                        "tags": [
                            {
                                "id": 1,
                                "name": "示例标签1",
                                "tag_type": "general",
                                "description": "这是示例标签1",
                                "is_active": True,
                                "created_at": "2023-01-01T00:00:00",
                                "updated_at": "2023-01-01T00:00:00"
                            },
                            {
                                "id": 2,
                                "name": "示例标签2",
                                "tag_type": "video",
                                "description": "这是示例标签2",
                                "is_active": True,
                                "created_at": "2023-01-01T00:00:00",
                                "updated_at": "2023-01-01T00:00:00"
                            }
                        ]
                    }
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
)
async def batch_create_resource_tags(
    tags: List[ResourceTagCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量创建资源标签
    
    批量创建资源标签。如果标签名已存在，则跳过该标签的创建。
    
    Args:
        tags (List[ResourceTagCreate]): 资源标签创建请求数据列表
            - name (str): 标签名，必须唯一
            - tag_type (str): 标签类型，可选值：audio, video, image, general
            - description (Optional[str]): 标签描述
        db (AsyncSession): 数据库会话（依赖注入）
        current_user (User): 当前认证用户（依赖注入）
        
    Returns:
        dict: 批量创建结果信息
            - message (str): 创建结果消息，包含成功创建的标签数量
            - tags (List[ResourceTagSchema]): 成功创建的标签列表
                - id (int): 标签ID
                - name (str): 标签名
                - tag_type (str): 标签类型
                - description (Optional[str]): 标签描述
                - is_active (bool): 是否激活
                - created_at (datetime): 创建时间
                - updated_at (datetime): 更新时间
            
    Raises:
        HTTPException:
            - 500: 当批量创建标签失败时
    """
    created_tags = []
    
    for tag_data in tags:
        # 检查标签名是否已存在
        result = await db.execute(
            select(ResourceTag).where(ResourceTag.name == tag_data.name)
        )
        existing_tag = result.scalar_one_or_none()
        if existing_tag:
            continue
        
        # 创建新标签
        db_tag = ResourceTag(**tag_data.dict())
        db.add(db_tag)
        created_tags.append(db_tag)
    
    await db.commit()
    for tag in created_tags:
        await db.refresh(tag)
    
    return {"message": f"成功创建 {len(created_tags)} 个标签", "tags": created_tags}