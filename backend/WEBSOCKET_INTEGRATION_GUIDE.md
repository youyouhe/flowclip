# WebSocket实时进度集成指南

本指南介绍如何在下载页面实现WebSocket实时进度更新。

## 🎯 功能概述

### ✅ **支持的场景**
1. **下载进度** - YouTube视频下载的实时进度
2. **音频提取** - 从视频提取音频的进度
3. **音频分割** - 音频按静音检测分割的进度
4. **字幕生成** - ASR生成字幕的进度
5. **视频切片** - 根据分析结果切片视频的进度

### 📊 **进度数据结构**

```json
{
  "type": "progress_update",
  "video_id": 123,
  "video_title": "视频标题",
  "video_status": "downloading",
  "download_progress": 75.5,
  "processing_progress": 75.5,
  "processing_stage": "download",
  "processing_message": "下载中 | 文件大小: 959.7MiB | 速度: 2.7MiB/s | 剩余: 05:44",
  "tasks": [
    {
      "id": 1,
      "task_type": "download",
      "task_name": "视频下载",
      "status": "running",
      "progress": 75.5,
      "stage": "download",
      "message": "正在下载..."
    }
  ]
}
```

## 🚀 快速集成

### 1. 基础HTML集成

```html
<!-- 引入进度管理器 -->
<script src="frontend_websocket_integration.js"></script>

<!-- 进度显示组件 -->
<div id="progress-123" class="download-progress-container">
    <div class="progress-bar-container">
        <div class="progress-bar" style="width: 0%"></div>
    </div>
    <div class="progress-text">0.0%</div>
    <div class="status-message">正在准备下载...</div>
</div>
```

### 2. JavaScript集成

```javascript
// 初始化进度管理器
const progressManager = new DownloadProgressManager();

// 在下载开始时初始化
await progressManager.initialize(token, videoId);

// 监听进度更新
progressManager.on('downloadComplete', (event) => {
    console.log('下载完成:', event.detail.videoId);
    // 跳转到视频详情页
    window.location.href = `/videos/${event.detail.videoId}`;
});
```

## 🔧 WebSocket使用

### 连接建立
```javascript
// WebSocket URL格式
ws://localhost:8001/ws/progress/{token}
```

### 消息类型
- **订阅消息**: `{"type": "subscribe", "video_id": 123}`
- **心跳消息**: `{"type": "ping"}`
- **进度更新**: 服务器推送的进度数据

### 处理断线重连

进度管理器自动处理：
- WebSocket断线重连（最多5次）
- 失败后自动切换到轮询模式
- 连接状态实时显示

## 📱 React集成示例

```jsx
import { useEffect, useState } from 'react';
import DownloadProgressManager from './DownloadProgressManager';

function DownloadProgress({ videoId }) {
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('preparing');
    const [message, setMessage] = useState('');
    
    useEffect(() => {
        const manager = new DownloadProgressManager();
        const token = localStorage.getItem('authToken');
        
        manager.initialize(token, videoId);
        
        manager.onProgress((data) => {
            setProgress(data.download_progress);
            setStatus(data.video_status);
            setMessage(data.processing_message);
        });
        
        return () => manager.disconnect();
    }, [videoId]);
    
    return (
        <div className="progress-container">
            <div className="progress-bar">
                <div style={{ width: `${progress}%` }} />
            </div>
            <div>{progress.toFixed(1)}% - {message}</div>
        </div>
    );
}
```

## 🎨 样式定制

### 进度条样式
```css
.progress-bar-container {
    width: 100%;
    height: 8px;
    background-color: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #45a049);
    transition: width 0.3s ease;
    position: relative;
}

.progress-bar::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    right: 0;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255,255,255,0.3),
        transparent
    );
    animation: shimmer 2s infinite;
}
```

## 🐛 调试指南

### 常见问题排查

1. **WebSocket连接失败**
   ```bash
   # 检查WebSocket端点
   curl -i -N \
   -H "Connection: Upgrade" \
   -H "Upgrade: websocket" \
   -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
   -H "Sec-WebSocket-Version: 13" \
   http://localhost:8001/ws/progress/YOUR_TOKEN
   ```

2. **进度不更新**
   - 检查浏览器控制台WebSocket消息
   - 验证token有效性
   - 确认video_id正确

3. **使用调试工具**
   ```bash
   # 测试进度API
   python debug_progress.py
   
   # 测试WebSocket
   node test_websocket.js
   ```

## 📡 网络要求

- **WebSocket端口**: 8001
- **协议**: ws:// 或 wss:// (生产环境)
- **认证**: Bearer token in URL path
- **心跳**: 每30秒自动ping/pong

## 🔄 回退机制

当WebSocket不可用时，系统自动切换到轮询模式：
- 每2秒轮询一次进度API
- 保持相同的UI体验
- 自动检测WebSocket恢复

## 🎯 下一步

1. 将`DownloadProgressManager`集成到你的前端项目
2. 根据你的UI框架调整样式
3. 测试WebSocket连接和断线重连
4. 处理下载完成后的页面跳转