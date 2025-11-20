# FlowClip 开发命令手册

## 快速启动命令

### 完整系统启动 (推荐)
```bash
# 启动所有服务 (Redis, MinIO, MySQL, 后端, 前端, Celery)
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 单独服务启动
```bash
# 启动基础服务
docker-compose up -d redis minio mysql

# 后端服务
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Celery Worker (新终端)
cd backend
celery -A app.core.celery worker --loglevel=info --concurrency=4

# Celery Beat (新终端)
cd backend
celery -A app.core.celery beat --loglevel=info

# 前端服务 (新终端)
cd frontend
npm run dev
```

## 后端开发命令

### 环境管理
```bash
# 安装依赖
cd backend
pip install -r requirements.txt
pip install -r requirements-audio.txt

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 数据库迁移
alembic upgrade head

# 创建新迁移
alembic revision --autogenerate -m "migration message"

# 重置数据库
alembic downgrade base
alembic upgrade head
```

### 测试命令
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_video_api.py -v

# 运行测试并生成覆盖率报告
pytest --cov=app --cov-report=html

# 运行异步测试
pytest tests/test_async.py -v
```

### 开发工具
```bash
# 检查代码风格
flake8 app/
black app/

# 类型检查
mypy app/

# 依赖检查
python check_dependencies.py

# 健康检查
python test_health_check.py

# 数据库结构检查
python check_db_structure.py
```

### 服务管理脚本
```bash
# 重启所有服务
./restart_services.sh

# 检查服务状态
./check_services.sh

# 停止所有服务
./stop_services.sh

# 快速部署
./quick_deploy.sh <PUBLIC_IP>

# 完整部署
./deploy.sh <PUBLIC_IP> <PRIVATE_IP>
```

## 前端开发命令

### 基础命令
```bash
cd frontend

# 安装依赖
npm install

# 开发服务器
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview

# 代码检查
npm run lint

# 类型检查
npx tsc --noEmit
```

### 高级命令
```bash
# 安装特定依赖
npm install antd @ant-design/icons
npm install axios react-query
npm install zustand

# 更新依赖
npm update

# 安全审计
npm audit

# 清理缓存
npm cache clean --force
```

## Celery 任务管理

### Worker 管理
```bash
# 启动 Worker (推荐)
celery -A app.core.celery worker --loglevel=info --concurrency=4

# 单进程模式 (调试用)
celery -A app.core.celery worker --loglevel=info --pool=solo

# 调试模式
celery -A app.core.celery worker --loglevel=debug

# 监控 Worker
celery -A app.core.celery events
```

### 任务监控
```bash
# 安装 Flower (Celery 监控)
pip install flower

# 启动 Flower
celery -A app.core.celery flower --port=5555

# 查看活动任务
celery -A app.core.celery inspect active

# 查看统计信息
celery -A app.core.celery inspect stats

# 清理队列
celery -A app.core.celery purge
```

### 任务调试
```bash
# 测试简单 Celery 任务
python test_celery_simple.py

# 调试 Celery 连接
python debug_celery_queue.py

# 测试 Redis 连接
python test_redis_connection.py
```

## 数据库管理

### MySQL 管理
```bash
# 连接到 MySQL 容器
docker-compose exec mysql mysql -u youtube_user -pyoutube_password youtube_slicer

# 备份数据库
docker-compose exec mysql mysqldump -u youtube_user -pyoutube_password youtube_slicer > backup.sql

# 恢复数据库
docker-compose exec -i mysql mysql -u youtube_user -pyoutube_password youtube_slicer < backup.sql

# 清理数据库
./clear_mysql_simple.sh
```

### 数据库清理脚本
```bash
# 清理处理任务
python scripts/run_cleanup.py --dry-run  # 预览
python scripts/run_cleanup.py             # 执行

# 清理过期数据
python cleanup_expired_videos.py

# 重置数据库
python clear_database.py
```

## MinIO 对象存储

### 管理
```bash
# 访问 MinIO Console
# URL: http://localhost:9001
# 用户名: minioadmin
# 密码: minioadmin

# 测试 MinIO 连接
python test_minio.py

# 修复 MinIO 配置
python debug_minio.sh

# 验证 MinIO 集成
python test_minio_fixed.sh
```

### 文件操作
```bash
# 列出存储桶
docker-compose exec minio mc ls local

# 清理文件
./verify_cleanup.sh
```

## TUS 和 ASR 集成

### TUS 测试
```bash
# TUS 集成测试
python test_tus_integration.py

# TUS 配置诊断
python diagnose_tus_threshold.py

# TUS 配置测试
python test_tus_config.py

# 回调服务器测试
python test_standalone_callback.py
```

### ASR 服务测试
```bash
# 测试 ASR 服务连接
python test_asr_connection.py

# 测试音频处理
python debug_extract_audio.py

# 测试进度跟踪
python debug_progress.py
```

## 系统监控和调试

### 日志查看
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f celery-worker
docker-compose logs -f frontend

# 查看实时日志
tail -f logs/celery-worker.log
tail -f logs/backend.log
```

### 性能监控
```bash
# 系统资源使用
docker stats

# 内存使用情况
free -h

# 磁盘使用情况
df -h

# 网络连接
netstat -tulpn
```

### 故障排除
```bash
# 服务健康检查
curl http://localhost:8001/health

# WebSocket 连接测试
python test_websocket_connection.py

# API 端点检查
python test_api_endpoints.py

# 完整系统诊断
python diagnose_backend.py
```

## 生产部署

### PM2 部署
```bash
# PM2 配置部署
./deploy_pm2.sh

# 查看进程状态
pm2 status

# 重启应用
pm2 restart flowclip-backend

# 查看日志
pm2 logs flowclip-backend
```

### 安全配置
```bash
# 设置 HTTPS
./setup_ssl.sh <DOMAIN>

# 配置防火墙
./configure_firewall.sh

# 创建用户
./install_user.sh
```

## 开发实用技巧

### 环境变量管理
```bash
# 复制环境模板
cp .env.example .env

# 验证配置
python test_config.py

# 检查配置文件
./verify-config.sh
```

### 代码质量
```bash
# 格式化代码
black backend/
isort backend/

# 检查代码质量
pylint app/
flake8 app/

# 运行所有检查
./run_tests.sh
```

### Git 工作流
```bash
# 创建功能分支
git checkout -b feature/new-feature

# 提交代码
git add .
git commit -m "feat: add new feature"

# 推送分支
git push origin feature/new-feature

# 合并到主分支
git checkout main
git merge feature/new-feature
```