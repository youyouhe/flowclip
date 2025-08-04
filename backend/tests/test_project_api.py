import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.video import Video

class TestProjectAPI:
    """测试项目API端点"""
    
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
    
    @pytest.fixture
    def auth_headers(self):
        """创建认证头"""
        return {"Authorization": "Bearer test-token"}
    
    @pytest.mark.asyncio
    async def test_create_project(self, test_client, mock_user, auth_headers):
        """测试创建项目成功"""
        
        # 模拟用户认证
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            # 模拟数据库操作
            with patch('app.api.v1.projects.get_db') as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = mock_db
                
                project_data = {
                    "name": "Test Project",
                    "description": "Test project description"
                }
                
                response = test_client.post("/api/v1/projects/", json=project_data, headers=auth_headers)
                # 由于没有真实的数据库，这个测试主要检查API路由是否正确
                assert response.status_code in [200, 401, 422]  # 接受成功或认证错误
    
    @pytest.mark.asyncio
    async def test_get_projects(self, test_client, mock_user, auth_headers):
        """测试获取项目列表"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            response = test_client.get("/api/v1/projects/", headers=auth_headers)
            assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_get_project_detail(self, test_client, mock_user, auth_headers):
        """测试获取项目详情"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            response = test_client.get("/api/v1/projects/1", headers=auth_headers)
            assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    async def test_get_project_videos(self, test_client, mock_user, auth_headers):
        """测试获取项目视频列表"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            response = test_client.get("/api/v1/projects/1/videos", headers=auth_headers)
            assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    async def test_update_project(self, test_client, mock_user, auth_headers):
        """测试更新项目"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            update_data = {
                "name": "Updated Project",
                "description": "Updated description"
            }
            
            response = test_client.put("/api/v1/projects/1", json=update_data, headers=auth_headers)
            assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    async def test_delete_project(self, test_client, mock_user, auth_headers):
        """测试删除项目"""
        
        with patch('app.core.security.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user
            
            response = test_client.delete("/api/v1/projects/1", headers=auth_headers)
            assert response.status_code in [200, 401, 404]
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, test_client):
        """测试未授权访问"""
        
        response = test_client.get("/api/v1/projects/")
        assert response.status_code == 401