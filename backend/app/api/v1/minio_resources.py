from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.minio_client import minio_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/minio-url",
    summary="获取MinIO资源的预签名URL",
    description="获取MinIO存储中资源的预签名URL，用于临时访问私有资源。该接口支持设置URL的过期时间。",
    responses={
        200: {
            "description": "成功返回预签名URL",
            "content": {
                "application/json": {
                    "example": {
                        "resource_url": "https://minio.example.com/temp-url",
                        "expires_in": 3600,
                        "object_path": "users/1/projects/1/videos/1.mp4"
                    }
                }
            }
        },
        400: {"description": "无效的对象路径"},
        404: {"description": "文件未找到"},
        500: {"description": "服务器内部错误"}
    }
)
async def get_minio_resource_url(
    object_path: str = Query(..., description="MinIO中的对象路径"),
    expiry: int = Query(3600, description="URL过期时间（秒）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取MinIO资源的预签名URL（通用方法）
    
    获取MinIO存储中资源的预签名URL，用于临时访问私有资源。该接口支持设置URL的过期时间。
    该方法可以用于访问任何存储在MinIO中的资源，包括视频、音频、字幕等文件。
    
    Args:
        object_path (str): MinIO中的对象路径，必须提供
        expiry (int): URL过期时间（秒），默认为3600秒（1小时）
        current_user (User): 当前认证用户（依赖注入）
        db (AsyncSession): 数据库会话（依赖注入）
        
    Returns:
        dict: 包含预签名URL信息的字典
            - resource_url (str): 资源的预签名URL
            - expires_in (int): URL过期时间（秒）
            - object_path (str): 请求的对象路径
            
    Raises:
        HTTPException:
            - 400: 当对象路径无效时（包含路径遍历攻击特征）
            - 404: 当请求的文件在存储中未找到时
            - 500: 当生成预签名URL失败时
    """
    logger.info(f"MinIO资源URL请求 - 用户ID: {current_user.id}, 对象路径: {object_path}, 过期时间: {expiry}")
    
    # 验证对象路径是否合法（防止路径遍历攻击）
    if ".." in object_path or object_path.startswith("/"):
        logger.warning(f"无效的对象路径: {object_path}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid object path"
        )
    
    # 检查文件是否存在
    logger.info(f"检查文件是否存在: {object_path}")
    file_exists = await minio_service.file_exists(object_path)
    logger.info(f"文件存在性检查结果: {file_exists}")
    
    if not file_exists:
        logger.warning(f"文件在存储中未找到: {object_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found in storage: {object_path}"
        )
    
    # 生成预签名URL
    logger.info(f"生成预签名URL: {object_path}")
    url = await minio_service.get_file_url(object_path, expiry)
    logger.info(f"预签名URL生成结果: {url is not None}")
    
    if not url:
        logger.error(f"生成资源URL失败: {object_path}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate resource URL"
        )
    
    logger.info(f"成功生成资源URL: {object_path}")
    return {
        "resource_url": url, 
        "expires_in": expiry, 
        "object_path": object_path
    }