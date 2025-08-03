#!/usr/bin/env python3
"""
通过HTTP测试WebSocket端点的token验证逻辑
"""
import requests
import json

def test_websocket_token_via_http():
    """通过HTTP测试WebSocket端点的token验证逻辑"""
    print("🔍 通过HTTP测试WebSocket端点token验证...")
    
    # 获取token
    login_data = {
        "username": "hem",
        "password": "123456"
    }
    
    response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"✅ Token获取成功")
        
        # 尝试通过HTTP访问WebSocket端点（这应该会失败，但可以显示错误信息）
        headers = {
            "Authorization": f"Bearer {token}",
            "Upgrade": "websocket",
            "Connection": "Upgrade"
        }
        
        try:
            response = requests.get(
                f"http://localhost:8001/api/v1/ws/progress/{token}",
                headers=headers,
                timeout=5
            )
            print(f"HTTP响应状态码: {response.status_code}")
            print(f"HTTP响应内容: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"HTTP请求失败: {e}")
            
        # 也尝试不带WebSocket头的请求
        try:
            response = requests.get(
                f"http://localhost:8001/api/v1/ws/progress/{token}",
                timeout=5
            )
            print(f"普通HTTP响应状态码: {response.status_code}")
            print(f"普通HTTP响应内容: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"普通HTTP请求失败: {e}")
            
    else:
        print(f"❌ Token获取失败: {response.status_code}")

if __name__ == "__main__":
    test_websocket_token_via_http()