#!/usr/bin/env python3
"""
简单的认证测试
"""
import requests
import json

def test_auth():
    """测试认证流程"""
    base_url = "http://localhost:8001"
    
    print("🔐 测试认证流程...")
    
    # 1. 注册用户
    print("1. 使用现有admin用户...")
    # 跳过注册步骤，直接使用现有的admin用户
    
    # 2. 登录获取token
    print("2. 使用hem用户登录获取token...")
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/auth/login", data=login_data)
        print(f"   登录响应: {response.status_code}")
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"   ✅ 登录成功，token: {token[:30]}...")
            return token
        else:
            print(f"   ❌ 登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ 登录请求失败: {e}")
        return None

def test_websocket_with_token(token):
    """使用有效token测试WebSocket"""
    import websockets
    import asyncio
    
    async def test_connection():
        uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
        print(f"3. 测试WebSocket连接...")
        print(f"   连接URL: {uri[:50]}...")
        
        try:
            async with websockets.connect(uri) as websocket:
                print("   ✅ WebSocket连接成功")
                
                # 发送订阅消息
                subscribe_msg = {
                    "type": "subscribe",
                    "video_id": 1
                }
                await websocket.send(json.dumps(subscribe_msg))
                print("   ✅ 发送订阅消息")
                
                # 等待响应
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"   ✅ 收到响应: {data.get('type', 'unknown')}")
                
                return True
                
        except Exception as e:
            print(f"   ❌ WebSocket连接失败: {e}")
            return False
    
    return asyncio.run(test_connection())

def main():
    """主测试流程"""
    print("🚀 开始认证和WebSocket测试")
    print("=" * 50)
    
    # 测试认证
    token = test_auth()
    if not token:
        print("\n❌ 认证测试失败")
        return
    
    print()
    
    # 测试WebSocket
    if test_websocket_with_token(token):
        print("\n🎉 所有测试通过！")
        print("WebSocket连接工作正常")
    else:
        print("\n❌ WebSocket测试失败")

if __name__ == "__main__":
    main()