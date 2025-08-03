#!/usr/bin/env python3
"""
模拟WebSocket端点逻辑测试
"""
import asyncio
from app.core.security import get_current_user_from_token
from app.core.database import AsyncSessionLocal, get_db

async def test_websocket_logic():
    """测试WebSocket端点的逻辑"""
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
        
        # 模拟WebSocket端点的逻辑
        try:
            async with AsyncSessionLocal() as db:
                print("🔍 验证token...")
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
                from app.api.v1.websocket import manager
                print("✅ 连接管理器获取成功")
                
        except Exception as e:
            print(f"❌ WebSocket端点逻辑异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ 登录失败: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_websocket_logic())