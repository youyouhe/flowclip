#!/usr/bin/env python3
"""
简单的WebSocket连接测试
"""
import asyncio
import websockets
import requests
import json

async def simple_websocket_test():
    """简单的WebSocket连接测试"""
    print("🔍 简单WebSocket连接测试...")
    
    # 获取token
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"✅ Token获取成功")
        
        # 测试WebSocket连接
        uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
        print(f"🔌 尝试连接: {uri[:60]}...")
        
        try:
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket连接成功")
                
                # 发送简单的ping消息
                await websocket.send(json.dumps({"type": "ping"}))
                print("✅ Ping消息发送成功")
                
                # 等待响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"✅ 收到响应: {response}")
                except asyncio.TimeoutError:
                    print("⏰ 等待响应超时")
                
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            print(f"   错误类型: {type(e).__name__}")
            
            # 如果是HTTP错误，尝试获取更多信息
            if hasattr(e, 'status_code'):
                print(f"   状态码: {e.status_code}")
            if hasattr(e, 'headers'):
                print(f"   响应头: {e.headers}")
                
    else:
        print(f"❌ Token获取失败: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(simple_websocket_test())