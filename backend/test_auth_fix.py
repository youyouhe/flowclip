#!/usr/bin/env python3
"""
测试认证API修复 - 验证JSON和表单格式都支持
"""
import asyncio
import aiohttp
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8001"

async def test_json_login():
    """测试JSON格式的登录请求"""
    print("🔍 测试JSON格式登录...")

    async with aiohttp.ClientSession() as session:
        data = {
            "username": "test_user",
            "password": "test_password"
        }

        try:
            async with session.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                print(f"✅ JSON登录 - 状态码: {response.status}")
                if response.status == 200:
                    print(f"   获取到token: {result.get('access_token', 'N/A')[:20]}...")
                else:
                    print(f"   响应: {result}")
                return response.status == 200
        except Exception as e:
            print(f"❌ JSON登录失败: {e}")
            return False

async def test_form_login():
    """测试表单格式的登录请求"""
    print("\n🔍 测试表单格式登录...")

    async with aiohttp.ClientSession() as session:
        data = {
            "username": "test_user",
            "password": "test_password"
        }

        try:
            async with session.post(
                f"{BASE_URL}/api/v1/auth/login",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                result = await response.json()
                print(f"✅ 表单登录 - 状态码: {response.status}")
                if response.status == 200:
                    print(f"   获取到token: {result.get('access_token', 'N/A')[:20]}...")
                else:
                    print(f"   响应: {result}")
                return response.status == 200
        except Exception as e:
            print(f"❌ 表单登录失败: {e}")
            return False

async def test_frontend_like_request():
    """测试模拟前端请求格式的登录"""
    print("\n🔍 测试模拟前端请求格式...")

    async with aiohttp.ClientSession() as session:
        data = {
            "username": "test_user",
            "password": "test_password"
        }

        try:
            # 完全模拟前端的请求方式
            async with session.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=data,  # 这和前端axios.post的方式一致
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            ) as response:
                result = await response.json()
                print(f"✅ 前端格式登录 - 状态码: {response.status}")
                if response.status == 200:
                    print(f"   获取到token: {result.get('access_token', 'N/A')[:20]}...")
                    print(f"   token类型: {result.get('token_type', 'N/A')}")
                else:
                    print(f"   响应: {result}")
                return response.status == 200
        except Exception as e:
            print(f"❌ 前端格式登录失败: {e}")
            return False

async def test_invalid_request():
    """测试无效请求格式"""
    print("\n🔍 测试无效请求格式...")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/v1/auth/login",
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                print(f"✅ 无效请求 - 状态码: {response.status}")
                print(f"   响应: {result}")
                return response.status == 400
        except Exception as e:
            print(f"❌ 无效请求测试失败: {e}")
            return False

async def main():
    """主测试函数"""
    print("🚀 开始测试认证API修复...")
    print("=" * 50)

    # 检查后端是否运行
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status != 200:
                    print("❌ 后端服务未运行或健康检查失败")
                    print("请确保后端服务在 http://localhost:8001 运行")
                    return
    except Exception:
        print("❌ 无法连接到后端服务")
        print("请确保后端服务在 http://localhost:8001 运行")
        return

    print("✅ 后端服务正常运行")
    print()

    # 运行测试
    results = []
    results.append(await test_json_login())
    results.append(await test_form_login())
    results.append(await test_frontend_like_request())
    results.append(await test_invalid_request())

    print("\n" + "=" * 50)
    print("📊 测试结果总结:")
    passed = sum(results)
    total = len(results)
    print(f"   通过: {passed}/{total}")

    if passed == total:
        print("🎉 所有测试通过！认证API修复成功")
    else:
        print("⚠️  部分测试失败，需要进一步检查")

if __name__ == "__main__":
    asyncio.run(main())