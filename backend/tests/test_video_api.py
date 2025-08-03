import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from app.main import app
from app.core.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.video import Video


class TestVideoAPI:
    """测试视频API端点"""
    
    @pytest.fixture
    def test_client(self):
        """创建测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """创建测试用户"""
        return User(
            id=1,
            email="test@example.com",
            username="testuser",
            is_active=True
        )
    
    @pytest.fixture
    def mock_project(self):
        """创建测试项目"""
        return Project(
            id=1,
            name="Test Project",
            user_id=1,
            description="Test project"
        )
    
    @pytest.mark.asyncio
    async def test_download_video_success(self, test_client, mock_user, mock_project):
        """测试视频下载成功"""
        
        # 模拟用户认证
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            # 模拟数据库查询
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_project
                mock_execute.return_value = mock_result
                
                # 模拟视频信息获取
                with patch('app.services.youtube_downloader.downloader.get_video_info') as mock_info:
                    mock_info.return_value = {
                        'title': 'Test Video',
                        'description': 'Test Description',
                        'duration': 120,
                        'thumbnail': 'http://example.com/thumb.jpg'
                    }
                    
                    # 模拟数据库操作
                    with patch('sqlalchemy.ext.asyncio.AsyncSession.add') as mock_add, \
                         patch('sqlalchemy.ext.asyncio.AsyncSession.commit') as mock_commit, \
                         patch('sqlalchemy.ext.asyncio.AsyncSession.refresh') as mock_refresh:
                        
                        mock_video = Video(
                            id=1,
                            title="Test Video",
                            url="https://www.youtube.com/watch?v=test123",
                            project_id=1,
                            status="downloading"
                        )
                        mock_refresh.return_value = None
                        
                        response = test_client.post(
                            "/api/v1/videos/download",
                            json={
                                "url": "https://www.youtube.com/watch?v=test123",
                                "project_id": 1
                            }
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["title"] == "Test Video"
                        assert data["status"] == "downloading"
    
    @pytest.mark.asyncio
    async def test_download_video_project_not_found(self, test_client, mock_user):
        """测试项目不存在"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = None
                mock_execute.return_value = mock_result
                
                response = test_client.post(
                    "/api/v1/videos/download",
                    json={
                        "url": "https://www.youtube.com/watch?v=test123",
                        "project_id": 999
                    }
                )
                
                assert response.status_code == 404
                assert "Project not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_download_video_invalid_url(self, test_client, mock_user, mock_project):
        """测试无效的YouTube URL"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_project
                mock_execute.return_value = mock_result
                
                with patch('app.services.youtube_downloader.downloader.get_video_info') as mock_info:
                    mock_info.side_effect = Exception("Invalid URL")
                    
                    response = test_client.post(
                        "/api/v1/videos/download",
                        json={
                            "url": "https://invalid-url.com",
                            "project_id": 1
                        }
                    )
                    
                    assert response.status_code == 400
                    assert "无法获取视频信息" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_videos_success(self, test_client, mock_user):
        """测试获取视频列表成功"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [
                    Video(
                        id=1,
                        title="Test Video 1",
                        url="https://www.youtube.com/watch?v=test1",
                        project_id=1,
                        status="completed",
                        file_path="youtube-videos/users/1/projects/1/videos/test1.mp4"
                    ),
                    Video(
                        id=2,
                        title="Test Video 2",
                        url="https://www.youtube.com/watch?v=test2",
                        project_id=1,
                        status="downloading"
                    )
                ]
                mock_execute.return_value = mock_result
                
                response = test_client.get("/api/v1/videos/")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert data[0]["title"] == "Test Video 1"
                assert data[1]["title"] == "Test Video 2"
    
    @pytest.mark.asyncio
    async def test_get_video_download_url_success(self, test_client, mock_user):
        """测试获取视频下载URL成功"""
        
        mock_video = Video(
            id=1,
            title="Test Video",
            url="https://www.youtube.com/watch?v=test123",
            project_id=1,
            file_path="youtube-videos/users/1/projects/1/videos/test123.mp4"
        )
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_video
                mock_execute.return_value = mock_result
                
                with patch('app.services.minio_client.minio_service.get_file_url') as mock_url:
                    mock_url.return_value = "http://minio.example.com/presigned-url"
                    
                    response = test_client.get("/api/v1/videos/1/download-url")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["download_url"] == "http://minio.example.com/presigned-url"
                    assert data["expires_in"] == 3600
    
    @pytest.mark.asyncio
    async def test_get_video_download_url_not_found(self, test_client, mock_user):
        """测试视频不存在"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = None
                mock_execute.return_value = mock_result
                
                response = test_client.get("/api/v1/videos/999/download-url")
                
                assert response.status_code == 404
                assert "Video not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_delete_video_success(self, test_client, mock_user):
        """测试删除视频成功"""
        
        mock_video = Video(
            id=1,
            title="Test Video",
            url="https://www.youtube.com/watch?v=test123",
            project_id=1,
            file_path="/tmp/test123.mp4"
        )
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_video
                mock_execute.return_value = mock_result
                
                with patch('os.path.exists') as mock_exists, \
                     patch('os.remove') as mock_remove, \
                     patch('sqlalchemy.ext.asyncio.AsyncSession.delete') as mock_delete, \
                     patch('sqlalchemy.ext.asyncio.AsyncSession.commit') as mock_commit:
                    
                    mock_exists.return_value = True
                    mock_remove.return_value = None
                    mock_delete.return_value = None
                    mock_commit.return_value = None
                    
                    response = test_client.delete("/api/v1/videos/1")
                    
                    assert response.status_code == 200
                    assert response.json()["message"] == "Video deleted successfully"
    
    @pytest.mark.asyncio
    async def test_update_video_success(self, test_client, mock_user):
        """测试更新视频信息成功"""
        
        mock_video = Video(
            id=1,
            title="Old Title",
            url="https://www.youtube.com/watch?v=test123",
            project_id=1
        )
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = mock_video
                mock_execute.return_value = mock_result
                
                with patch('sqlalchemy.ext.asyncio.AsyncSession.commit') as mock_commit, \
                     patch('sqlalchemy.ext.asyncio.AsyncSession.refresh') as mock_refresh:
                    
                    mock_commit.return_value = None
                    mock_refresh.return_value = None
                    
                    response = test_client.put(
                        "/api/v1/videos/1",
                        json={
                            "title": "New Title",
                            "description": "New Description"
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["title"] == "New Title"
                    assert data["description"] == "New Description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])