# Flowclip 前端实时进度集成指南

## 🚀 功能特性

### ✅ **实时进度追踪**
- **WebSocket连接**: 实时接收Celery下载任务进度
- **断线重连**: 自动处理网络中断，最大重试5次
- **回退机制**: WebSocket失败时自动切换到HTTP轮询
- **多视频支持**: 同时追踪多个视频的下载进度

### 📊 **进度展示**
- **下载进度**: 实时显示YouTube视频下载百分比
- **处理阶段**: 显示当前处理阶段（下载、音频提取、分割、ASR等）
- **详细信息**: 显示文件大小、下载速度、剩余时间等
- **状态指示**: 彩色状态标签和进度条

## 🏗️ 技术架构

### **前端组件**
- **VideoManagementPage**: 主视频管理页面
- **DownloadProgressManager**: WebSocket连接管理器
- **useAuth**: React Hook认证管理
- **apiService**: API请求封装

### **WebSocket消息类型**
```json
{
  "type": "progress_update",
  "video_id": 123,
  "video_title": "视频标题",
  "video_status": "downloading",
  "download_progress": 75.5,
  "processing_progress": 75.5,
  "processing_stage": "download",
  "processing_message": "下载中 | 文件大小: 959.7MiB | 速度: 2.7MiB/s",
  "tasks": [...]
}
```

## 📦 安装和配置

### **1. 安装依赖**
```bash
cd frontend
npm install
```

### **2. 启动开发服务器**
```bash
npm start
# 访问 http://localhost:3000
```

### **3. 构建生产版本**
```bash
npm run build
```

## 🔧 环境配置

### **环境变量**
创建 `.env` 文件：
```bash
REACT_APP_API_URL=http://localhost:8001
```

### **代理配置**
`package.json` 已配置代理：
```json
"proxy": "http://localhost:8001"
```

## 📱 使用方法

### **1. 登录**
- 访问 `http://localhost:3000`
- 使用演示账号：
  - 用户名: `demo`
  - 密码: `demo123`

### **2. 视频管理**
- **添加视频**: 输入YouTube URL开始下载
- **实时进度**: 进度条实时更新下载状态
- **状态查看**: 查看每个视频的详细处理状态
- **操作管理**: 支持删除、重新下载等操作

### **3. 进度追踪**
自动追踪以下阶段：
1. **下载阶段**: YouTube视频下载
2. **音频提取**: 从视频中提取音频
3. **音频分割**: 按静音检测分割音频
4. **ASR处理**: 语音识别生成字幕
5. **视频切片**: 根据字幕切片视频

## 🎯 实时特性

### **WebSocket连接**
- **端点**: `ws://localhost:8001/ws/progress/{token}`
- **自动重连**: 断线后自动重连
- **心跳机制**: 保持连接活跃

### **进度数据**
```javascript
// 使用示例
import { progressService } from './services/websocketService';

// 初始化
await progressService.initialize(token, videoId);

// 监听进度
progressService.on('progressUpdate', (data) => {
  console.log('进度更新:', data.download_progress + '%');
});

// 监听完成
progressService.on('downloadComplete', (data) => {
  console.log('下载完成:', data.video_id);
});
```

## 🔍 调试和故障排除

### **检查WebSocket连接**
```bash
# 测试WebSocket端点
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8001/ws/progress/YOUR_TOKEN
```

### **浏览器调试**
1. 打开开发者工具 (F12)
2. 切换到 Network 标签
3. 查看 WebSocket 连接状态
4. 检查 Console 中的日志信息

### **常见问题**

#### **WebSocket连接失败**
- 检查后端服务是否启动
- 确认端口8001是否开放
- 查看防火墙设置

#### **进度不更新**
- 检查token是否有效
- 确认video_id是否正确
- 查看后端日志

#### **跨域问题**
- 确保后端CORS配置正确
- 检查代理设置

## 📊 性能优化

### **前端优化**
- 虚拟滚动处理大量视频
- 防抖处理进度更新
- 图片懒加载

### **网络优化**
- WebSocket压缩
- 批量更新减少网络请求
- 心跳间隔优化

## 🔮 扩展功能

### **计划中的功能**
- 批量下载管理
- 下载队列优先级
- 断点续传
- 下载速度限制
- 通知提醒

### **高级特性**
- 下载历史记录
- 统计分析
- 移动端适配
- PWA支持

## 📞 支持

如有问题，请检查：
1. 后端服务是否正常运行
2. Redis服务状态
3. WebSocket端口是否开放
4. 浏览器控制台错误信息