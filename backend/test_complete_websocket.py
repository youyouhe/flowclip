#!/usr/bin/env python3
"""
完整测试WebSocket端点逻辑
"""
import asyncio
import json
from app.core.security import get_current_user_from_token
from app.core.database import AsyncSessionLocal
from app.api.v1.websocket import manager

async def test_complete_websocket_logic():
    """完整测试WebSocket端点逻辑"""
    import requests
    
    # 获取token
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"Token: {token[:50]}...")
        
        # 完整模拟WebSocket端点逻辑
        try:
            print("🔍 开始验证token...")
            async with AsyncSessionLocal() as db:
                user = await get_current_user_from_token(token=token, db=db)
                
                if not user:
                    print("❌ Token验证失败，用户为空")
                    return
                
                print(f"✅ Token验证成功，用户: {user.username} (ID: {user.id})")
                
                # 测试用户是否活跃
                if not user.is_active:
                    print("❌ 用户未激活")
                    return
                
                print("✅ 用户状态正常")
                
                # 测试连接管理器
                print("🔍 测试连接管理器...")
                user_id = user.id
                
                # 模拟WebSocket连接
                class MockWebSocket:
                    def __init__(self):
                        self.messages = []
                        self.closed = False
                    
                    async def send_text(self, message):
                        self.messages.append(message)
                        print(f"📨 发送消息: {message[:100]}...")
                    
                    async def close(self, code=None, reason=None):
                        self.closed = True
                        print(f"🔌 连接关闭: {code} - {reason}")
                
                mock_ws = MockWebSocket()
                
                # 测试连接
                await manager.connect(mock_ws, user_id)
                print("✅ 连接管理器连接成功")
                
                # 测试订阅逻辑
                print("🔍 测试订阅逻辑...")
                video_id = 1
                
                # 发送订阅消息
                subscribe_message = {
                    "type": "subscribe",
                    "video_id": video_id
                }
                
                message_str = json.dumps(subscribe_message)
                print(f"📨 处理订阅消息: {message_str}")
                
                # 模拟处理订阅消息
                message = json.loads(message_str)
                
                if message.get('type') == 'subscribe':
                    video_id = message.get('video_id')
                    if video_id:
                        print(f"✅ 订阅视频 {video_id}")
                        
                        # 测试发送当前进度
                        from app.api.v1.websocket import send_current_progress
                        await send_current_progress(mock_ws, video_id, user_id, db)
                        print("✅ 当前进度发送成功")
                        
                        # 检查发送的消息
                        if mock_ws.messages:
                            last_message = json.loads(mock_ws.messages[-1])
                            print(f"✅ 收到进度消息: {last_message.get('type', 'unknown')}")
                        else:
                            print("⚠️  未收到进度消息")
                
                # 测试断开连接
                manager.disconnect(user_id)
                print("✅ 连接管理器断开成功")
                
                print("🎉 完整WebSocket端点逻辑测试成功！")
                
        except Exception as e:
            print(f"❌ WebSocket端点逻辑异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ 登录失败: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_complete_websocket_logic())