#!/usr/bin/env python3
"""
简单的WebSocket连接测试脚本
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """测试WebSocket连接"""
    # 这里需要替换为有效的JWT token
    token = "your_jwt_token_here"
    video_id = 1
    
    uri = f"ws://localhost:8001/ws/progress/{token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket连接已建立")
            
            # 订阅视频进度
            subscribe_message = {
                "type": "subscribe",
                "video_id": video_id
            }
            
            await websocket.send(json.dumps(subscribe_message))
            logger.info(f"已订阅视频 {video_id} 的进度")
            
            # 监听消息
            async for message in websocket:
                data = json.loads(message)
                logger.info(f"收到消息: {data}")
                
                if data.get("type") == "progress_update":
                    logger.info(f"进度更新: {data.get('download_progress', 0)}%")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket连接已关闭")
    except Exception as e:
        logger.error(f"WebSocket连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())