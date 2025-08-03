#!/usr/bin/env python3
"""
创建测试用户并获取token
"""
import asyncio
import sys
import os
import requests
import json

# 添加backend目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

API_BASE_URL = "http://192.168.8.107:8001"

def create_test_user():
    """创建测试用户"""
    print("=== 创建测试用户 ===")
    
    # 登录获取token (使用现有用户)
    login_data = {
        "username": "newuser",
        "password": "password123"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/v1/auth/login", data=login_data)
        print(f"登录响应: {response.status_code}")
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("access_token")
            print(f"✅ 登录成功，获取token: {token[:50]}...")
            
            # 保存token到文件
            with open("test_token.txt", "w") as f:
                f.write(token)
            print("✅ Token已保存到 test_token.txt")
            
            return token
        else:
            print(f"❌ 登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return None

def test_thumbnail_api(token):
    """测试缩略图API"""
    print("\n=== 测试缩略图API ===")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 获取视频列表
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/videos", headers=headers)
        print(f"视频列表响应: {response.status_code}")
        if response.status_code == 200:
            videos = response.json()
            print(f"✅ 获取到 {len(videos)} 个视频")
            
            if videos:
                # 测试第一个视频的缩略图
                video_id = videos[0]["id"]
                print(f"测试视频ID: {video_id}")
                
                # 获取缩略图URL
                thumbnail_response = requests.get(f"{API_BASE_URL}/api/v1/videos/{video_id}/thumbnail-download-url", headers=headers)
                print(f"缩略图URL响应: {thumbnail_response.status_code}")
                
                if thumbnail_response.status_code == 200:
                    thumbnail_data = thumbnail_response.json()
                    thumbnail_url = thumbnail_data.get("download_url")
                    print(f"✅ 缩略图URL: {thumbnail_url}")
                    
                    # 测试访问缩略图
                    if thumbnail_url:
                        img_response = requests.head(thumbnail_url)
                        print(f"缩略图访问响应: {img_response.status_code}")
                        if img_response.status_code == 200:
                            print("✅ 缩略图可以正常访问")
                        else:
                            print(f"❌ 缩略图访问失败: {img_response.status_code}")
                            print(f"响应头: {img_response.headers}")
                else:
                    print(f"❌ 获取缩略图URL失败: {thumbnail_response.text}")
            else:
                print("❌ 没有找到视频")
        else:
            print(f"❌ 获取视频列表失败: {response.text}")
    except Exception as e:
        print(f"❌ API请求失败: {e}")

if __name__ == "__main__":
    token = create_test_user()
    if token:
        test_thumbnail_api(token)