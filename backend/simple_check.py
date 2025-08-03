#!/usr/bin/env python3
"""
简单的视频列表检查
"""
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
    
    # 获取视频列表
    headers = {"Authorization": f"Bearer {token}"}
    videos_response = requests.get("http://localhost:8001/api/v1/videos", headers=headers)
    
    if videos_response.status_code == 200:
        videos = videos_response.json()
        print(f"视频数量: {len(videos)}")
        
        for video in videos:
            print(f"ID: {video['id']}, 标题: {video['title']}, 状态: {video['status']}")
    else:
        print(f"获取视频列表失败: {videos_response.status_code}")
else:
    print(f"登录失败: {response.status_code}")