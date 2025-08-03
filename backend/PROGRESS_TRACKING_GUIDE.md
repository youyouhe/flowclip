# 增强的下载进度跟踪指南

本指南介绍了如何使用改进的实时进度跟踪功能，该功能可以显示YouTube下载的详细进度信息。

## 🚀 功能概述

1. **实时进度显示** - 显示详细的下载进度，包括百分比、速度、剩余时间
2. **阶段跟踪** - 显示当前处理阶段（准备、分析、下载、合并、转换）
3. **片段进度** - 对于HLS下载，显示当前片段/总片段
4. **错误处理** - 实时显示错误和警告信息
5. **WebSocket实时更新** - 前端可以实时接收进度更新

## 📊 进度信息格式

下载过程中的每个阶段都会提供详细的进度信息：

### 1. 准备阶段
```
进度: 5% - 正在获取HLS播放列表...
进度: 10% - 检测到 893 个HLS片段
进度: 15% - 选择格式: 96 (hls-1080p)
```

### 2. 下载阶段
```
进度: 25.8% - 下载中 | 文件大小: 959.7MiB | 速度: 2.7MiB/s | 剩余: 05:44 | 片段: 24/893
```

### 3. 完成阶段
```
进度: 95% - 正在合并音视频流...
进度: 98% - 正在转换视频格式...
进度: 100% - 下载完成
```

## 🔧 使用方式

### 后端使用

#### 1. 直接调用下载服务
```python
from app.services.youtube_downloader_minio import downloader_minio

async def progress_callback(progress, message):
    print(f"下载进度: {progress:.1f}% - {message}")

result = await downloader_minio.download_and_upload_video(
    url="https://www.youtube.com/watch?v=VIDEO_ID",
    project_id=123,
    user_id=456,
    quality="best",
    progress_callback=progress_callback
)
```

#### 2. Celery任务中使用
```python
# 进度回调会自动集成到Celery任务中
# 无需额外配置，任务会自动更新进度
```

### 前端使用

#### 1. 轮询进度API
```javascript
// 定期查询进度
const checkProgress = async (videoId) => {
    const response = await fetch(`/api/v1/videos/${videoId}/progress`);
    const data = await response.json();
    
    console.log(`进度: ${data.download_progress}%`);
    console.log(`状态: ${data.processing_message}`);
    console.log(`阶段: ${data.processing_stage}`);
    
    return data;
};
```

#### 2. WebSocket实时更新
```javascript
// 使用WebSocket接收实时更新
const ws = new WebSocket('ws://localhost:8001/ws/progress');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`实时进度: ${data.download_progress}%`);
};
```

## 🧪 测试功能

### 1. 运行进度解析测试
```bash
cd backend
python test_progress_tracking.py
```

### 2. 运行完整流程测试
```bash
cd backend
python test_complete_progress.py
```

### 3. 手动测试API
```bash
# 获取视频进度
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8001/api/v1/videos/VIDEO_ID/progress
```

## 📋 API端点

### 获取视频进度
```http
GET /api/v1/videos/{video_id}/progress
Authorization: Bearer {token}
```

**响应格式：**
```json
{
    "video_id": 123,
    "title": "视频标题",
    "status": "downloading",
    "download_progress": 75.5,
    "processing_progress": 75.5,
    "processing_stage": "download",
    "processing_message": "下载中 | 文件大小: 959.7MiB | 速度: 2.7MiB/s | 剩余: 05:44",
    "file_size": 1006632960,
    "duration": 213,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:01:30Z",
    "processing_tasks": [
        {
            "id": 1,
            "task_type": "download",
            "status": "running",
            "progress": 75.5,
            "stage": "download",
            "message": "正在下载视频..."
        }
    ]
}
```

### 获取任务状态
```http
GET /api/v1/videos/{video_id}/task-status/{task_id}
Authorization: Bearer {token}
```

## 🔍 调试信息

### 查看详细日志
在 `backend/backend.log` 中可以查看详细的进度跟踪日志：

```bash
tail -f backend/backend.log | grep -E "(progress|yt-dlp|download)"
```

### 常见日志格式
```
[INFO] 下载进度: 25.8% - 下载中 | 文件大小: 959.7MiB | 速度: 2.7MiB/s | 剩余: 05:44 | 片段: 24/893
[DEBUG] yt-dlp输出: [download] 25.8% of ~959.74MiB at    2.67MiB/s ETA 05:44 (frag 24/893)
[INFO] 阶段变更: downloading -> merging
```

## 🚨 故障排除

### 1. 进度不更新
- 检查Celery worker是否运行
- 检查Redis连接是否正常
- 查看 `backend.log` 中的错误信息

### 2. 下载失败
- 检查网络连接
- 验证YouTube URL是否有效
- 检查是否有可用的cookie文件

### 3. 进度解析错误
- 检查yt-dlp版本是否兼容
- 查看详细日志中的解析错误
- 验证输出格式是否匹配正则表达式

## 📈 性能优化

### 1. 更新频率控制
- 进度更新最小间隔：1秒
- 进度变化阈值：0.5%
- 避免过于频繁的更新

### 2. 日志级别
- 生产环境：INFO级别
- 调试环境：DEBUG级别
- 错误追踪：ERROR级别

## 🔄 集成示例

### 完整的下载流程
```python
from app.services.youtube_downloader_minio import downloader_minio
from app.services.progress_service import update_video_progress

async def enhanced_download(url, project_id, user_id, video_id):
    """增强的下载流程"""
    
    # 更新初始状态
    await update_video_progress(video_id, user_id, {
        'status': 'downloading',
        'processing_stage': 'preparing',
        'processing_message': '开始下载视频...'
    })
    
    # 执行下载
    result = await downloader_minio.download_and_upload_video(
        url=url,
        project_id=project_id,
        user_id=user_id,
        video_id=video_id,
        progress_callback=lambda progress, message: update_video_progress(
            video_id, user_id, {
                'download_progress': progress,
                'processing_message': message,
                'status': 'downloading'
            }
        )
    )
    
    if result.get('success'):
        await update_video_progress(video_id, user_id, {
            'status': 'completed',
            'download_progress': 100.0,
            'processing_message': '下载完成!',
            'file_size': result['filesize'],
            'duration': result['duration']
        })
    else:
        await update_video_progress(video_id, user_id, {
            'status': 'failed',
            'processing_error': result.get('error', '下载失败')
        })
    
    return result
```