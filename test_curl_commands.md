# YouTube → MinIO Integration Test Commands

## 1. Test YouTube Video Info First

```bash
curl -X POST http://localhost:8001/api/v1/videos/download \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "url": "https://www.youtube.com/watch?v=BaqfDhZVnu4",
    "project_id": 1
  }'
```

## 2. Get Video Info (Debug)

```bash
python -c "
import asyncio
from app.services.youtube_downloader_minio import downloader_minio

async def test_video_info():
    try:
        video_info = await downloader_minio.get_video_info('https://www.youtube.com/watch?v=BaqfDhZVnu4')
        print('✅ Video Info:')
        print(f'  Title: {video_info[\"title\"]}')
        print(f'  Duration: {video_info[\"duration\"]}s')
        print(f'  File Size: {video_info.get(\"filesize\", \"Unknown\")}')
        print(f'  ID: {video_info[\"video_id\"]}')
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test_video_info())
"
```

## 3. Direct Test with Cookies

```bash
python -c "
import asyncio
from app.services.youtube_downloader_minio import YouTubeDownloaderMinio

async def test_download():
    downloader = YouTubeDownloaderMinio(cookies_file='/home/cat/github/slice-youtube/youtube_cookies.txt')
    
    try:
        print('🎯 Testing YouTube → MinIO download...')
        
        # Get video info first
        video_info = await downloader.get_video_info('https://www.youtube.com/watch?v=BaqfDhZVnu4')
        print(f'📺 Video: {video_info[\"title\"]}')
        
        # Download and upload to MinIO
        result = await downloader.download_and_upload_video(
            url='https://www.youtube.com/watch?v=BaqfDhZVnu4',
            project_id=1,
            user_id=1,
            format_id='best'  # or 'worst' for faster testing
        )
        
        if result['success']:
            print('✅ Download and upload completed!')
            print(f'  📁 File: {result[\"filename\"]}')
            print(f'  🗂️  MinIO Path: {result[\"minio_path\"]}')
            print(f'  📊 Size: {result[\"filesize\"]} bytes')
            print(f'  🎯 Video ID: {result[\"video_id\"]}')
            
            # Verify file exists in MinIO
            from app.services.minio_client import minio_service
            object_name = result['minio_path'].replace('youtube-videos/', '')
            exists = await minio_service.file_exists(object_name)
            print(f'  ✅ Verified in MinIO: {exists}')
        else:
            print('❌ Download failed')
            
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test_download())
"
```

## 4. Manual MinIO Upload Test

```bash
python -c "
import asyncio
from app.services.minio_client import minio_service

async def test_upload():
    # Create test file
    test_content = b'Test upload to MinIO'
    object_name = 'test/test-upload.txt'
    
    # Upload to MinIO
    result = await minio_service.upload_file_content(test_content, object_name, 'text/plain')
    print(f'✅ Uploaded: {result}')
    
    # Verify file exists
    exists = await minio_service.file_exists(object_name)
    print(f'✅ File exists: {exists}')
    
    # Get download URL
    url = await minio_service.get_file_url(object_name, 300)
    print(f'✅ Download URL: {url}')

asyncio.run(test_upload())
"
```

## 5. Check MinIO Console

Visit: http://localhost:9001
- Username: minioadmin
- Password: minioadmin
- Navigate to: youtube-videos bucket → users/1/projects/1/videos/

## 6. Test File Access via API

```bash
# Get download URL for a file
curl -X GET "http://localhost:8000/api/v1/videos/1/download-url?expiry=3600" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 7. Test Database Integration

```bash
python -c "
import sqlite3
conn = sqlite3.connect('youtube_slicer.db')
cursor = conn.cursor()

# Check latest videos
cursor.execute('SELECT id, title, file_path, status, file_size FROM videos ORDER BY id DESC LIMIT 5')
videos = cursor.fetchall()
print('📊 Latest videos:')
for video in videos:
    print(f'  ID: {video[0]}, Title: {video[1]}, Status: {video[3]}, Size: {video[4]} bytes')
    print(f'  MinIO Path: {video[2]}')

conn.close()
"
```

## 8. Cleanup Test Files

```bash
python -c "
import asyncio
from app.services.minio_client import minio_service

async def cleanup():
    # Clean up test files
    await minio_service.delete_file('test/test-upload.txt')
    await minio_service.delete_file('test/test-complete.txt')
    await minio_service.delete_file('demo/test-file.txt')
    print('✅ Test files cleaned up')

asyncio.run(cleanup())
"
```

## 🔧 Environment Setup Checklist

Before running commands:

1. **Services Running**: ✅ MinIO (9000/9001), Redis (6379)
2. **Cookies File**: ✅ `/home/cat/github/slice-youtube/youtube_cookies.txt`
3. **Backend**: Start with: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
4. **Database**: SQLite file at `youtube_slicer.db`

## 🎯 Quick Test Sequence

```bash
# 1. Test MinIO connection
python -c "from app.services.minio_client import minio_service; import asyncio; asyncio.run(minio_service.ensure_bucket_exists())"

# 2. Test YouTube info (with cookies)
python -c "
import asyncio
from app.services.youtube_downloader_minio import YouTubeDownloaderMinio
downloader = YouTubeDownloaderMinio(cookies_file='/home/cat/github/slice-youtube/youtube_cookies.txt')
asyncio.run(downloader.get_video_info('https://www.youtube.com/watch?v=BaqfDhZVnu4'))
"

# 3. Test full download
python -c "
import asyncio
from app.services.youtube_downloader_minio import YouTubeDownloaderMinio
downloader = YouTubeDownloaderMinio(cookies_file='/home/cat/github/slice-youtube/youtube_cookies.txt')
asyncio.run(downloader.download_and_upload_video('https://www.youtube.com/watch?v=BaqfDhZVnu4', 1, 1))
"
```