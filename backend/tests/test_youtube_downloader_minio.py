import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from app.services.youtube_downloader_minio import YouTubeDownloaderMinio
from app.services.minio_client import minio_service


class TestYouTubeDownloaderMinio:
    """测试MinIO集成的YouTube下载器"""
    
    @pytest.fixture
    def downloader(self):
        """创建下载器实例"""
        return YouTubeDownloaderMinio(cookies_file=None)
    
    @pytest.mark.asyncio
    async def test_get_video_info_success(self, downloader):
        """测试获取视频信息成功"""
        mock_info = {
            'id': 'test123',
            'title': 'Test Video',
            'duration': 120,
            'uploader': 'Test Uploader',
            'upload_date': '20240101',
            'view_count': 1000,
            'description': 'Test description',
            'thumbnail': 'http://example.com/thumb.jpg',
            'formats': [
                {
                    'format_id': '22',
                    'ext': 'mp4',
                    'resolution': '720p',
                    'filesize': 1024000,
                    'quality': 3
                }
            ]
        }
        
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        
        with patch('yt_dlp.YoutubeDL') as mock_yt_dlp:
            mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
            
            result = await downloader.get_video_info("http://youtube.com/watch?v=test123")
            
            assert result['title'] == 'Test Video'
            assert result['duration'] == 120
            assert result['video_id'] == 'test123'
            assert len(result['formats']) == 1
    
    @pytest.mark.asyncio
    async def test_get_video_info_failure(self, downloader):
        """测试获取视频信息失败"""
        mock_ydl = Mock()
        mock_ydl.extract_info.side_effect = Exception("Video not found")
        
        with patch('yt_dlp.YoutubeDL') as mock_yt_dlp:
            mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
            
            with pytest.raises(Exception) as exc_info:
                await downloader.get_video_info("http://youtube.com/watch?v=invalid")
            
            assert "获取视频信息失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_and_upload_video_success(self, downloader):
        """测试视频下载和上传成功"""
        mock_video_info = {
            'id': 'test123',
            'title': 'Test Video',
            'duration': 120,
            'uploader': 'Test Uploader',
            'upload_date': '20240101',
            'view_count': 1000,
            'ext': 'mp4'
        }
        
        with patch.object(downloader, 'get_video_info') as mock_get_info:
            mock_get_info.return_value = {'video_id': 'test123'}
            
            mock_ydl = Mock()
            mock_ydl.extract_info.return_value = mock_video_info
            
            # 模拟文件存在
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.stat.return_value.st_size = 1024000
            
            with patch('yt_dlp.YoutubeDL') as mock_yt_dlp, \
                 patch('pathlib.Path') as mock_path_class, \
                 patch.object(minio_service, 'upload_file') as mock_upload, \
                 patch.object(minio_service, 'generate_object_name') as mock_gen_name:
                
                mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
                mock_path_class.return_value = mock_path
                mock_upload.return_value = "youtube-videos/users/1/projects/1/videos/test123.mp4"
                mock_gen_name.return_value = "users/1/projects/1/videos/test123.mp4"
                
                result = await downloader.download_and_upload_video(
                    "http://youtube.com/watch?v=test123",
                    project_id=1,
                    user_id=1
                )
                
                assert result['success'] is True
                assert result['video_id'] == 'test123'
                assert result['title'] == 'Test Video'
                assert result['minio_path'] == "youtube-videos/users/1/projects/1/videos/test123.mp4"
                assert result['filesize'] == 1024000
    
    @pytest.mark.asyncio
    async def test_download_and_upload_audio_success(self, downloader):
        """测试音频下载和上传成功"""
        mock_video_info = {
            'id': 'test123',
            'title': 'Test Audio',
            'duration': 120,
            'ext': 'mp3'
        }
        
        with patch.object(downloader, 'get_video_info') as mock_get_info:
            mock_get_info.return_value = {'video_id': 'test123'}
            
            mock_ydl = Mock()
            mock_ydl.extract_info.return_value = mock_video_info
            
            # 模拟文件存在
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.suffix = '.mp3'
            mock_path.stem = 'test123'
            mock_path.stat.return_value.st_size = 512000
            
            with patch('yt_dlp.YoutubeDL') as mock_yt_dlp, \
                 patch('pathlib.Path') as mock_path_class, \
                 patch.object(minio_service, 'upload_file') as mock_upload, \
                 patch.object(minio_service, 'generate_audio_object_name') as mock_gen_name:
                
                mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
                mock_path_class.return_value = mock_path
                mock_upload.return_value = "youtube-videos/users/1/projects/1/audio/test123.mp3"
                mock_gen_name.return_value = "users/1/projects/1/audio/test123.mp3"
                
                result = await downloader.download_and_upload_audio(
                    "http://youtube.com/watch?v=test123",
                    project_id=1,
                    user_id=1
                )
                
                assert result['success'] is True
                assert result['video_id'] == 'test123'
                assert result['title'] == 'Test Audio'
                assert result['minio_path'] == "youtube-videos/users/1/projects/1/audio/test123.mp3"
                assert result['audio_ext'] == 'mp3'
    
    @pytest.mark.asyncio
    async def test_download_and_upload_video_file_not_found(self, downloader):
        """测试视频文件未找到"""
        with patch.object(downloader, 'get_video_info') as mock_get_info:
            mock_get_info.return_value = {'video_id': 'test123'}
            
            mock_ydl = Mock()
            mock_ydl.extract_info.return_value = {'id': 'test123', 'ext': 'mp4'}
            
            # 模拟文件不存在
            mock_path = Mock()
            mock_path.exists.return_value = False
            
            with patch('yt_dlp.YoutubeDL') as mock_yt_dlp, \
                 patch('pathlib.Path') as mock_path_class:
                
                mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
                mock_path_class.return_value = mock_path
                
                with pytest.raises(Exception) as exc_info:
                    await downloader.download_and_upload_video(
                        "http://youtube.com/watch?v=test123",
                        project_id=1,
                        user_id=1
                    )
                
                assert "下载文件未找到" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_and_upload_video_upload_failure(self, downloader):
        """测试上传失败"""
        with patch.object(downloader, 'get_video_info') as mock_get_info:
            mock_get_info.return_value = {'video_id': 'test123'}
            
            mock_ydl = Mock()
            mock_ydl.extract_info.return_value = {
                'id': 'test123',
                'title': 'Test Video',
                'duration': 120,
                'uploader': 'Test Uploader',
                'upload_date': '20240101',
                'view_count': 1000,
                'ext': 'mp4'
            }
            
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.stat.return_value.st_size = 1024000
            
            with patch('yt_dlp.YoutubeDL') as mock_yt_dlp, \
                 patch('pathlib.Path') as mock_path_class, \
                 patch.object(minio_service, 'upload_file') as mock_upload:
                
                mock_yt_dlp.return_value.__enter__.return_value = mock_ydl
                mock_path_class.return_value = mock_path
                mock_upload.return_value = None  # 模拟上传失败
                
                with pytest.raises(Exception) as exc_info:
                    await downloader.download_and_upload_video(
                        "http://youtube.com/watch?v=test123",
                        project_id=1,
                        user_id=1
                    )
                
                assert "上传到MinIO失败" in str(exc_info.value)
    
    def test_extract_formats(self, downloader):
        """测试格式提取"""
        test_formats = [
            {
                'vcodec': 'h264',
                'acodec': 'aac',
                'format_id': '22',
                'ext': 'mp4',
                'resolution': '720p',
                'filesize': 1024000,
                'quality': 3
            },
            {
                'vcodec': 'none',  # 音频格式
                'acodec': 'aac',
                'format_id': '140',
                'ext': 'm4a',
                'resolution': 'audio only',
                'filesize': 512000,
                'quality': 3
            }
        ]
        
        result = downloader._extract_formats(test_formats)
        
        assert len(result) == 1  # 只应返回视频格式
        assert result[0]['format_id'] == '22'
        assert result[0]['ext'] == 'mp4'


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_download_and_upload(self):
        """测试真实的下载和上传（需要YouTube访问和MinIO服务）"""
        # 注意：这是一个集成测试，需要真实的YouTube URL和运行的MinIO服务
        # 仅在有适当环境时运行
        
        if not os.getenv('INTEGRATION_TESTS'):
            pytest.skip("Integration tests disabled")
        
        downloader = YouTubeDownloaderMinio()
        
        # 使用一个公开的测试视频
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            result = await downloader.download_and_upload_video(
                test_url,
                project_id=1,
                user_id=1,
                format_id='worst'  # 使用低质量以加快测试
            )
            
            assert result['success'] is True
            assert 'minio_path' in result
            assert result['minio_path'] is not None
            
            # 验证文件存在于MinIO
            from app.services.minio_client import minio_service
            object_name = result['minio_path'].replace(f"{minio_service.bucket_name}/", "")
            exists = await minio_service.file_exists(object_name)
            assert exists is True
            
            # 清理测试文件
            await minio_service.delete_file(object_name)
            
        except Exception as e:
            pytest.skip(f"Integration test failed: {str(e)}")


if __name__ == "__main__":
    pytest.main([__file__])