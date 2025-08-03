#!/usr/bin/env python3
"""
Test script to verify video update fixes
"""

import asyncio
import sqlite3
from pathlib import Path
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.video import Video

async def test_video_update():
    """Test video update functionality"""
    
    print("🔍 Testing video update fixes...")
    
    # Test database connection
    db_path = Path('backend/youtube_slicer.db')
    if not db_path.exists():
        print("❌ Database not found")
        return
    
    # Test SQLAlchemy update
    try:
        async with AsyncSessionLocal() as db:
            # Find a video to test with
            stmt = select(Video).limit(1)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if video:
                print(f"✅ Found video ID: {video.id}")
                
                # Test update with SQLAlchemy update statement
                update_stmt = (
                    update(Video)
                    .where(Video.id == video.id)
                    .values(
                        download_progress=50.0,
                        processing_message="Test update working",
                        status="testing"
                    )
                )
                await db.execute(update_stmt)
                await db.commit()
                
                # Verify update
                stmt = select(Video).where(Video.id == video.id)
                result = await db.execute(stmt)
                updated_video = result.scalar_one_or_none()
                
                if updated_video and updated_video.download_progress == 50.0:
                    print("✅ Video update working correctly")
                    
                    # Reset back
                    update_stmt = (
                        update(Video)
                        .where(Video.id == video.id)
                        .values(status="pending")
                    )
                    await db.execute(update_stmt)
                    await db.commit()
                    print("✅ Reset test video")
                else:
                    print("❌ Update verification failed")
            else:
                print("⚠️ No videos found to test")
                
    except Exception as e:
        print(f"❌ Database update test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_video_update())