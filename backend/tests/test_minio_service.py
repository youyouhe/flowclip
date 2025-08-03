import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.services.minio_client import MinioService
from app.core.config import settings


class TestMinioService:
    """测试MinIO服务类"""
    
    @pytest.fixture
    def minio_service(self):
        """创建MinIO服务实例"""
        return MinioService()
    
    @pytest.fixture
    def mock_minio_client(self):
        """创建模拟的MinIO客户端"""
        with patch('app.services.minio_client.Minio') as mock_client:
            yield mock_client
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_success(self, minio_service, mock_minio_client):
        """测试成功创建桶"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.bucket_exists.return_value = False
        mock_instance.make_bucket.return_value = None
        
        result = await minio_service.ensure_bucket_exists()
        
        assert result is True
        mock_instance.bucket_exists.assert_called_once_with(minio_service.bucket_name)
        mock_instance.make_bucket.assert_called_once_with(minio_service.bucket_name)
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_already_exists(self, minio_service, mock_minio_client):
        """测试桶已存在的情况"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.bucket_exists.return_value = True
        
        result = await minio_service.ensure_bucket_exists()
        
        assert result is True
        mock_instance.bucket_exists.assert_called_once_with(minio_service.bucket_name)
        mock_instance.make_bucket.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_failure(self, minio_service, mock_minio_client):
        """测试创建桶失败"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.bucket_exists.side_effect = Exception("MinIO connection failed")
        
        result = await minio_service.ensure_bucket_exists()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, minio_service, mock_minio_client):
        """测试文件上传成功"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.fput_object.return_value = None
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
            tmp_file.write(b"test content")
            tmp_path = tmp_file.name
        
        try:
            result = await minio_service.upload_file(tmp_path, "test-object.txt", "text/plain")
            assert result == f"{minio_service.bucket_name}/test-object.txt"
            mock_instance.fput_object.assert_called_once()
        finally:
            os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_upload_file_failure(self, minio_service, mock_minio_client):
        """测试文件上传失败"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.fput_object.side_effect = S3Error("test", "error", "resource", "request_id", "host_id")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            result = await minio_service.upload_file(tmp_path, "test-object.txt", "text/plain")
            assert result is None
        finally:
            os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_upload_file_content_success(self, minio_service, mock_minio_client):
        """测试文件内容上传成功"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.put_object.return_value = None
        
        content = b"test content"
        result = await minio_service.upload_file_content(content, "test-object.txt", "text/plain")
        
        assert result == f"{minio_service.bucket_name}/test-object.txt"
        mock_instance.put_object.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_file_content_failure(self, minio_service, mock_minio_client):
        """测试文件内容上传失败"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.put_object.side_effect = S3Error("test", "error", "resource", "request_id", "host_id")
        
        content = b"test content"
        result = await minio_service.upload_file_content(content, "test-object.txt", "text/plain")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_file_url_success(self, minio_service, mock_minio_client):
        """测试获取文件URL成功"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.presigned_get_object.return_value = "http://minio.example.com/test-url"
        
        result = await minio_service.get_file_url("test-object.txt", 3600)
        
        assert result == "http://minio.example.com/test-url"
        mock_instance.presigned_get_object.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_file_url_failure(self, minio_service, mock_minio_client):
        """测试获取文件URL失败"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.presigned_get_object.side_effect = S3Error("test", "error", "resource", "request_id", "host_id")
        
        result = await minio_service.get_file_url("test-object.txt", 3600)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self, minio_service, mock_minio_client):
        """测试删除文件成功"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.remove_object.return_value = None
        
        result = await minio_service.delete_file("test-object.txt")
        
        assert result is True
        mock_instance.remove_object.assert_called_once_with(
            minio_service.bucket_name, "test-object.txt"
        )
    
    @pytest.mark.asyncio
    async def test_delete_file_failure(self, minio_service, mock_minio_client):
        """测试删除文件失败"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.remove_object.side_effect = S3Error("test", "error", "resource", "request_id", "host_id")
        
        result = await minio_service.delete_file("test-object.txt")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_file_exists_success(self, minio_service, mock_minio_client):
        """测试文件存在检查成功"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.stat_object.return_value = Mock()
        
        result = await minio_service.file_exists("test-object.txt")
        
        assert result is True
        mock_instance.stat_object.assert_called_once_with(
            minio_service.bucket_name, "test-object.txt"
        )
    
    @pytest.mark.asyncio
    async def test_file_exists_not_found(self, minio_service, mock_minio_client):
        """测试文件不存在"""
        mock_instance = Mock()
        mock_minio_client.return_value = mock_instance
        mock_instance.stat_object.side_effect = S3Error("NoSuchKey", "error", "resource", "request_id", "host_id")
        
        result = await minio_service.file_exists("test-object.txt")
        
        assert result is False
    
    def test_generate_object_name(self, minio_service):
        """测试生成对象名称"""
        result = minio_service.generate_object_name(1, 2, "test_video.mp4")
        expected = "users/1/projects/2/videos/test_video.mp4"
        assert result == expected
    
    def test_generate_audio_object_name(self, minio_service):
        """测试生成音频对象名称"""
        result = minio_service.generate_audio_object_name(1, 2, "video123")
        expected = "users/1/projects/2/audio/video123.mp3"
        assert result == expected
    
    def test_generate_thumbnail_object_name(self, minio_service):
        """测试生成缩略图对象名称"""
        result = minio_service.generate_thumbnail_object_name(1, 2, "video123")
        expected = "users/1/projects/2/thumbnails/video123.jpg"
        assert result == expected


class TestMinioIntegration:
    """集成测试 - 需要实际的MinIO服务"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_minio_operations(self, minio_service):
        """测试实际的MinIO操作（需要运行中的MinIO服务）"""
        # 确保桶存在
        bucket_created = await minio_service.ensure_bucket_exists()
        assert bucket_created is True
        
        # 测试文件上传
        test_content = b"Hello, MinIO!"
        object_name = "test/test-file.txt"
        
        upload_result = await minio_service.upload_file_content(
            test_content, object_name, "text/plain"
        )
        assert upload_result is not None
        
        # 测试文件存在检查
        exists = await minio_service.file_exists(object_name)
        assert exists is True
        
        # 测试获取文件URL
        url = await minio_service.get_file_url(object_name, 60)
        assert url is not None
        assert "presigned" in url or "minio" in url.lower()
        
        # 测试删除文件
        deleted = await minio_service.delete_file(object_name)
        assert deleted is True
        
        # 确认文件已被删除
        exists_after = await minio_service.file_exists(object_name)
        assert exists_after is False


if __name__ == "__main__":
    pytest.main([__file__])