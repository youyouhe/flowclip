# FlowClip 项目结构详解

## 根目录结构
```
EchoClip/
├── backend/                    # FastAPI 后端服务
├── frontend/                   # React 前端应用
├── docker-compose.yml          # Docker 编排配置
├── deploy.sh                   # 自动化部署脚本
├── .env.template              # 环境变量模板
├── README.md                  # 项目说明文档
├── README.zh.md              # 中文项目说明
├── requirements.txt           # Python 依赖列表
└── scripts/                   # 工具脚本
```

## 后端结构 (/backend)

### 应用核心 (/backend/app)
```
app/
├── main.py                    # FastAPI 应用入口
├── __init__.py               # 应用初始化
├── api/                      # API 路由定义
│   └── v1/                   # API v1 版本
│       ├── auth.py          # 认证相关 API
│       ├── videos.py        # 视频管理 API
│       ├── projects.py      # 项目管理 API
│       ├── processing.py    # 处理任务 API
│       ├── slices.py        # 视频切片 API
│       └── system.py        # 系统配置 API
├── core/                     # 核心配置和服务
│   ├── config.py            # 应用配置
│   ├── security.py          # 安全认证
│   ├── database.py          # 数据库连接
│   ├── celery.py            # Celery 配置
│   ├── redis.py             # Redis 连接
│   └── minio.py             # MinIO 客户端
├── models/                   # SQLAlchemy 数据模型
│   ├── user.py              # 用户模型
│   ├── project.py           # 项目模型
│   ├── video.py             # 视频模型
│   ├── processing_task.py   # 处理任务模型
│   ├── transcript.py        # 字幕模型
│   ├── video_slice.py       # 视频切片模型
│   └── system_config.py     # 系统配置模型
├── schemas/                  # Pydantic 数据模式
│   ├── user.py              # 用户数据模式
│   ├── project.py           # 项目数据模式
│   ├── video.py             # 视频数据模式
│   ├── processing.py        # 处理任务模式
│   └── common.py            # 通用模式
├── services/                 # 业务逻辑服务
│   ├── auth_service.py      # 认证服务
│   ├── video_service.py     # 视频处理服务
│   ├── youtube_service.py   # YouTube 下载服务
│   ├── audio_processor.py   # 音频处理服务
│   ├── asr_service.py       # ASR 字幕服务
│   ├── llm_service.py       # AI 分析服务
│   ├── capcut_service.py    # CapCut 集成服务
│   ├── tus_asr_client.py    # TUS ASR 客户端
│   ├── file_size_detector.py # 文件大小检测服务
│   └── progress_service.py  # 进度跟踪服务
├── tasks/                    # Celery 后台任务
│   ├── video_tasks.py       # 视频处理任务
│   ├── audio_tasks.py       # 音频处理任务
│   ├── asr_tasks.py         # ASR 处理任务
│   ├── llm_tasks.py         # AI 分析任务
│   └── cleanup_tasks.py     # 清理任务
└── utils/                    # 工具函数
    ├── file_utils.py        # 文件操作工具
    ├── video_utils.py       # 视频处理工具
    └── validation_utils.py  # 验证工具
```

### 数据库迁移 (/backend/alembic)
```
alembic/
├── versions/                 # 迁移版本文件
├── env.py                   # Alembic 环境配置
├── script.py.mako           # 迁移脚本模板
└── alembic.ini              # Alembic 配置文件
```

### 测试代码 (/backend/tests)
```
tests/
├── conftest.py              # pytest 配置
├── test_auth.py             # 认证测试
├── test_video_api.py        # 视频 API 测试
├── test_processing.py       # 处理任务测试
├── test_asr_service.py      # ASR 服务测试
├── test_minio.py            # MinIO 集成测试
├── test_tus_integration.py  # TUS 集成测试
└── fixtures/                # 测试数据
```

### 脚本工具 (/backend/scripts)
```
scripts/
├── run_cleanup.py           # 任务清理脚本
├── cleanup_processing_tasks.py  # 处理任务清理
├── init_system_config.py    # 系统配置初始化
├── backup_database.py       # 数据库备份
└── create_test_user.py      # 测试用户创建
```

## 前端结构 (/frontend)

### 源代码 (/frontend/src)
```
src/
├── main.tsx                 # React 应用入口
├── App.tsx                  # 根组件
├── index.css                # 全局样式
├── pages/                   # 页面组件
│   ├── HomePage.tsx         # 首页
│   ├── LoginPage.tsx        # 登录页
│   ├── ProjectPage.tsx      # 项目页面
│   ├── VideoManager.tsx     # 视频管理
│   ├── VideoPlayer.tsx      # 视频播放器
│   ├── SliceEditor.tsx      # 切片编辑器
│   └── SettingsPage.tsx     # 设置页面
├── components/              # 可复用组件
│   ├── VideoCard.tsx        # 视频卡片
│   ├── ProjectCard.tsx      # 项目卡片
│   ├── ProgressBar.tsx      # 进度条
│   ├── Timeline.tsx         # 时间轴
│   ├── FileUpload.tsx       # 文件上传
│   └── WebSocketStatus.tsx  # WebSocket 状态
├── services/                # API 客户端
│   ├── api.ts               # API 基础配置
│   ├── auth.ts              # 认证服务
│   ├── video.ts             # 视频服务
│   ├── project.ts           # 项目服务
│   ├── websocket.ts         # WebSocket 服务
│   └── upload.ts            # 文件上传服务
├── store/                   # Zustand 状态管理
│   ├── authStore.ts         # 认证状态
│   ├── videoStore.ts        # 视频状态
│   ├── projectStore.ts      # 项目状态
│   └── progressStore.ts     # 进度状态
├── types/                   # TypeScript 类型定义
│   ├── auth.ts              # 认证类型
│   ├── video.ts             # 视频类型
│   ├── project.ts           # 项目类型
│   └── api.ts               # API 响应类型
├── hooks/                   # 自定义 Hooks
│   ├── useAuth.ts           # 认证 Hook
│   ├── useWebSocket.ts      # WebSocket Hook
│   ├── useVideoPlayer.ts    # 视频播放器 Hook
│   └── useProgress.ts       # 进度跟踪 Hook
└── utils/                   # 工具函数
    ├── format.ts            # 格式化工具
    ├── validation.ts        # 验证工具
    └── constants.ts         # 常量定义
```

### 配置文件
```
frontend/
├── package.json             # 依赖配置
├── tsconfig.json           # TypeScript 配置
├── vite.config.ts          # Vite 构建配置
├── tailwind.config.js      # Tailwind CSS 配置
├── postcss.config.js       # PostCSS 配置
├── .env.example           # 环境变量模板
├── Dockerfile.dev         # 开发环境 Docker
└── Dockerfile             # 生产环境 Docker
```

## 服务架构

### Docker 服务
```yaml
# docker-compose.yml 主要服务
services:
  mysql:           # MySQL 8.0 数据库
  redis:           # Redis 缓存和消息队列
  minio:           # MinIO 对象存储
  backend:         # FastAPI 后端 API
  frontend:        # React 前端应用
  celery-worker:   # Celery 后台任务处理器
  celery-beat:     # Celery 定时任务调度器
  callback-server: # TUS 回调服务器
  mcp-server:      # MCP 服务器
```

### 端口分配
```
8001: FastAPI 后端 API
8002: MCP 服务器
3000: React 前端开发服务器
3306: MySQL 数据库
6379: Redis
9000: MinIO API
9001: MinIO 控制台
9090: TUS 回调服务器
5555: Flower 监控 (可选)
```

## 数据流程

### 视频处理流程
```
YouTube URL → yt-dlp 下载 → FFmpeg 音频提取 → 静音检测分割 → ASR 字幕生成 → AI 分析 → 视频切片 → CapCut 导出
```

### 异步任务流程
```
API 请求 → Celery 任务队列 → Worker 执行 → 进度更新 (WebSocket) → 结果存储 → 通知前端
```

### TUS 大文件处理
```
文件大小检测 → TUS 上传 → 分块传输 → ASR 处理 → 回调接收 → 结果获取
```

## 关键集成点

### ASR 服务集成
- **SenseVoice**: 中文优化，速度较快
- **Whisper**: 多语言支持，精度较高
- **TUS 协议**: 大文件分块上传和断点续传

### CapCut 集成
- **草稿创建**: 自动生成剪映草稿
- **效果应用**: 音频增强和特效
- **字幕同步**: 时间轴对齐

### 存储集成
- **MinIO**: S3 兼容对象存储
- **文件分类**: 原始视频、音频、字幕、切片
- **访问控制**: 签名 URL 和权限管理

## 开发工作流

### 功能开发流程
1. **后端 API**: FastAPI 路由和业务逻辑
2. **数据库模型**: SQLAlchemy 模型和迁移
3. **异步任务**: Celery 任务定义
4. **前端组件**: React 组件和状态管理
5. **WebSocket**: 实时进度更新
6. **测试**: 单元测试和集成测试

### 调试技巧
- **日志查看**: `docker-compose logs -f <service>`
- **数据库检查**: MySQL 客户端连接
- **任务监控**: Flower 或 Celery inspect
- **API 测试**: Postman 或 curl
- **前端调试**: React DevTools

### 部署流程
1. **环境准备**: Docker 和依赖安装
2. **配置设置**: 环境变量和密钥
3. **服务启动**: docker-compose up
4. **数据库迁移**: Alembic upgrade
5. **健康检查**: 服务状态验证
6. **测试验证**: 功能测试确认