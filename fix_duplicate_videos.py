#!/usr/bin/env python3
"""
Script to fix duplicate video entries in the database and clean up stuck downloads
"""

import pymysql
import sys
import asyncio
import aiohttp
import json
from pathlib import Path
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_duplicate_videos():
    """Fix duplicate video entries"""
    
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    
    try:
        conn = pymysql.connect(**mysql_config)
        cursor = conn.cursor()
    
        # Step 1: Find duplicate videos
        print("🔍 Finding duplicate videos...")
        cursor.execute('''
            SELECT url, project_id, COUNT(*) as count
            FROM videos
            GROUP BY url, project_id
            HAVING COUNT(*) > 1
        ''')
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("✅ No duplicate videos found")
            return
        
        print(f"📊 Found {len(duplicates)} duplicate video groups")
        
        # Step 2: For each duplicate group, keep only the most recent
        for duplicate in duplicates:
            url = duplicate['url']
            project_id = duplicate['project_id']
            count = duplicate['count']
            
            print(f"\n📝 Processing: {url} in project {project_id} ({count} duplicates)")
            
            # Get the IDs of duplicates (excluding the most recent)
            cursor.execute('''
                SELECT id FROM videos 
                WHERE url = %s AND project_id = %s
                ORDER BY created_at DESC
            ''', (url, project_id))
            
            video_ids = cursor.fetchall()
            if len(video_ids) > 1:
                # Keep the most recent, delete others
                keep_id = video_ids[0]['id']
                delete_ids = [vid['id'] for vid in video_ids[1:]]
                
                print(f"   ✅ Keeping video ID: {keep_id}")
                print(f"   🗑️  Deleting: {delete_ids}")
                
                # Delete related records first (if any)
                # Note: Foreign key constraints with CASCADE DELETE will handle related records
                
                # Delete the duplicate videos
                placeholders = ','.join(['%s'] * len(delete_ids))
                cursor.execute(f'DELETE FROM videos WHERE id IN ({placeholders})', delete_ids)
                
                print(f"   ✅ Deleted {cursor.rowcount} duplicate videos")
        
        # Step 3: Add unique constraint to prevent future duplicates
        print("\n🔒 Adding unique constraint...")
        try:
            cursor.execute('''
                ALTER TABLE videos 
                ADD UNIQUE INDEX idx_video_url_project (url, project_id)
            ''')
            print("✅ Unique constraint added")
        except pymysql.MySQLError as e:
            # Check if constraint already exists
            if '1061' in str(e):  # Duplicate key error
                print("⚠️  Unique constraint already exists")
            else:
                print(f"⚠️  Could not add unique constraint: {e}")
        
        conn.commit()
        print("\n🎉 Duplicate video fix completed!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error fixing duplicates: {e}")
    finally:
        conn.close()

def cleanup_stuck_videos():
    """Clean up stuck video downloads and corresponding files"""
    
    db_path = Path('backend/youtube_slicer.db')
    
    if not db_path.exists():
        print("❌ Database not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("🔍 Analyzing stuck videos...")
        
        # Step 1: Find videos with mismatched status based on processing tasks
        cursor.execute('''
            SELECT v.id, v.url, v.status, v.download_progress, v.created_at, 
                   p.status as task_status, p.progress as task_progress, p.output_data,
                   v.file_path, v.filename
            FROM videos v
            LEFT JOIN processing_tasks p ON v.id = p.video_id AND p.task_type = 'download'
            WHERE (v.status IN ('downloading', 'processing') AND v.created_at < datetime('now', '-30 minutes'))
               OR (p.status = 'success' AND v.status != 'completed')
               OR (p.status = 'failed' AND v.status != 'failed')
            ORDER BY v.created_at DESC
        ''')
        
        stuck_videos = cursor.fetchall()
        
        if not stuck_videos:
            print("✅ No stuck videos found")
            return
        
        print(f"📊 Found {len(stuck_videos)} videos with status issues")
        
        videos_to_update = []
        videos_to_delete = []
        minio_files_to_cleanup = []
        
        for video in stuck_videos:
            video_id, url, status, progress, created_at, task_status, task_progress, output_data, file_path, filename = video
            
            print(f"\n🚨 Video {video_id}: {filename or url[:50]}...")
            print(f"   Current: status={status}, progress={progress}%")
            if task_status:
                print(f"   Task: status={task_status}, progress={task_progress}%")
            
            # Handle different scenarios
            if task_status == 'success' and status != 'completed':
                # Task succeeded but video not updated
                if output_data:
                    try:
                        import json
                        task_data = json.loads(output_data)
                        videos_to_update.append({
                            'id': video_id,
                            'status': 'completed',
                            'progress': 100.0,
                            'file_path': task_data.get('minio_path'),
                            'filename': task_data.get('filename'),
                            'file_size': task_data.get('filesize'),
                            'thumbnail_url': task_data.get('thumbnail_url'),
                            'type': 'complete_from_task'
                        })
                        print(f"   ✅ Will complete from task data")
                    except:
                        videos_to_update.append({
                            'id': video_id,
                            'status': 'completed',
                            'progress': 100.0,
                            'type': 'complete_manual'
                        })
                        print(f"   ⚠️ Will complete manually")
                        
            elif task_status == 'failed' and status not in ['failed', 'error']:
                # Task failed but video not updated
                videos_to_update.append({
                    'id': video_id,
                    'status': 'failed',
                    'progress': 0.0,
                    'type': 'fail_from_task'
                })
                print(f"   ❌ Will mark as failed")
                
            elif status in ['downloading', 'processing'] and created_at < datetime.now() - timedelta(hours=2):
                # Stuck for more than 2 hours
                if file_path and file_path.strip():
                    videos_to_delete.append(video_id)
                    minio_files_to_cleanup.append(file_path)
                    print(f"   🗑️ Will delete stuck video and file")
                else:
                    videos_to_delete.append(video_id)
                    print(f"   🗑️ Will delete stuck video (no file)")
        
        # Process updates
        if videos_to_update:
            print(f"\n📈 Updating {len(videos_to_update)} videos...")
            for video in videos_to_update:
                if video['type'] == 'complete_from_task':
                    cursor.execute('''
                        UPDATE videos 
                        SET status = %s, download_progress = %s, file_path = %s, 
                            filename = %s, file_size = %s, thumbnail_url = %s, 
                            processing_stage = 'download', processing_message = '视频下载完成',
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (
                        video['status'], video['progress'], video['file_path'],
                        video['filename'], video['file_size'], video['thumbnail_url'],
                        video['id']
                    ))
                else:
                    cursor.execute('''
                        UPDATE videos 
                        SET status = %s, download_progress = %s, 
                            processing_stage = 'error', processing_message = 'Processing corrected',
                            updated_at = NOW()
                        WHERE id = %s
                    ''', (video['status'], video['progress'], video['id']))
                
                print(f"   ✅ Updated video {video['id']} to {video['status']}")
        
        # Process deletions
        if videos_to_delete:
            print(f"\n🗑️ Cleaning up {len(videos_to_delete)} stuck videos...")
            
            # Delete processing tasks first
            placeholders = ','.join(['%s'] * len(videos_to_delete))
            cursor.execute(f'''
                DELETE FROM processing_tasks 
                WHERE video_id IN ({placeholders})
            ''', videos_to_delete)
            print(f"   ✅ Deleted {cursor.rowcount} stuck processing tasks")
            
            # Delete videos
            placeholders = ','.join(['%s'] * len(videos_to_delete))
            cursor.execute(f'''
                DELETE FROM videos 
                WHERE id IN ({placeholders})
            ''', videos_to_delete)
            print(f"   ✅ Deleted {cursor.rowcount} stuck videos")
            
            # Clean up files
            if minio_files_to_cleanup:
                print(f"   🧹 Cleaning up {len(minio_files_to_cleanup)} MinIO files...")
                asyncio.run(cleanup_minio_files(minio_files_to_cleanup))
        
        conn.commit()
        
        if not videos_to_update and not videos_to_delete:
            print("✅ All videos are properly synchronized")
        else:
            print(f"\n🎉 Cleaned up {len(videos_to_update) + len(videos_to_delete)} videos")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during stuck video cleanup: {e}")
    finally:
        conn.close()

async def cleanup_minio_files(file_paths):
    """Clean up files from MinIO storage"""
    try:
        import sys
        sys.path.append('backend')
        
        from app.services.minio_client import minio_service
        from app.core.config import settings
        
        deleted_count = 0
        for file_path in file_paths:
            if file_path:
                try:
                    # Extract object name from file path
                    if file_path.startswith(f"{settings.minio_bucket_name}/"):
                        object_name = file_path[len(settings.minio_bucket_name)+1:]
                    else:
                        object_name = file_path
                    
                    # Check if file exists
                    try:
                        minio_service.client.stat_object(settings.minio_bucket_name, object_name)
                        # File exists, delete it
                        minio_service.client.remove_object(settings.minio_bucket_name, object_name)
                        print(f"   ✅ Deleted: {object_name}")
                        deleted_count += 1
                    except:
                        print(f"   ⚠️  File not found: {object_name}")
                        
                except Exception as e:
                    print(f"   ❌ Error deleting {file_path}: {e}")
        
        print(f"🧹 Cleaned up {deleted_count} MinIO files")
        
    except ImportError as e:
        print(f"⚠️  MinIO cleanup skipped (not available): {e}")
    except Exception as e:
        print(f"❌ MinIO cleanup failed: {e}")

def reset_processing_status():
    """Reset stuck processing status to failed"""
    
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    
    try:
        conn = pymysql.connect(**mysql_config)
        cursor = conn.cursor()
    
        print("🔧 Resetting stuck processing status...")
        
        # Reset videos stuck in downloading/processing for > 2 hours
        cursor.execute('''
            UPDATE videos 
            SET status = 'failed', 
                processing_message = 'Aborted due to system restart',
                processing_stage = 'error',
                updated_at = NOW()
            WHERE status IN ('downloading', 'processing') 
            AND created_at < DATE_SUB(NOW(), INTERVAL 2 HOUR)
        ''')
        
        stuck_video_count = cursor.rowcount
        if stuck_video_count > 0:
            print(f"   ✅ Reset {stuck_video_count} stuck videos to failed status")
        else:
            print("   ✅ No stuck videos to reset")
        
        # Reset stuck processing tasks
        cursor.execute('''
            UPDATE processing_tasks 
            SET status = 'failed', 
                message = 'Aborted due to system restart',
                updated_at = NOW()
            WHERE status IN ('running', 'pending') 
            AND created_at < DATE_SUB(NOW(), INTERVAL 2 HOUR)
        ''')
        
        stuck_task_count = cursor.rowcount
        if stuck_task_count > 0:
            print(f"   ✅ Reset {stuck_task_count} stuck processing tasks to failed status")
        else:
            print("   ✅ No stuck processing tasks to reset")
        
        # Report summary
        total_reset = stuck_video_count + stuck_task_count
        if total_reset > 0:
            print(f"\n📊 Summary: Reset {total_reset} items to failed status")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error resetting processing status: {e}")
    finally:
        conn.close()

def main():
    """Main function to run all cleanup tasks"""
    print("🧹 YouTube Slicer Cleanup Tool")
    print("=" * 40)
    
    while True:
        print("\nAvailable cleanup tasks:")
        print("1. Fix duplicate videos")
        print("2. Clean up stuck downloads")
        print("3. Reset stuck processing status")
        print("4. Run all cleanup tasks")
        print("5. Exit")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == '1':
            fix_duplicate_videos()
        elif choice == '2':
            cleanup_stuck_videos()
        elif choice == '3':
            reset_processing_status()
        elif choice == '4':
            fix_duplicate_videos()
            cleanup_stuck_videos()
            reset_processing_status()
            print("\n🎉 All cleanup tasks completed!")
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid option. Please select 1-5.")

if __name__ == "__main__":
    main()