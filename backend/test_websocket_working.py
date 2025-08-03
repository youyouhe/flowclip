#!/usr/bin/env python3
"""
测试WebSocket连接的简单脚本
"""
import asyncio
import websockets
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket():
    """测试WebSocket连接"""
    # 首先获取token
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    try:
        # 登录获取token
        response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
        if response.status_code != 200:
            logger.error(f"登录失败: {response.status_code}")
            return
        
        token = response.json().get("access_token")
        logger.info(f"获取到token: {token[:50]}...")
        
        # 连接WebSocket
        uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
        logger.info(f"连接WebSocket: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket连接成功")
            
            # 发送ping消息
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))
            logger.info("已发送ping消息")
            
            # 等待pong响应
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"收到响应: {data}")
            
            # 测试订阅视频进度
            subscribe_message = {
                "type": "subscribe",
                "video_id": 24
            }
            await websocket.send(json.dumps(subscribe_message))
            logger.info("已发送订阅消息")
            
            # 等待进度更新
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"收到进度更新: {data}")
            
    except Exception as e:
        logger.error(f"WebSocket测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket())
