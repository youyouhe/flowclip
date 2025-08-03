#!/usr/bin/env python3
"""
测试JWT token验证
"""
import asyncio
from app.core.security import get_current_user_from_token
from app.core.database import AsyncSessionLocal

async def test_token_validation():
    """测试token验证"""
    # 获取token
    import requests
    
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"Token: {token}")
        
        # 测试token验证
        async with AsyncSessionLocal() as db:
            try:
                user = await get_current_user_from_token(token=token, db=db)
                if user:
                    print(f"✅ Token验证成功，用户: {user.username} (ID: {user.id})")
                else:
                    print("❌ Token验证失败，用户为空")
            except Exception as e:
                print(f"❌ Token验证异常: {e}")
                import traceback
                traceback.print_exc()
    else:
        print(f"❌ 登录失败: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_token_validation())