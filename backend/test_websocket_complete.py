#!/usr/bin/env python3
"""
WebSocket连接测试脚本 - 包含用户认证
"""
import asyncio
import websockets
import json
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 后端API配置
BASE_URL = "http://localhost:8001"
API_URL = f"{BASE_URL}/api/v1"

async def get_auth_token():
    """获取认证token"""
    # 使用测试用户凭据
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    try:
        response = requests.post(f"{API_URL}/auth/login", data=login_data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            logger.info("成功获取认证token")
            return token
        else:
            logger.error(f"登录失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"登录请求失败: {e}")
        return None

async def create_test_user():
    """创建测试用户"""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(f"{API_URL}/auth/register", json=user_data)
        if response.status_code in [200, 201, 400]:  # 400表示用户已存在
            logger.info("测试用户已存在或创建成功")
            return True
        else:
            logger.error(f"创建用户失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"创建用户请求失败: {e}")
        return False

async def create_test_project(token):
    """创建测试项目"""
    project_data = {
        "name": "WebSocket测试项目",
        "description": "用于测试WebSocket连接的项目"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(f"{API_URL}/projects", json=project_data, headers=headers)
        if response.status_code in [200, 201]:
            project_id = response.json().get("id")
            logger.info(f"测试项目创建成功，ID: {project_id}")
            return project_id
        else:
            logger.error(f"创建项目失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"创建项目请求失败: {e}")
        return None

async def start_video_download(token, project_id):
    """启动视频下载任务"""
    download_data = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # 示例视频
        "project_id": project_id
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(f"{API_URL}/videos/download", json=download_data, headers=headers)
        if response.status_code in [200, 201]:
            video_id = response.json().get("video_id")
            logger.info(f"下载任务已启动，视频ID: {video_id}")
            return video_id
        else:
            logger.error(f"启动下载失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"启动下载请求失败: {e}")
        return None

async def test_websocket_connection(token, video_id):
    """测试WebSocket连接"""
    uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket连接已建立")
            
            # 订阅视频进度
            subscribe_message = {
                "type": "subscribe",
                "video_id": video_id
            }
            
            await websocket.send(json.dumps(subscribe_message))
            logger.info(f"✅ 已订阅视频 {video_id} 的进度")
            
            # 监听消息（30秒超时）
            try:
                for i in range(30):  # 30秒超时
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        logger.info(f"📨 收到消息: {data}")
                        
                        if data.get("type") == "progress_update":
                            progress = data.get('download_progress', 0)
                            stage = data.get('processing_stage', 'unknown')
                            logger.info(f"📊 进度更新: {progress}% - {stage}")
                        
                        elif data.get("type") == "pong":
                            logger.info("💓 收到心跳响应")
                        
                    except asyncio.TimeoutError:
                        # 每10秒发送一次心跳
                        if i % 10 == 0:
                            await websocket.send(json.dumps({"type": "ping"}))
                            logger.info("💓 发送心跳")
                        continue
                
                logger.info("⏰ 测试超时，连接正常")
                
            except websockets.exceptions.ConnectionClosed:
                logger.info("🔌 WebSocket连接已关闭")
                
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"❌ WebSocket连接被拒绝: {e}")
    except Exception as e:
        logger.error(f"❌ WebSocket连接失败: {e}")

async def main():
    """主测试流程"""
    logger.info("🚀 开始WebSocket连接测试")
    
    # 1. 创建测试用户
    await create_test_user()
    
    # 2. 获取认证token
    token = await get_auth_token()
    if not token:
        logger.error("❌ 无法获取认证token，测试终止")
        return
    
    # 3. 创建测试项目
    project_id = await create_test_project(token)
    if not project_id:
        logger.error("❌ 无法创建测试项目，测试终止")
        return
    
    # 4. 启动视频下载任务
    video_id = await start_video_download(token, project_id)
    if not video_id:
        logger.error("❌ 无法启动下载任务，测试终止")
        return
    
    # 5. 测试WebSocket连接
    await test_websocket_connection(token, video_id)
    
    logger.info("🏁 测试完成")

if __name__ == "__main__":
    asyncio.run(main())