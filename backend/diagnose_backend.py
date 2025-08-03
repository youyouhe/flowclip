#!/usr/bin/env python3
"""
后端服务诊断脚本
"""
import requests
import json

def check_backend_status():
    """检查后端服务状态"""
    base_url = "http://localhost:8001"
    
    print("🔍 检查后端服务状态...")
    
    # 检查主端点
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务正常运行")
        else:
            print(f"❌ 后端服务异常: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 无法连接到后端服务: {e}")
        return False
    
    # 检查API端点
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ API端点正常")
        else:
            print(f"⚠️  API端点返回: {response.status_code}")
    except requests.exceptions.RequestException:
        print("⚠️  健康检查端点不可用")
    
    # 检查数据库连接
    try:
        response = requests.post(f"{base_url}/api/v1/auth/login", 
                               json={"email": "test@example.com", "password": "wrong_password"}, 
                               timeout=5)
        if response.status_code in [401, 422]:
            print("✅ 数据库连接正常")
        else:
            print(f"⚠️  数据库连接状态未知: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 数据库连接检查失败: {e}")
    
    return True

def check_websocket_endpoint():
    """检查WebSocket端点"""
    import websockets
    import asyncio
    
    async def test_websocket():
        uri = "ws://localhost:8001/ws/progress/invalid_token"
        try:
            async with websockets.connect(uri) as websocket:
                print("❌ WebSocket端点不应该接受无效token")
                return False
        except Exception as e:
            if "403" in str(e) or "Invalid token" in str(e):
                print("✅ WebSocket端点正常拒绝无效token")
                return True
            else:
                print(f"⚠️  WebSocket端点返回: {e}")
                return False
    
    print("🔍 检查WebSocket端点...")
    try:
        return asyncio.run(test_websocket())
    except Exception as e:
        print(f"❌ WebSocket检查失败: {e}")
        return False

def create_test_user():
    """创建测试用户"""
    print("🔍 创建测试用户...")
    
    user_data = {
        "email": "test@example.com",
        "password": "testpassword",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post("http://localhost:8001/api/v1/auth/register", 
                               json=user_data, timeout=5)
        
        if response.status_code in [200, 201]:
            print("✅ 测试用户创建成功")
            return True
        elif response.status_code == 400 and "already registered" in response.text:
            print("✅ 测试用户已存在")
            return True
        else:
            print(f"❌ 创建用户失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 创建用户请求失败: {e}")
        return False

def get_test_token():
    """获取测试token"""
    print("🔍 获取认证token...")
    
    login_data = {
        "email": "test@example.com",
        "password": "testpassword"
    }
    
    try:
        response = requests.post("http://localhost:8001/api/v1/auth/login", 
                               json=login_data, timeout=5)
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("✅ 成功获取认证token")
            return token
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

def main():
    """主诊断流程"""
    print("🚀 开始后端服务诊断")
    print("=" * 50)
    
    # 检查后端服务
    if not check_backend_status():
        print("\n❌ 后端服务未运行，请先启动服务:")
        print("   cd backend")
        print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        return
    
    print()
    
    # 检查WebSocket端点
    if not check_websocket_endpoint():
        print("\n❌ WebSocket端点异常")
        return
    
    print()
    
    # 创建测试用户
    if not create_test_user():
        print("\n❌ 无法创建测试用户")
        return
    
    print()
    
    # 获取测试token
    token = get_test_token()
    if not token:
        print("\n❌ 无法获取认证token")
        return
    
    print()
    print("🎉 所有检查通过！")
    print("现在可以运行 WebSocket 测试:")
    print("   python test_websocket_complete.py")
    print(f"   或者使用 token: {token[:20]}... 在测试HTML页面中")

if __name__ == "__main__":
    main()