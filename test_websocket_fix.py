#!/usr/bin/env python3
"""
Test script to verify WebSocket progress updates are working
"""

import asyncio
import aiohttp
import json
import requests

async def test_websocket_connection():
    """Test WebSocket connection for progress updates"""
    
    # First, test WebSocket endpoint
    print("🔍 Testing WebSocket endpoint...")
    
    # Test 1: Basic WebSocket connection
    try:
        async with aiohttp.ClientSession() as session:
            # Note: This is a simplified test, actual token would be needed
            async with session.ws_connect('http://localhost:8001/ws/progress/test_token') as ws:
                print("✅ WebSocket connection established")
                
                # Send ping
                await ws.send_str(json.dumps({"type": "ping"}))
                
                # Wait for response
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print(f"📨 Received: {data}")
                        if data.get("type") == "pong":
                            print("✅ WebSocket heartbeat working")
                            break
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ WebSocket error: {ws.exception()}")
                        break
                        
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
    
    # Test 2: Check if progress service is running
    print("\n🔍 Testing progress service...")
    try:
        import sys
        sys.path.append('backend')
        
        from app.services.progress_service import progress_service
        
        # Check if service is initialized
        if progress_service._running:
            print("✅ Progress service is running")
        else:
            print("⚠️  Progress service is not running")
            
    except Exception as e:
        print(f"❌ Progress service test failed: {e}")
    
    # Test 3: Check API endpoints
    print("\n🔍 Testing API endpoints...")
    try:
        response = requests.get("http://localhost:8001/health")
        if response.status_code == 200:
            print("✅ Backend API is healthy")
        else:
            print(f"❌ Backend API health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Backend API test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())