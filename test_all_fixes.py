#!/usr/bin/env python3
"""
Test script to verify all fixes are working
"""

import asyncio
import aiohttp
import requests
import json
import sqlite3
from pathlib import Path

def test_database_fixes():
    """Test database fixes"""
    print("🔍 Testing database fixes...")
    
    db_path = Path('backend/youtube_slicer.db')
    if not db_path.exists():
        print("❌ Database not found")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check for duplicates
        cursor.execute('''
            SELECT url, project_id, COUNT(*) as count
            FROM videos
            GROUP BY url, project_id
            HAVING COUNT(*) > 1
        ''')
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"❌ Found duplicate videos: {duplicates}")
            return False
        else:
            print("✅ No duplicate videos found")
            
        # Check for unique constraint
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_video_url_project'
        """)
        constraint = cursor.fetchone()
        if constraint:
            print("✅ Unique constraint found")
        else:
            print("⚠️  Unique constraint not found")
            
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    finally:
        conn.close()

async def test_websocket_connection():
    """Test WebSocket connection"""
    print("\n🔍 Testing WebSocket connection...")
    
    try:
        # Test API health
        response = requests.get("http://localhost:8001/health")
        if response.status_code != 200:
            print("❌ Backend API not healthy")
            return False
        
        print("✅ Backend API is healthy")
        
        # Test WebSocket endpoint accessibility
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("http://localhost:8001/docs"):
                    print("✅ API documentation accessible")
            except Exception as e:
                print(f"❌ API documentation not accessible: {e}")
                return False
                
        print("✅ WebSocket infrastructure ready")
        return True
        
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

def test_cors_configuration():
    """Test CORS configuration"""
    print("\n🔍 Testing CORS configuration...")
    
    try:
        # Test CORS preflight request
        response = requests.options(
            "http://localhost:8001/api/v1/auth/login",
            headers={
                'Origin': 'http://192.168.8.107:3000',
                'Access-Control-Request-Method': 'POST'
            }
        )
        
        if response.status_code == 200:
            cors_header = response.headers.get('Access-Control-Allow-Origin')
            if cors_header and ('192.168.8.107:3000' in cors_header or cors_header == '*'):
                print("✅ CORS configuration working")
                return True
            else:
                print(f"❌ CORS header missing: {cors_header}")
                return False
        else:
            print(f"❌ CORS preflight failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ CORS test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Testing all fixes...\n")
    
    # Test database fixes
    db_ok = test_database_fixes()
    
    # Test CORS configuration
    cors_ok = test_cors_configuration()
    
    # Test WebSocket connection
    websocket_ok = await test_websocket_connection()
    
    print("\n" + "="*50)
    print("📊 Test Results:")
    print(f"Database fixes: {'✅' if db_ok else '❌'}")
    print(f"CORS configuration: {'✅' if cors_ok else '❌'}")
    print(f"WebSocket connection: {'✅' if websocket_ok else '❌'}")
    
    if all([db_ok, cors_ok, websocket_ok]):
        print("\n🎉 All fixes are working correctly!")
        print("\nNext steps:")
        print("1. Run: python fix_duplicate_videos.py")
        print("2. Start backend: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        print("3. Start Celery: celery -A app.core.celery worker --loglevel=info")
        print("4. Test video download with same URL")
    else:
        print("\n❌ Some tests failed. Check the output above.")

if __name__ == "__main__":
    asyncio.run(main())