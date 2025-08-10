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

@router.post("/", response_model=ResourceTagSchema)
async def create_resource_tag(
    tag: ResourceTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建资源标签"""
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

@router.get("/", response_model=List[ResourceTagSchema])
async def get_resource_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tag_type: Optional[str] = Query(None, pattern="^(audio|video|image|general)$"),
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资源标签列表"""
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

@router.get("/{tag_id}", response_model=ResourceTagSchema)
async def get_resource_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取特定资源标签"""
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.id == tag_id)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    return tag

@router.put("/{tag_id}", response_model=ResourceTagSchema)
async def update_resource_tag(
    tag_id: int,
    tag_update: ResourceTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新资源标签"""
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

@router.delete("/{tag_id}")
async def delete_resource_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除资源标签"""
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

@router.post("/batch-create")
async def batch_create_resource_tags(
    tags: List[ResourceTagCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量创建资源标签"""
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