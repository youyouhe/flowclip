#!/usr/bin/env python3
"""
Test WebSocket connection with minimal dependencies
"""
import asyncio
import websockets
import json

async def test_websocket():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2IiwiZXhwIjoxNzU0MTk3MTU5fQ.HYyMzc0DkL8R8Vt2SSN2PGp-OjD76_Ghx_mQnucEDOM"
    uri = f"ws://localhost:8001/api/v1/ws/progress/{token}"
    
    print(f"Testing WebSocket connection to: {uri[:60]}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connected successfully!")
            
            # Send a ping message
            await websocket.send(json.dumps({"type": "ping"}))
            print("✅ Ping message sent")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✅ Received response: {response}")
            
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_websocket())