#!/usr/bin/env python3
"""
测试WebSocket状态查询机制
"""
import asyncio
import websockets
import json
import time

async def test_websocket_status_query():
    """测试WebSocket状态查询功能"""
    # 需要替换为有效的token
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzU0MzEzNzQwfQ.5aDZ-cy3QZlidkIHg3Ko8NlckqbSNvfRVEZpw9KfpdM"
    
    if token == "YOUR_TOKEN_HERE":
        print("请先获取有效的JWT token并替换脚本中的token")
        return
    
    uri = f"ws://192.168.8.107:8001/api/v1/ws/progress/{token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功")
            
            # 监听消息
            async def listen_messages():
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        print(f"📨 收到消息: {data}")
                        
                        if data.get('type') == 'progress_update':
                            print(f"  视频ID: {data.get('video_id')}")
                            print(f"  状态: {data.get('video_status')}")
                            print(f"  下载进度: {data.get('download_progress')}%")
                            print(f"  处理进度: {data.get('processing_progress')}%")
                            print(f"  阶段: {data.get('processing_stage')}")
                            print(f"  消息: {data.get('processing_message')}")
                            print("-" * 50)
                        
                    except websockets.exceptions.ConnectionClosed:
                        print("WebSocket连接已关闭")
                        break
                    except Exception as e:
                        print(f"接收消息错误: {e}")
            
            # 启动消息监听任务
            listen_task = asyncio.create_task(listen_messages())
            
            # 等待连接稳定
            await asyncio.sleep(2)
            
            # 发送状态更新请求（模拟前端每3秒查询）
            for i in range(5):
                print(f"🔄 发送状态更新请求 {i+1}/5")
                request = {
                    "type": "request_status_update"
                }
                await websocket.send(json.dumps(request))
                await asyncio.sleep(3)  # 每3秒发送一次
                print(f"⏰ 等待3秒后发送下一个请求...")
            
            # 等待最后一条消息
            await asyncio.sleep(2)
            
            # 取消监听任务
            listen_task.cancel()
            
            print("✅ 测试完成")
            
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_status_query())