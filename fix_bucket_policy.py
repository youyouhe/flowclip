#!/usr/bin/env python3
"""
修复MinIO存储桶策略
"""
import asyncio
import sys
import os
import json

# 添加backend目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.minio_client import minio_service
from minio import Minio
from minio.error import S3Error
from app.core.config import settings

async def fix_bucket_policy():
    """修复存储桶策略"""
    print("=== 修复MinIO存储桶策略 ===")
    
    # 直接使用MinIO客户端
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure
    )
    
    bucket_name = settings.minio_bucket_name
    
    # 检查桶是否存在
    try:
        if not client.bucket_exists(bucket_name):
            print(f"❌ 存储桶 {bucket_name} 不存在")
            return
        print(f"✅ 存储桶 {bucket_name} 存在")
    except S3Error as e:
        print(f"❌ 检查存储桶失败: {e}")
        return
    
    # 设置更宽松的存储桶策略
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            },
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket_name}"]
            }
        ]
    }
    
    try:
        policy_json = json.dumps(bucket_policy)
        client.set_bucket_policy(bucket_name, policy_json)
        print(f"✅ 存储桶策略设置成功")
        
        # 验证策略
        try:
            current_policy = client.get_bucket_policy(bucket_name)
            print(f"✅ 当前策略: {current_policy}")
        except Exception as e:
            print(f"⚠️ 无法获取当前策略: {e}")
            
    except Exception as e:
        print(f"❌ 设置存储桶策略失败: {e}")
    
    # 测试匿名访问
    test_object = "users/6/projects/7/thumbnails/YgRmuePMHdE.jpg"
    try:
        # 检查对象是否存在
        client.stat_object(bucket_name, test_object)
        print(f"✅ 测试对象存在: {test_object}")
        
        # 生成预签名URL
        from datetime import timedelta
        from urllib.parse import urlparse
        
        url = client.presigned_get_object(
            bucket_name,
            test_object,
            expires=timedelta(seconds=3600)
        )
        
        print(f"✅ 生成的预签名URL: {url}")
        
        # 检查URL中的端点
        parsed = urlparse(url)
        if settings.minio_endpoint in parsed.netloc:
            print("✅ URL端点正确")
        else:
            print(f"❌ URL端点不匹配: 期望 {settings.minio_endpoint}, 实际 {parsed.netloc}")
        
    except S3Error as e:
        print(f"❌ 测试对象访问失败: {e}")

if __name__ == "__main__":
    asyncio.run(fix_bucket_policy())