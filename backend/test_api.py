#!/usr/bin/env python3
"""
YouTube Slicer API 测试脚本
运行所有API端点的测试，包括认证、项目、视频、处理和上传功能
"""

import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any, Optional

# 配置
BASE_URL = "http://localhost:8001"
HEADERS = {"Content-Type": "application/json"}

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
        self.token = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def request(self, method: str, endpoint: str, data: Dict = None, auth: bool = True, form_data: bool = False) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {}
        if not form_data:
            headers.update(HEADERS)
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        kwargs = {}
        if form_data:
            kwargs["data"] = data
        else:
            if method.upper() in ["POST", "PUT", "PATCH"]:
                kwargs["json"] = data
            elif method.upper() == "GET":
                kwargs["params"] = data
                
        async with self.session.request(
            method, url, 
            headers=headers,
            **kwargs
        ) as response:
            try:
                result = await response.json()
            except:
                result = {"status": response.status, "text": await response.text()}
            
            print(f"{method} {endpoint} - Status: {response.status}")
            if response.status >= 400:
                print(f"  Error: {result}")
            return result
    
    async def test_health_check(self):
        """测试健康检查"""
        print("\n=== 健康检查测试 ===")
        result = await self.request("GET", "/health", auth=False)
        assert result.get("status") == "healthy", "健康检查失败"
        print("✅ 健康检查通过")
    
    async def test_root_endpoint(self):
        """测试根端点"""
        print("\n=== 根端点测试 ===")
        result = await self.request("GET", "/", auth=False)
        assert result.get("message") == "YouTube Slicer API", "根端点失败"
        print("✅ 根端点测试通过")
    
    async def test_docs_endpoint(self):
        """测试文档端点"""
        print("\n=== 文档端点测试 ===")
        # 只检查状态码，不解析HTML
        url = f"{self.base_url}/docs"
        async with self.session.get(url) as response:
            assert response.status == 200, f"文档端点失败: {response.status}"
            content_type = response.headers.get('content-type', '')
            assert 'text/html' in content_type, f"文档不是HTML: {content_type}"
        print("✅ 文档端点测试通过")
    
    async def test_auth_endpoints(self):
        """测试认证相关端点"""
        print("\n=== 认证API测试 ===")
        
        # 测试注册
        register_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
            "full_name": "Test User"
        }
        
        try:
            register_result = await self.request("POST", "/api/v1/auth/register", register_data, auth=False)
            print(f"注册结果: {register_result}")
            
            # 测试登录（使用表单格式）
            login_data = {
                "username": "testuser",
                "password": "testpassword123"
            }
            
            login_result = await self.request("POST", "/api/v1/auth/login", login_data, auth=False, form_data=True)
            if "access_token" in login_result:
                self.token = login_result["access_token"]
                print("✅ 登录成功，获取token")
                
                # 测试获取当前用户信息
                me_result = await self.request("GET", "/api/v1/auth/me")
                assert me_result["username"] == "testuser", "用户信息错误"
                print("✅ 用户信息获取成功")
            else:
                print("❌ 登录失败")
        except Exception as e:
            print(f"❌ 认证测试失败: {e}")
    
    async def test_project_endpoints(self):
        """测试项目相关端点"""
        if not self.token:
            print("❌ 跳过项目测试：未登录")
            return
            
        print("\n=== 项目API测试 ===")
        
        # 获取项目列表
        projects = await self.request("GET", "/api/v1/projects/")
        assert isinstance(projects, dict), "项目列表格式错误"
        print("✅ 项目列表获取成功")
        
        # 创建项目
        project_data = {
            "name": "测试项目",
            "description": "这是一个测试项目"
        }
        
        create_result = await self.request("POST", "/api/v1/projects/", project_data)
        print(f"创建项目结果: {create_result}")
    
    async def test_video_endpoints(self):
        """测试视频相关端点"""
        if not self.token:
            print("❌ 跳过视频测试：未登录")
            return
            
        print("\n=== 视频API测试 ===")
        
        # 获取视频列表
        videos = await self.request("GET", "/api/v1/videos/")
        assert isinstance(videos, dict), "视频列表格式错误"
        print("✅ 视频列表获取成功")
    
    async def test_processing_endpoints(self):
        """测试处理相关端点"""
        if not self.token:
            print("❌ 跳过处理测试：未登录")
            return
            
        print("\n=== 处理API测试 ===")
        
        # 测试处理状态端点
        status = await self.request("GET", "/api/v1/processing/status/test-task")
        print(f"处理状态测试: {status}")
    
    async def test_upload_endpoints(self):
        """测试上传相关端点"""
        if not self.token:
            print("❌ 跳过上载测试：未登录")
            return
            
        print("\n=== 上传API测试 ===")
        
        # 测试YouTube认证URL
        auth_url = await self.request("GET", "/api/v1/upload/youtube/auth-url")
        print(f"YouTube认证URL测试: {auth_url}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始YouTube Slicer API测试...")
        print(f"测试地址: {self.base_url}")
        
        try:
            # 基础测试
            await self.test_health_check()
            await self.test_root_endpoint()
            await self.test_docs_endpoint()
            
            # 认证测试
            await self.test_auth_endpoints()
            
            # 功能测试
            await self.test_project_endpoints()
            await self.test_video_endpoints()
            await self.test_processing_endpoints()
            await self.test_upload_endpoints()
            
            print("\n🎉 所有测试完成！")
            
        except Exception as e:
            print(f"\n❌ 测试中断: {e}")
            raise

async def main():
    """主测试函数"""
    async with APITester(BASE_URL) as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())