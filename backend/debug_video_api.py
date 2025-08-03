#!/usr/bin/env python3

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.models.project import Project
from app.services.youtube_downloader import downloader

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_video_download():
    """Debug the video download process step by step"""
    
    print("=== Debugging Video Download API ===")
    
    # Test 1: Database connection
    print("\n1. Testing database connection...")
    try:
        async for db in get_db():
            print("✓ Database connection successful")
            
            # Test 2: Check if project exists
            print("\n2. Checking project with ID 1...")
            from sqlalchemy import select
            stmt = select(Project).where(Project.id == 1)
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            
            if project:
                print(f"✓ Project found: {project.name} (User ID: {project.user_id})")
            else:
                print("✗ Project 1 not found")
                return
                
            # Test 3: Test YouTube downloader
            print("\n3. Testing YouTube downloader...")
            try:
                url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                video_info = await downloader.get_video_info(url)
                print(f"✓ Video info retrieved: {video_info['title']}")
                print(f"  Duration: {video_info['duration']} seconds")
                
                # Test 4: Create video record
                print("\n4. Creating video record...")
                import uuid
                new_video = Video(
                    title=video_info['title'],
                    description=video_info['description'][:500] if video_info['description'] else None,
                    url=url,
                    project_id=1,
                    filename=f"{video_info['title'][:50]}.mp4",
                    duration=video_info['duration'],
                    file_size=0,
                    thumbnail_url=video_info['thumbnail'],
                    status="downloading",
                    download_progress=0.0
                )
                
                db.add(new_video)
                await db.commit()
                await db.refresh(new_video)
                print(f"✓ Video record created with ID: {new_video.id}")
                
                # Test 5: Test actual download
                print("\n5. Testing actual download...")
                try:
                    download_result = await downloader.download_video(
                        url=url,
                        project_id=1,
                        user_id=1
                    )
                    print(f"✓ Download successful: {download_result}")
                    
                    # Update video record
                    new_video.status = "completed"
                    new_video.download_progress = 100.0
                    new_video.file_path = download_result['filepath']
                    new_video.filename = download_result['filename']
                    new_video.file_size = download_result['filesize']
                    
                    await db.commit()
                    print("✓ Video record updated with download info")
                    
                except Exception as e:
                    print(f"✗ Download failed: {e}")
                    # Update status to failed
                    new_video.status = "failed"
                    new_video.download_progress = 0.0
                    await db.commit()
                    
            except Exception as e:
                print(f"✗ YouTube downloader error: {e}")
                
    except Exception as e:
        print(f"✗ Database error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_video_download())