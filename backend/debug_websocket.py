#!/usr/bin/env python3
"""
WebSocket连接调试脚本
"""
import asyncio
import websockets
import json
import requests
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_token():
    """测试token是否有效"""
    print("🔐 测试认证token...")
    
    # 获取token
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    try:
        response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"✅ Token获取成功: {token[:50]}...")
            return token
        else:
            print(f"❌ Token获取失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

async def test_websocket_with_debug(token):
    """带调试信息的WebSocket连接测试"""
    uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
    print(f"🔌 测试WebSocket连接...")
    print(f"   URI: {uri[:80]}...")
    
    try:
        # 创建WebSocket连接
        websocket = await websockets.connect(uri)
        print("✅ WebSocket连接建立成功")
        
        # 发送订阅消息
        subscribe_msg = {
            "type": "subscribe",
            "video_id": 1
        }
        await websocket.send(json.dumps(subscribe_msg))
        print("✅ 订阅消息发送成功")
        
        # 等待响应
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"✅ 收到响应: {data}")
            
            # 检查响应类型
            if data.get("type") == "progress_update":
                print("✅ 进度更新消息正常")
            elif data.get("type") == "error":
                print(f"⚠️  收到错误消息: {data.get('message')}")
            else:
                print(f"📨 收到其他类型消息: {data.get('type')}")
            
            await websocket.close()
            return True
            
        except asyncio.TimeoutError:
            print("⏰ 等待响应超时")
            await websocket.close()
            return False
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket连接被拒绝，状态码: {e.status_code}")
        return False
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")
        return False

async def test_api_endpoints():
    """测试API端点"""
    print("🔍 测试API端点...")
    
    # 测试健康检查
    try:
        response = requests.get("http://localhost:8001/", timeout=5)
        print(f"✅ 主端点正常: {response.status_code}")
    except Exception as e:
        print(f"❌ 主端点异常: {e}")
        return False
    
    # 测试用户信息端点
    try:
        token = await test_token()
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get("http://localhost:8001/api/v1/auth/me", headers=headers, timeout=5)
            if response.status_code == 200:
                user_info = response.json()
                print(f"✅ 用户信息获取成功: {user_info.get('username')}")
                return True
            else:
                print(f"❌ 用户信息获取失败: {response.status_code} - {response.text}")
        else:
            print("❌ 无法获取token")
    except Exception as e:
        print(f"❌ 用户信息请求失败: {e}")
    
    return False

async def main():
    """主测试流程"""
    print("🚀 开始WebSocket连接调试")
    print("=" * 60)
    
    # 测试API端点
    if not await test_api_endpoints():
        print("\n❌ API端点测试失败")
        return
    
    print()
    
    # 测试token
    token = await test_token()
    if not token:
        print("\n❌ Token测试失败")
        return
    
    print()
    
    # 测试WebSocket连接
    if await test_websocket_with_debug(token):
        print("\n🎉 WebSocket连接测试成功！")
    else:
        print("\n❌ WebSocket连接测试失败")
        print("\n可能的原因:")
        print("1. JWT token验证失败")
        print("2. WebSocket端点配置问题")
        print("3. CORS配置问题")
        print("4. 用户权限问题")

if __name__ == "__main__":
    asyncio.run(main())