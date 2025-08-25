from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.minio_client import minio_service

router = APIRouter()

@router.get("/minio-url")
async def get_minio_resource_url(
    object_path: str = Query(..., description="MinIO中的对象路径"),
    expiry: int = Query(3600, description="URL过期时间（秒）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取MinIO资源的预签名URL（通用方法）"""
    # 验证对象路径是否合法（防止路径遍历攻击）
    if ".." in object_path or object_path.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid object path"
        )
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(object_path)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found in storage: {object_path}"
        )
    
    # 生成预签名URL
    url = await minio_service.get_file_url(object_path, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate resource URL"
        )
    
    return {
        "resource_url": url, 
        "expires_in": expiry, 
        "object_path": object_path
    }