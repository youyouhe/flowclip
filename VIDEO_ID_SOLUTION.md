# Video ID 一致性问题和实时任务状态解决方案

## 问题分析

### Video ID 类型不一致
1. **数据库 video_id**: 整数类型，内部使用
2. **YouTube video_id**: 字符串类型，YouTube 平台标识
3. **WebSocket 传输**: 数字类型
4. **前端处理**: number 类型

### 获取运行中视频 ID 的方法

#### 后端 API 端点
1. **GET /api/v1/videos/active** - 获取所有非完成状态的视频
2. **GET /api/v1/status/videos/running** - 获取所有正在运行的视频 IDs（新增）
3. **GET /api/v1/processing/tasks** - 获取处理任务列表
4. **GET /api/v1/status** - 获取系统状态和统计

#### WebSocket 实时更新
- 连接: `ws://localhost:8001/ws/progress/{token}`
- 消息格式: `{"type": "progress_update", "video_id": 123, "video_status": "processing", ...}`

## 解决方案

### 1. 新增 API 端点

已添加 `GET /api/v1/status/videos/running` 端点，返回所有正在运行的视频 IDs 列表。

### 2. 前端实时状态更新策略

```javascript
// 获取运行中的视频 IDs
const runningVideoIds = await dashboardAPI.getRunningVideoIds();

// WebSocket 连接和状态更新
wsService.on('progress_update', (data) => {
  const { video_id, video_status, download_progress, processing_progress } = data;
  
  // 更新对应视频的状态
  updateVideoStatus(video_id, {
    status: video_status,
    download_progress,
    processing_progress
  });
});
```

### 3. 测试脚本

创建了 `test_running_video_ids.py` 脚本来验证获取运行中视频 IDs 的功能。

## 使用方法

### 获取运行中的视频 IDs
```bash
# 运行测试脚本
python test_running_video_ids.py

# 或者直接调用 API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/v1/status/videos/running
```

### 实时状态更新
```javascript
// 1. 获取初始的运行中视频 IDs
const runningVideoIds = await dashboardAPI.getRunningVideoIds();

// 2. 建立 WebSocket 连接
wsService.connect();

// 3. 监听进度更新
wsService.on('progress_update', (data) => {
  console.log('Video ID:', data.video_id);
  console.log('Status:', data.video_status);
  console.log('Progress:', data.download_progress);
});
```

## 关键点

1. **Video ID 一致性**: 确保前后端使用相同的数字类型 ID
2. **实时更新**: 使用 WebSocket 推送进度更新
3. **状态查询**: 定期查询运行中的视频 IDs 以确保同步
4. **错误处理**: 处理视频 ID 不存在的情况

## 测试和验证

运行测试脚本验证功能：
```bash
python test_running_video_ids.py
```

这个解决方案提供了完整的视频 ID 管理和实时状态更新机制。