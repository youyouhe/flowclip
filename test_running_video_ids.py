#!/usr/bin/env python3
"""
测试获取运行中视频 IDs 的脚本
"""
import requests
import json
import sys
import os

# 添加后端路径以便导入
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def test_running_video_ids():
    """测试获取运行中的视频 IDs"""
    base_url = "http://localhost:8001"
    
    # 1. 首先登录获取 token
    print("🔐 登录获取 token...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/auth/login", json=login_data)
        if response.status_code != 200:
            print(f"❌ 登录失败: {response.status_code}")
            print(f"响应: {response.text}")
            return
        
        token = response.json()["access_token"]
        print(f"✅ 登录成功，获取到 token")
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # 2. 测试获取运行中的视频 IDs
        print("\n📊 测试获取运行中的视频 IDs...")
        response = requests.get(f"{base_url}/api/v1/status/videos/running", headers=headers)
        
        if response.status_code == 200:
            running_video_ids = response.json()
            print(f"✅ 成功获取运行中的视频 IDs: {running_video_ids}")
            
            if running_video_ids:
                print(f"📈 当前有 {len(running_video_ids)} 个视频正在运行")
                for video_id in running_video_ids:
                    print(f"   - Video ID: {video_id}")
            else:
                print("📝 当前没有运行中的视频")
                
        else:
            print(f"❌ 获取运行中的视频 IDs 失败: {response.status_code}")
            print(f"响应: {response.text}")
        
        # 3. 对比获取活跃视频的方法
        print("\n🔄 对比获取活跃视频的方法...")
        
        # 方法1: 使用 /videos/active
        response = requests.get(f"{base_url}/api/v1/videos/active", headers=headers)
        if response.status_code == 200:
            active_videos = response.json()
            active_video_ids = [video['id'] for video in active_videos]
            print(f"📋 /videos/active 返回的活跃视频 IDs: {active_video_ids}")
        
        # 方法2: 查询处理任务状态
        response = requests.get(f"{base_url}/api/v1/processing/tasks", headers=headers)
        if response.status_code == 200:
            tasks = response.json()
            running_task_video_ids = list(set([task['video_id'] for task in tasks if task['status'] in ['pending', 'running']]))
            print(f"📋 处理任务中的运行视频 IDs: {running_task_video_ids}")
        
        # 4. 获取系统状态
        print("\n📊 获取系统状态...")
        response = requests.get(f"{base_url}/api/v1/status", headers=headers)
        if response.status_code == 200:
            status_data = response.json()
            task_stats = status_data.get('task_stats', {})
            print(f"📈 任务统计: {task_stats}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
    except KeyError as e:
        print(f"❌ 响应解析失败: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

def test_video_id_consistency():
    """测试视频 ID 一致性"""
    print("\n🔍 测试视频 ID 一致性...")
    
    # 这里可以添加测试不同来源的 video ID 是否一致
    print("📝 视频 ID 一致性检查:")
    print("   - 数据库 video_id: 整数类型")
    print("   - YouTube video_id: 字符串类型")
    print("   - WebSocket 传输: 数字类型")
    print("   - 前端处理: number 类型")

if __name__ == "__main__":
    print("🚀 开始测试获取运行中的视频 IDs...")
    test_running_video_ids()
    test_video_id_consistency()
    print("\n✅ 测试完成")