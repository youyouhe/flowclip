import os
import io
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from urllib.parse import urlparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from app.core.config import settings

class MinioService:
    """MinIO文件存储服务"""
    
    def __init__(self):
        # 决定使用哪个端点来初始化MinIO客户端
        # 如果配置了公共端点，使用公共端点，否则使用内部端点
        endpoint = settings.minio_endpoint
        if settings.minio_public_endpoint:
            # 对于URL生成，使用公共端点以确保签名正确
            # 但初始化客户端时需要去除协议部分
            public_endpoint = settings.minio_public_endpoint
            if public_endpoint.startswith('http://'):
                endpoint = public_endpoint[7:]  # Remove 'http://'
            elif public_endpoint.startswith('https://'):
                endpoint = public_endpoint[8:]  # Remove 'https://'
            else:
                endpoint = public_endpoint
        
        self.client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region="us-east-1"  # 添加区域配置，避免签名问题
        )
        self.bucket_name = settings.minio_bucket_name
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def ensure_bucket_exists(self) -> bool:
        """确保桶存在并设置正确的权限"""
        def _ensure_bucket():
            try:
                if not self.client.bucket_exists(self.bucket_name):
                    self.client.make_bucket(self.bucket_name)
                    print(f"✓ MinIO桶 '{self.bucket_name}' 创建成功")
                
                # 设置桶策略，允许预签名URL访问
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                        }
                    ]
                }
                
                import json
                try:
                    policy_json = json.dumps(bucket_policy)
                    self.client.set_bucket_policy(self.bucket_name, policy_json)
                    print(f"✓ MinIO桶 '{self.bucket_name}' 策略设置成功")
                except Exception as policy_error:
                    print(f"⚠ 设置桶策略失败: {policy_error}")
                
                # CORS配置在MinIO 7.x版本中需要通过其他方式设置
                print(f"⚠ MinIO桶 '{self.bucket_name}' CORS配置跳过 (需要通过MinIO Console手动设置)")
                
                return True
            except S3Error as e:
                print(f"✗ MinIO桶操作失败: {e}")
                return False
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _ensure_bucket
        )
    
    async def upload_file(
        self, 
        file_path: str, 
        object_name: str, 
        content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """上传文件到MinIO"""
        def _upload():
            try:
                self.client.fput_object(
                    self.bucket_name,
                    object_name,
                    file_path,
                    content_type=content_type
                )
                return object_name
            except S3Error as e:
                print(f"✗ 文件上传失败: {e}")
                return None
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _upload
        )

    def upload_file_sync(
        self, 
        file_path: str, 
        object_name: str, 
        content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """同步上传文件到MinIO"""
        try:
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path,
                content_type=content_type
            )
            return object_name
        except S3Error as e:
            print(f"✗ 文件上传失败: {e}")
            return None
    
    async def upload_file_content(
        self, 
        content: bytes, 
        object_name: str, 
        content_type: str = "application/octet-stream"
    ) -> Optional[str]:
        """上传文件内容到MinIO"""
        def _upload():
            try:
                file_data = io.BytesIO(content)
                file_size = len(content)
                
                self.client.put_object(
                    self.bucket_name,
                    object_name,
                    file_data,
                    file_size,
                    content_type=content_type
                )
                return object_name
            except S3Error as e:
                print(f"✗ 内容上传失败: {e}")
                return None
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _upload
        )
    
    async def get_file_url(self, object_name: str, expiry: int = 3600) -> Optional[str]:
        """获取文件的预签名URL"""
        def _get_url():
            try:
                # 尝试使用预签名URL
                url = self.client.presigned_get_object(
                    self.bucket_name, 
                    object_name, 
                    expires=timedelta(seconds=expiry)
                )
                
                # 验证预签名URL是否可以访问
                import requests
                try:
                    response = requests.head(url, timeout=5)
                    if response.status_code == 200:
                        return url
                    else:
                        print(f"⚠ 预签名URL验证失败，状态码: {response.status_code}")
                except requests.RequestException as e:
                    print(f"⚠ 预签名URL验证异常: {e}")
                
                # 如果预签名URL不可用，回退到直接URL
                if settings.minio_public_endpoint:
                    # 如果公共端点没有协议前缀，添加http://
                    public_endpoint = settings.minio_public_endpoint
                    if not public_endpoint.startswith(('http://', 'https://')):
                        public_endpoint = 'http://' + public_endpoint
                    
                    # 确保公共端点不以/结尾
                    public_endpoint = public_endpoint.rstrip('/')
                    
                    # 构建直接URL
                    direct_url = f"{public_endpoint}/{self.bucket_name}/{object_name}"
                    print(f"✓ 使用直接URL: {direct_url}")
                    return direct_url
                else:
                    return url
                    
            except S3Error as e:
                print(f"✗ 获取URL失败: {e}")
                return None
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _get_url
        )
    
    async def delete_file(self, object_name: str) -> bool:
        """删除文件"""
        def _delete():
            try:
                self.client.remove_object(self.bucket_name, object_name)
                return True
            except S3Error as e:
                print(f"✗ 文件删除失败: {e}")
                return False
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _delete
        )
    
    async def file_exists(self, object_name: str) -> bool:
        """检查文件是否存在"""
        def _exists():
            try:
                self.client.stat_object(self.bucket_name, object_name)
                return True
            except S3Error:
                return False
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _exists
        )
    
    def generate_object_name(self, user_id: int, project_id: int, filename: str) -> str:
        """生成MinIO对象名称"""
        return f"users/{user_id}/projects/{project_id}/videos/{filename}"
    
    def generate_audio_object_name(self, user_id: int, project_id: int, video_id: str, audio_format: str = "wav") -> str:
        """生成音频对象名称"""
        return f"users/{user_id}/projects/{project_id}/audio/{video_id}.{audio_format}"
    
    def generate_thumbnail_object_name(self, user_id: int, project_id: int, video_id: str) -> str:
        """生成缩略图对象名称"""
        return f"users/{user_id}/projects/{project_id}/thumbnails/{video_id}.jpg"
    
    def generate_split_audio_object_name(self, user_id: int, project_id: int, video_id: str, segment_index: int) -> str:
        """生成分割音频对象名称"""
        return f"users/{user_id}/projects/{project_id}/splits/{video_id}/segment_{segment_index:03d}.wav"
    
    def generate_srt_object_name(self, user_id: int, project_id: int, video_id: str) -> str:
        """生成SRT字幕对象名称"""
        return f"users/{user_id}/projects/{project_id}/subtitles/{video_id}.srt"
    
    def generate_asr_json_object_name(self, user_id: int, project_id: int, video_id: str) -> str:
        """生成ASR JSON结果对象名称"""
        return f"users/{user_id}/projects/{project_id}/asr_results/{video_id}_asr_result.json"
    
    def generate_slice_object_name(self, user_id: int, project_id: int, video_id: int, filename: str) -> str:
        """生成视频切片对象名称"""
        import uuid
        slice_uuid = str(uuid.uuid4())
        return f"users/{user_id}/projects/{project_id}/slices/{slice_uuid}/{filename}"
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试MinIO连接和配置"""
        def _test():
            try:
                # 测试连接
                buckets = self.client.list_buckets()
                
                # 测试桶是否存在
                bucket_exists = self.client.bucket_exists(self.bucket_name)
                
                # 测试策略设置
                try:
                    policy = self.client.get_bucket_policy(self.bucket_name)
                    has_policy = bool(policy)
                except:
                    has_policy = False
                
                return {
                    "connected": True,
                    "buckets_count": len(buckets),
                    "bucket_exists": bucket_exists,
                    "has_policy": has_policy,
                    "endpoint": settings.minio_endpoint,
                    "bucket_name": self.bucket_name,
                    "secure": settings.minio_secure
                }
            except Exception as e:
                return {
                    "connected": False,
                    "error": str(e),
                    "endpoint": settings.minio_endpoint,
                    "bucket_name": self.bucket_name
                }
        
        return await asyncio.get_event_loop().run_in_executor(
            self.executor, _test
        )

# 全局实例
minio_service = MinioService()