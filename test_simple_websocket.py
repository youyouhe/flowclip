#!/usr/bin/env python3
"""
简单的WebSocket状态查询测试
"""
import asyncio
import websockets
import json

async def test_simple_websocket():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzU0MzEzNzQwfQ.5aDZ-cy3QZlidkIHg3Ko8NlckqbSNvfRVEZpw9KfpdM"
    uri = f"ws://192.168.8.107:8001/api/v1/ws/progress/{token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功")
            
            # 发送状态更新请求
            print("🔄 发送状态更新请求...")
            request = {
                "type": "request_status_update"
            }
            await websocket.send(json.dumps(request))
            
            # 等待响应
            print("⏳ 等待响应...")
            for i in range(3):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    print(f"📨 收到消息: {json.dumps(data, indent=2, ensure_ascii=False)}")
                except asyncio.TimeoutError:
                    print(f"⏰ 第{i+1}次等待超时")
                except Exception as e:
                    print(f"❌ 接收消息错误: {e}")
            
            print("✅ 测试完成")
            
    except Exception as e:
        print(f"❌ WebSocket连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple_websocket())