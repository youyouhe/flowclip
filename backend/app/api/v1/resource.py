from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, and_
from typing import List, Optional
from app.core.database import get_db
from app.models.resource import Resource, ResourceTag, ResourceTagRelation
from app.schemas.resource import Resource as ResourceSchema, ResourceCreate, ResourceUpdate, ResourceQuery, ResourceSearchResult
from fastapi import Depends
from app.core.security import get_current_user, oauth2_scheme
from app.models.user import User
from app.services.minio_client import MinioService
from app.core.config import settings
import os
import uuid
from datetime import datetime

router = APIRouter(tags=["resources"])

# ==================== 标签管理端点 ====================

@router.get("/tags", response_model=List[dict])
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
    
    return [{"id": tag.id, "name": tag.name, "tag_type": tag.tag_type} for tag in tags]

@router.post("/tags", response_model=dict)
async def create_resource_tag(
    name: str = Form(...),
    tag_type: str = Form(..., pattern="^(audio|video|image|general)$"),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建资源标签"""
    # 检查标签名是否已存在
    result = await db.execute(
        select(ResourceTag).where(ResourceTag.name == name)
    )
    existing_tag = result.scalar_one_or_none()
    if existing_tag:
        raise HTTPException(status_code=400, detail="标签名已存在")
    
    # 创建新标签
    db_tag = ResourceTag(
        name=name,
        tag_type=tag_type,
        description=description
    )
    db.add(db_tag)
    await db.commit()
    await db.refresh(db_tag)
    
    return {"message": "标签创建成功", "tag": {"id": db_tag.id, "name": db_tag.name, "tag_type": db_tag.tag_type}}

@router.delete("/tags/{tag_id}")
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

# ==================== 资源管理端点 ====================

@router.post("/", response_model=ResourceSchema)
async def create_resource(
    resource: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建资源"""
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

@router.get("/", response_model=ResourceSearchResult)
async def get_resources(
    file_type: Optional[str] = Query(None, pattern="^(video|audio|image|all)$"),
    tag_id: Optional[int] = Query(None, ge=1),
    search: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    is_public: Optional[bool] = None,
    created_by: Optional[int] = Query(None, ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资源列表"""
    query = select(Resource)
    count_query = select(func.count(Resource.id))
    
    # 构建过滤条件
    conditions = []
    
    if file_type and file_type != "all":
        conditions.append(Resource.file_type == file_type)
    
    if tag_id:
        conditions.append(
            Resource.id.in_(
                select(ResourceTagRelation.resource_id).where(
                    ResourceTagRelation.tag_id == tag_id
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
                    select(ResourceTagRelation.resource_id).join(
                        ResourceTag, ResourceTagRelation.tag_id == ResourceTag.id
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

@router.get("/{resource_id}", response_model=ResourceSchema)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取特定资源"""
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 加载标签
    await db.refresh(resource, attribute_names=['tags'])
    
    return resource

@router.put("/{resource_id}", response_model=ResourceSchema)
async def update_resource(
    resource_id: int,
    resource_update: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新资源"""
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

@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除资源"""
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 从MinIO删除文件
    try:
        minio_service = MinioService()
        minio_service.remove_file(resource.file_path)
    except Exception as e:
        print(f"删除MinIO文件失败: {e}")
    
    # 软删除
    resource.is_active = False
    await db.commit()
    
    return {"message": "资源删除成功"}

@router.post("/upload")
async def upload_resource(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    is_public: bool = Form(True),
    tags: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传资源文件"""
    # 验证文件类型
    allowed_types = {
        'video': ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'],
        'audio': ['audio/mp3', 'audio/wav', 'audio/ogg', 'audio/mpeg'],
        'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    }
    
    file_type = None
    for ft, mime_types in allowed_types.items():
        if file.content_type in mime_types:
            file_type = ft
            break
    
    if not file_type:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    
    # 生成文件路径
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = f"global-resources/{file_type}/{current_user.id}/{unique_filename}"
    
    # 上传到MinIO
    try:
        minio_service = MinioService()
        await minio_service.upload_file(file.file, file_path, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
    
    # 获取文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()
    file.file.seek(0)  # 重置文件指针
    
    # 创建资源记录
    resource_data = ResourceCreate(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        file_type=file_type,
        description=description,
        is_public=is_public,
        created_by=current_user.id
    )
    
    # 创建资源
    db_resource = Resource(**resource_data.dict())
    db.add(db_resource)
    await db.commit()
    await db.refresh(db_resource)
    
    # 添加标签
    if tags:
        tag_names = [tag.strip() for tag in tags.split(",")]
        for tag_name in tag_names:
            result = await db.execute(
                select(ResourceTag).where(
                    and_(
                        ResourceTag.name == tag_name,
                        ResourceTag.is_active == True
                    )
                )
            )
            tag = result.scalar_one_or_none()
            if tag:
                db_resource.tags.append(tag)
        await db.commit()
        await db.refresh(db_resource, attribute_names=['tags'])
    
    return {"message": "文件上传成功", "resource": db_resource}

@router.get("/{resource_id}/download-url")
async def get_resource_download_url(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资源下载链接"""
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.is_active == True)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查访问权限
    if not resource.is_public and resource.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
    
    # 生成下载链接
    try:
        minio_service = MinioService()
        download_url = minio_service.get_presigned_url(resource.file_path)
        
        # 更新下载次数
        resource.download_count += 1
        await db.commit()
        
        return {"download_url": download_url, "filename": resource.original_filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成下载链接失败: {str(e)}")

@router.get("/{resource_id}/view-url")
async def get_resource_view_url(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资源查看链接"""
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.is_active == True)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    
    # 检查访问权限
    if not resource.is_public and resource.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
    
    # 生成查看链接
    try:
        minio_service = MinioService()
        view_url = minio_service.get_presigned_url(resource.file_path)
        
        # 更新查看次数
        resource.view_count += 1
        await db.commit()
        
        return {"view_url": view_url, "filename": resource.original_filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成查看链接失败: {str(e)}")