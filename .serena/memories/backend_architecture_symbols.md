# EchoClip 后端架构符号分析

基于 `get_symbols_overview` 工具生成的项目架构概览

## 🏗️ 核心应用结构 (backend/app/main.py)

### 主要符号分析
- **`app`**: 应用程序根模块 (Variable)
- **`host`/`port`**: 服务器配置变量 (Variables)
- **`startup_event`**: 应用启动事件处理 (Function)
- **`shutdown_event`**: 应用关闭事件处理 (Function)
- **`root`**: 根路由处理器 (Function)
- **`health_check`**: 健康检查端点 (Function)

**架构特点**: 
- 标准的 FastAPI 应用结构
- 完整的生命周期管理
- 中间件集成 (header_cleanup_middleware, log_requests)
- 外部服务依赖等待 (wait_for_database, wait_for_redis)

---

## 🔐 认证系统 (backend/app/api/v1/auth.py)

### 核心符号
- **`router`**: FastAPI 路由器 (Variable)
- **`oauth2_scheme`**: OAuth2 密码承载者方案 (Variable)
- **`UserCreate`**: 用户创建数据模型 (Class)
- **`UserLogin`**: 用户登录数据模型 (Class)
- **`UserResponse`**: 用户响应数据模型 (Class)
- **`Token`**: JWT Token 模型 (Class)
- **`register`**: 用户注册端点 (Function)
- **`login`**: 用户登录端点 (Function)
- **`get_current_user_info`**: 获取当前用户信息 (Function)

**设计模式**: 
- Pydantic 模型验证
- JWT Token 认证
- OAuth2 标准

---

## ⚙️ 配置管理 (backend/app/core/config.py)

### 核心符号
- **`Settings`**: 主配置类 (Class)
- **`settings`**: 全局配置实例 (Variable)
- **`bootstrap_config`**: 启动配置管理 (Variable)
- **`USE_BOOTSTRAP`**: 启动模式标志 (Constant)

**配置能力**:
- 环境变量自动加载
- Bootstrap 配置支持
- 类型安全的配置访问
- 多环境配置管理

---

## 🗄️ 数据库层 (backend/app/core/database.py)

### 核心符号
- **`Base`**: SQLAlchemy 基础模型类 (Class)
- **`async_engine`**: 异步数据库引擎 (Variable)
- **`sync_engine`**: 同步数据库引擎 (Variable)
- **`AsyncSessionLocal`**: 异步会话工厂 (Variable)
- **`SyncSessionLocal`**: 同步会话工厂 (Variable)
- **`SyncDBContext`**: 同步数据库上下文管理器 (Class)
- **`get_db`**: 获取数据库会话 (Function)
- **`get_sync_db`**: 获取同步数据库会话 (Function)
- **`create_tables`**: 创建数据表 (Function)

**数据库特性**:
- SQLAlchemy 2.0 异步支持
- 双引擎模式 (async/sync)
- 上下文管理器模式
- 表结构管理

---

## 🔒 安全模块 (backend/app/core/security.py)

### 核心符号
- **`pwd_context`**: 密码哈希上下文 (Variable)
- **`oauth2_scheme`**: OAuth2 认证方案 (Variable)
- **`verify_password`**: 密码验证函数 (Function)
- **`get_password_hash`**: 密码哈希生成 (Function)
- **`create_access_token`**: JWT Token 创建 (Function)
- **`get_current_user`**: 当前用户认证 (Function)
- **`get_current_active_user`**: 活跃用户验证 (Function)
- **`get_current_user_from_token`**: Token 解析用户 (Function)

**安全特性**:
- bcrypt 密码哈希
- JWT Token 管理
- 多层用户验证
- OAuth2 标准

---

## 📊 数据模型层 (backend/app/models)

### Video 模型 (video.py)
- **`Video`**: 核心视频数据模型 (Class)

**模型特点**:
- SQLAlchemy 声明式基类
- 视频元数据管理
- 关系映射支持

---

## 🛠️ 服务层架构

### 核心服务文件 (通过 list_dir 发现)
- **`youtube_downloader.py`**: YouTube 视频下载服务
- **`youtube_downloader_minio.py`**: MinIO 集成下载服务
- **`audio_processor.py`**: 音频处理服务
- **`llm_service.py`**: AI 分析服务
- **`video_slicing_service.py`**: 视频切片服务
- **`minio_client.py`**: 对象存储客户端
- **`progress_service.py`**: 进度跟踪服务
- **`capcut_service.py`**: CapCut 集成服务
- **`jianying_service.py`**: 剪映集成服务
- **`asr_service.py`**: 自动语音识别服务
- **`tus_asr_client.py`**: TUS ASR 客户端
- **`file_size_detector.py`**: 文件大小检测服务
- **`state_manager.py`**: 状态管理服务
- **`system_config_service.py`**: 系统配置服务
- **`global_callback_manager.py`**: 全局回调管理
- **`standalone_callback_client.py`**: 独立回调客户端

**服务层特点**:
- 模块化设计
- 外部服务集成
- 异步处理支持
- 状态管理
- 错误处理

---

## 📋 任务处理层 (backend/app/tasks/video_tasks.py)

### 核心符号
- **`run_async`**: 异步任务执行器 (Variable)
- **`update_task_status`**: 任务状态更新 (Function)
- **`_wait_for_task_sync`**: 同步任务等待器 (Function)
- **`__all__`**: 公开模块接口 (Constant)

**任务特性**:
- Celery 集成
- 状态跟踪
- 同步/异步支持

---

## 🎯 架构洞察

### 1. **分层架构模式**
```
API 层 → 服务层 → 数据层 → 存储层
```

### 2. **依赖注入模式**
- FastAPI 依赖系统
- 数据库会话注入
- 用户认证注入

### 3. **异步优先设计**
- SQLAlchemy 2.0 异步
- FastAPI 异步路由
- Celery 后台任务

### 4. **外部服务集成**
- MinIO 对象存储
- YouTube API
- ASR 服务
- AI/LLM 服务
- CapCut/剪映集成

### 5. **配置驱动**
- 环境变量配置
- Bootstrap 支持
- 多环境适配

### 6. **安全设计**
- JWT Token 认证
- 密码安全哈希
- OAuth2 标准
- 用户权限验证

---

## 📚 开发指导

### 添加新服务的建议模式:
1. **创建数据模型** (models/)
2. **实现业务逻辑** (services/)
3. **定义 API 路由** (api/v1/)
4. **添加数据验证** (schemas/)
5. **编写后台任务** (tasks/)

### 代码约定:
- 使用 SQLAlchemy 2.0 语法
- 异步函数优先
- Pydantic 数据验证
- 类型提示完整
- 错误处理统一

---

*此架构分析基于 Serena MCP 的 `get_symbols_overview` 工具自动生成*