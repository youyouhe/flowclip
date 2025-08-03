# Backend API Testing Commands for YouTube → MinIO Integration

## 🎯 Backend API Testing Commands

### **1. Test Backend Health**
```bash
curl -X GET http://localhost:8001/health
```

### **2. Test YouTube Video Download via API**

**Step 1: Create a project (if needed)**
```bash
curl -X POST http://localhost:8001/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "name": "Test YouTube Project",
    "description": "Testing YouTube → MinIO integration"
  }'
```

**Step 2: Download YouTube video via API**
```bash
curl -X POST http://localhost:8001/api/v1/videos/download \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "url": "https://www.youtube.com/watch?v=BaqfDhZVnu4",
    "project_id": 1
  }'
```

### **3. Monitor Download Progress**

**Get video list:**
```bash
curl -X GET http://localhost:8001/api/v1/videos \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Get specific video:**
```bash
curl -X GET http://localhost:8001/api/v1/videos/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### **4. Test MinIO File Access**

**Get download URL:**
```bash
curl -X GET "http://localhost:8001/api/v1/videos/1/download-url?expiry=3600" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### **5. Test Database Integration**

**Check database records:**
```bash
python -c "
import sqlite3
conn = sqlite3.connect('youtube_slicer.db')
cursor = conn.cursor()

# Get videos with MinIO paths
cursor.execute('''
SELECT id, title, filename, file_path, status, file_size, created_at 
FROM videos 
WHERE url LIKE '%BaqfDhZVnu4%' 
ORDER BY created_at DESC
''')

videos = cursor.fetchall()
print('📊 YouTube videos in database:')
for video in videos:
    print(f'ID: {video[0]}')
    print(f'Title: {video[1]}')
    print(f'Filename: {video[2]}')
    print(f'MinIO Path: {video[3]}')
    print(f'Status: {video[4]}')
    print(f'Size: {video[5]} bytes')
    print(f'Created: {video[6]}')
    print('---')

conn.close()
"
```

### **6. Manual Backend Test (Direct Python)**

```bash
python -c "
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path('.').absolute()))

from app.services.youtube_downloader_minio import YouTubeDownloaderMinio
from app.services.minio_client import minio_service

async def test_backend_integration():
    print('🎯 Testing Backend Integration...')
    
    # Test MinIO connection
    bucket_ok = await minio_service.ensure_bucket_exists()
    print(f'✅ MinIO bucket: {bucket_ok}')
    
    # Test YouTube downloader with cookies
    downloader = YouTubeDownloaderMinio(cookies_file='/home/cat/github/slice-youtube/youtube_cookies.txt')
    
    try:
        # Get video info
        info = await downloader.get_video_info('https://www.youtube.com/watch?v=BaqfDhZVnu4')
        print(f'📺 Video: {info[\"title\"]}')
        
        # Download and upload
        result = await downloader.download_and_upload_video(
            url='https://www.youtube.com/watch?v=BaqfDhZVnu4',
            project_id=1,
            user_id=1
        )
        
        if result['success']:
            print('✅ Download completed!')
            print(f'  File: {result[\"filename\"]}')
            print(f'  MinIO: {result[\"minio_path\"]}')
            print(f'  Size: {result[\"filesize\"]} bytes')
            
            # Verify file exists
            object_name = result['minio_path'].replace('youtube-videos/', '')
            exists = await minio_service.file_exists(object_name)
            print(f'  Verified: {exists}')
        else:
            print('❌ Download failed')
            
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test_backend_integration())
"
```

### **7. Check MinIO Console**

Visit: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`
- Navigate to: `youtube-videos` → `users/1/projects/1/videos/`

### **8. Monitor via Logs**

```bash
# Watch backend logs
sudo docker logs backend_app_1 --tail 50 -f

# Watch MinIO logs
sudo docker logs backend_minio_1 --tail 20 -f
```

## 🔧 Environment Setup Checklist

Before running API commands:

1. **Services Running**: ✅ MinIO (9000/9001), Redis (6379)
2. **Cookies**: ✅ `/home/cat/github/slice-youtube/youtube_cookies.txt`
3. **Database**: ✅ `youtube_slicer.db` ready
4. **Backend**: Available on port 8001

## 🎯 Quick Test Sequence

```bash
# 1. Test MinIO connection
python -c "from app.services.minio_client import minio_service; import asyncio; asyncio.run(minio_service.ensure_bucket_exists())"

# 2. Test video info (with cookies)
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