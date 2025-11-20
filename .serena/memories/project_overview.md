# FlowClip (EchoClip) 项目概览

## 项目简介
FlowClip 是一个全面的视频处理平台，专注于自动化视频编辑工作流程。系统能够：
- 自动下载 YouTube 视频（支持需要登录的视频）
- 提取音频并进行静音检测分割
- 使用 ASR（SenseVoice/Whisper）生成字幕
- 基于 AI 分析生成视频切片建议
- 导出到 CapCut 进行进一步编辑

## 技术架构

### 后端技术栈
- **Web 框架**: FastAPI (Python 3.8+)
- **异步处理**: Celery + Redis
- **数据库**: MySQL 8.0 (生产) / SQLite (开发)
- **对象存储**: MinIO (S3 兼容)
- **视频处理**: FFmpeg + yt-dlp
- **AI 集成**: OpenAI API, OpenRouter
- **ASR 服务**: SenseVoice/Whisper (外部服务)

### 前端技术栈
- **框架**: React 18 + TypeScript
- **UI 组件**: Ant Design
- **状态管理**: Zustand
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **HTTP 客户端**: Axios
- **WebSocket**: 实时进度更新

### 微服务架构
- **Backend API**: FastAPI 应用服务器 (端口 8001)
- **Celery Worker**: 后台任务处理器
- **Celery Beat**: 定时任务调度器
- **Callback Server**: TUS 协议回调服务器 (端口 9090)
- **MCP Server**: Model Context Protocol 服务器 (端口 8002)
- **Frontend**: React 开发服务器 (端口 3000)

### 核心功能模块
1. **用户认证**: JWT + Google OAuth
2. **项目管理**: 视频组织和管理
3. **视频下载**: yt-dlp 集成，支持 cookies 认证
4. **音频处理**: FFmpeg 音频提取和静音分割
5. **ASR 字幕**: SenseVoice/Whisper 自动语音识别
6. **AI 分析**: LLM 内容分析和切片建议
7. **视频切片**: 基于分析结果的片段创建
8. **CapCut 集成**: 导出到剪映草稿
9. **实时进度**: WebSocket 进度推送
10. **TUS 协议**: 大文件分块上传和断点续传

## 部署特性
- **容器化**: Docker + Docker Compose
- **自动化部署**: deploy.sh 脚本
- **健康检查**: 所有服务都包含健康检查
- **日志管理**: 结构化日志和轮转
- **资源限制**: 内存和 CPU 使用控制
- **数据持久化**: Docker 卷挂载
- **网络安全**: 内部网络隔离