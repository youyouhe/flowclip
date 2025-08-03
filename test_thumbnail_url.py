#!/usr/bin/env python3
"""
测试缩略图URL生成功能
"""
import asyncio
import sys
import os

# 添加backend目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.minio_client import minio_service
from app.core.config import settings

async def test_thumbnail_url():
    """测试缩略图URL生成"""
    print("=== 测试缩略图URL生成 ===")
    
    # 测试MinIO连接
    print(f"MinIO端点: {settings.minio_endpoint}")
    print(f"存储桶名称: {settings.minio_bucket_name}")
    
    # 测试连接
    test_result = await minio_service.test_connection()
    print(f"连接测试结果: {test_result}")
    
    if not test_result['connected']:
        print("❌ MinIO连接失败")
        return
    
    # 生成测试缩略图对象名称
    test_object_name = minio_service.generate_thumbnail_object_name(6, 7, "YgRmuePMHdE")
    print(f"测试对象名称: {test_object_name}")
    
    # 检查文件是否存在
    exists = await minio_service.file_exists(test_object_name)
    print(f"文件是否存在: {exists}")
    
    if exists:
        # 生成预签名URL
        url = await minio_service.get_file_url(test_object_name, 3600)
        print(f"生成的URL: {url}")
        
        # 验证URL是否包含正确的端点
        if settings.minio_endpoint in url:
            print("✅ URL包含正确的端点")
        else:
            print("❌ URL端点不匹配")
    else:
        print("❌ 测试文件不存在")

if __name__ == "__main__":
    asyncio.run(test_thumbnail_url())