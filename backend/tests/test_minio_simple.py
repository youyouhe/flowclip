import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.minio_client import MinioService


class TestMinioServiceSimple:
    """MinIO服务简单测试"""
    
    def test_generate_object_name(self):
        """测试生成对象名称"""
        service = MinioService()
        result = service.generate_object_name(1, 2, "test_video.mp4")
        expected = "users/1/projects/2/videos/test_video.mp4"
        assert result == expected
    
    def test_generate_audio_object_name(self):
        """测试生成音频对象名称"""
        service = MinioService()
        result = service.generate_audio_object_name(1, 2, "video123")
        expected = "users/1/projects/2/audio/video123.mp3"
        assert result == expected
    
    def test_generate_thumbnail_object_name(self):
        """测试生成缩略图对象名称"""
        service = MinioService()
        result = service.generate_thumbnail_object_name(1, 2, "video123")
        expected = "users/1/projects/2/thumbnails/video123.jpg"
        assert result == expected


class TestMinioOperationsMock:
    """使用Mock测试MinIO操作"""
    
    @pytest.fixture
    def minio_service(self):
        """创建MinIO服务实例"""
        return MinioService()
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_success(self, minio_service):
        """测试成功创建桶"""
        with patch.object(minio_service.client, 'bucket_exists', return_value=False):
            with patch.object(minio_service.client, 'make_bucket') as mock_make:
                result = await minio_service.ensure_bucket_exists()
                assert result is True
                mock_make.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_file_content_success(self, minio_service):
        """测试文件内容上传成功"""
        with patch.object(minio_service.client, 'put_object') as mock_put:
            mock_put.return_value = None
            
            result = await minio_service.upload_file_content(
                b"test content", "test-object.txt", "text/plain"
            )
            
            assert result == f"{minio_service.bucket_name}/test-object.txt"
            mock_put.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_file_url_success(self, minio_service):
        """测试获取文件URL成功"""
        with patch.object(minio_service.client, 'presigned_get_object') as mock_url:
            mock_url.return_value = "http://minio.example.com/presigned-url"
            
            result = await minio_service.get_file_url("test-object.txt", 3600)
            
            assert result == "http://minio.example.com/presigned-url"
            mock_url.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])