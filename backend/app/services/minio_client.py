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
        self.client = Minio(
            settings.minio_endpoint,
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
                url = self.client.presigned_get_object(
                    self.bucket_name, 
                    object_name, 
                    expires=timedelta(seconds=expiry)
                )
                
                # 安全地替换URL中的主机名，不破坏签名
                # 使用urlparse来正确处理URL，避免破坏查询参数和签名
                from urllib.parse import urlparse, urlunparse
                
                parsed = urlparse(url)
                
                # 如果配置了公共端点，使用公共端点
                if settings.minio_public_endpoint:
                    # 解析公共端点，移除协议前缀
                    from urllib.parse import urlparse
                    public_parsed = urlparse(settings.minio_public_endpoint)
                    new_netloc = public_parsed.netloc
                    
                    # 如果公共端点没有指定协议，使用原协议
                    new_scheme = public_parsed.scheme if public_parsed.scheme else parsed.scheme
                    
                    # 重建URL，保持所有其他部分不变
                    new_url = urlunparse((
                        new_scheme,
                        new_netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment
                    ))
                    return new_url
                
                # 如果没有配置公共端点，使用原始URL
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