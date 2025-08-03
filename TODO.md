# YouTube Slicer Debug Todo List

## ✅ Issues Fixed

### High Priority - COMPLETED ✅
- [x] **Debug duplicate video download error** - 'Multiple rows were found when one or none was required'
  - Fixed: Replaced `scalar_one_or_none()` with `first()` and proper tuple handling
  - Added ordering by `created_at.desc()` to get most recent video
  - Files updated: backend/app/tasks/video_tasks.py

- [x] **Fix frontend WebSocket progress updates**
  - Fixed: Added progress service initialization in startup event
  - Fixed: WebSocket endpoint now properly connected to progress updates
  - Files updated: backend/app/main.py, progress service integration

### Medium Priority - COMPLETED ✅
- [x] **Add database unique constraint**
  - Created: fix_duplicate_videos.py script to handle existing duplicates
  - Added: Unique index on (url, project_id) to prevent future duplicates

- [x] **Review download task logic**
  - Fixed: All video lookup queries now handle multiple results correctly
  - Improved: Uses most recent video instead of failing on duplicates

- [x] **Test WebSocket connection flow**
  - Created: test_websocket_fix.py for testing connections
  - Verified: WebSocket endpoints are accessible and functional

- [x] **Verify progress update callbacks**
  - Fixed: Progress service properly initialized on startup
  - Fixed: WebSocket notifications are now properly broadcast

## 🧪 Testing Commands

```bash
# Test the fixes
python fix_duplicate_videos.py
python test_websocket_fix.py

# Verify database fixes
python -c "
import sqlite3
conn = sqlite3.connect('backend/youtube_slicer.db')
cursor = conn.cursor()
cursor.execute('SELECT url, project_id, COUNT(*) FROM videos GROUP BY url, project_id HAVING COUNT(*) > 1')
print('Remaining duplicates:', cursor.fetchall())
conn.close()
"

# Test WebSocket with real token
# 1. First get a valid token:
# curl -X POST http://localhost:8001/api/v1/auth/login -H "Content-Type: application/json" -d '{"username": "demo", "password": "demo123"}'
# 2. Then test WebSocket with that token
```

## 🚀 Quick Start After Fixes

```bash
# 1. Stop all services
docker-compose down

# 2. Fix duplicate videos
python fix_duplicate_videos.py

# 3. Start services
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
celery -A app.core.celery worker --loglevel=info

# 4. Test download
# Use the same video URL - it should now work without duplicate errors
```

## Quick Fixes Needed

1. **Database Schema Fix**:
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS idx_video_url_project ON videos(url, project_id);
   ```

2. **Download Task Fix**:
   - Replace `scalar_one_or_none()` with `first()` and handle duplicates
   - Add logic to check for existing videos before creating new ones

3. **WebSocket Debug**:
   - Test: `curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8001/ws/progress/YOUR_TOKEN`
   - Check: Redis pub/sub for progress messages

## Testing Commands

```bash
# Check for duplicate videos
python -c "
import sqlite3
conn = sqlite3.connect('backend/youtube_slicer.db')
cursor = conn.cursor()
cursor.execute('SELECT url, project_id, COUNT(*) FROM videos GROUP BY url, project_id HAVING COUNT(*) > 1')
duplicates = cursor.fetchall()
print('Duplicate videos:', duplicates)
conn.close()
"

# Test WebSocket connection
python test_websocket.html
```