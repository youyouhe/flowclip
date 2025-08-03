#!/usr/bin/env python3
"""
检查FastAPI路由配置
"""
import requests
import json

def check_routes():
    """检查FastAPI的路由配置"""
    print("🔍 检查FastAPI路由配置...")
    
    # 检查OpenAPI文档
    try:
        response = requests.get("http://localhost:8001/docs", timeout=5)
        if response.status_code == 200:
            print("✅ OpenAPI文档可访问")
        else:
            print(f"⚠️  OpenAPI文档访问失败: {response.status_code}")
    except Exception as e:
        print(f"❌ OpenAPI文档访问异常: {e}")
    
    # 检查OpenAPI JSON
    try:
        response = requests.get("http://localhost:8001/openapi.json", timeout=5)
        if response.status_code == 200:
            print("✅ OpenAPI JSON可访问")
            openapi_data = response.json()
            
            # 查找WebSocket路径
            paths = openapi_data.get("paths", {})
            websocket_paths = [path for path in paths if path.startswith("/ws/")]
            
            if websocket_paths:
                print(f"✅ 找到WebSocket路径: {websocket_paths}")
                for path in websocket_paths:
                    print(f"   - {path}: {list(paths[path].keys())}")
            else:
                print("❌ 未找到WebSocket路径")
                
        else:
            print(f"⚠️  OpenAPI JSON访问失败: {response.status_code}")
    except Exception as e:
        print(f"❌ OpenAPI JSON访问异常: {e}")

def check_websocket_endpoint_directly():
    """直接检查WebSocket端点"""
    print("\n🔍 直接检查WebSocket端点...")
    
    # 使用curl测试WebSocket端点
    import subprocess
    import sys
    
    try:
        # 获取token
        login_data = {
            "username": "hem",
            "password": "123456"
        }
        
        response = requests.post("http://localhost:8001/api/v1/auth/login", data=login_data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"✅ Token获取成功")
            
            # 使用curl测试WebSocket连接
            curl_cmd = [
                "curl", "-I", "-H", "Connection: Upgrade", 
                "-H", "Upgrade: websocket", 
                "-H", "Sec-WebSocket-Version: 13",
                "-H", f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
                f"http://localhost:8001/ws/progress/{token}"
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=10)
            print(f"curl返回码: {result.returncode}")
            print(f"curl输出: {result.stdout}")
            if result.stderr:
                print(f"curl错误: {result.stderr}")
                
        else:
            print(f"❌ Token获取失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def main():
    """主函数"""
    print("🚀 开始检查FastAPI路由配置")
    print("=" * 60)
    
    check_routes()
    check_websocket_endpoint_directly()

if __name__ == "__main__":
    main()