# FlowClip 常见任务和问题解决方案

## 新功能开发任务

### 1. 添加新的 API 端点
```bash
# 1. 在 backend/app/api/v1/ 创建新路由文件
touch backend/app/api/v1/new_feature.py

# 2. 定义 Pydantic 模式
touch backend/app/schemas/new_feature.py

# 3. 实现业务逻辑
touch backend/app/services/new_feature_service.py

# 4. 添加数据库模型 (如需要)
touch backend/app/models/new_feature.py

# 5. 创建迁移文件
cd backend
alembic revision --autogenerate -m "add new feature"

# 6. 应用迁移
alembic upgrade head

# 7. 编写测试
touch backend/tests/test_new_feature.py
```

### 2. 添加新的前端页面
```bash
# 1. 创建页面组件
touch frontend/src/pages/NewPage.tsx

# 2. 定义类型
touch frontend/src/types/newFeature.ts

# 3. 添加 API 服务
touch frontend/src/services/newFeature.ts

# 4. 创建状态管理
touch frontend/src/store/newFeatureStore.ts

# 5. 添加路由 (在 App.tsx 中)
<Route path="/new-feature" element={<NewPage />} />
```

### 3. 添加新的 Celery 任务
```bash
# 1. 创建任务文件
touch backend/app/tasks/new_task.py

# 2. 实现任务逻辑
# @celery_app.task(bind=True)
# def new_processing_task(self, video_id: str):
#     # 任务实现

# 3. 在 API 中调用任务
# from app.tasks.new_task import new_processing_task
# task = new_processing_task.delay(video_id)

# 4. 编写测试
touch backend/tests/test_new_task.py
```

## 系统维护任务

### 1. 数据库维护
```bash
# 备份数据库
docker-compose exec mysql mysqldump -u youtube_user -pyoutube_password youtube_slicer > backup_$(date +%Y%m%d).sql

# 清理过期数据 (30天前)
python scripts/run_cleanup.py --older-than 30

# 重建索引
docker-compose exec mysql mysql -u youtube_user -pyoutube_password -e "OPTIMIZE TABLE videos, processing_tasks, video_slices;"

# 检查数据库完整性
python check_db_structure.py
```

### 2. 存储清理
```bash
# 清理 MinIO 中的孤立文件
python cleanup_expired_videos.py

# 验证文件完整性
./verify_cleanup.sh

# 手动清理大文件
docker-compose exec minio mc rm --recursive local/youtube-videos/temp/
```

### 3. 性能优化
```bash
# 监控系统资源
docker stats

# 分析慢查询
docker-compose exec mysql mysql -u youtube_user -pyoutube_password -e "SHOW PROCESSLIST;"

# 清理 Redis 内存
docker-compose exec redis redis-cli FLUSHDB

# 重启服务 (如需要)
docker-compose restart celery-worker
```

## 故障排除指南

### 1. 服务无法启动
```bash
# 检查端口占用
netstat -tulpn | grep :8001

# 检查环境变量
cat .env

# 查看详细错误日志
docker-compose logs backend

# 检查服务依赖
docker-compose ps
```

### 2. Celery 任务卡住
```bash
# 查看活动任务
celery -A app.core.celery inspect active

# 重启 Worker
docker-compose restart celery-worker

# 清理队列 (谨慎操作)
celery -A app.core.celery purge

# 查看任务详情
celery -A app.core.celery inspect reserved
```

### 3. 视频处理失败
```bash
# 检查 FFmpeg 安装
ffmpeg -version

# 验证视频文件
ffprobe /path/to/video.mp4

# 检查磁盘空间
df -h

# 查看处理日志
docker-compose logs celery-worker | grep "ERROR"
```

### 4. ASR 服务连接问题
```bash
# 测试 ASR 服务连接
curl -X POST http://192.168.8.107:5001/asr -F "file=@test.wav"

# 检查音频文件格式
file /path/to/audio.wav

# 测试 TUS 连接
python test_tus_integration.py

# 诊断 TUS 配置
python diagnose_tus_threshold.py
```

### 5. MinIO 连接问题
```bash
# 测试 MinIO 连接
python test_minio.py

# 修复权限问题
python debug_minio.sh

# 手动创建存储桶
docker-compose exec minio mc mb local/test-bucket

# 检查访问密钥
docker-compose exec minio mc config host ls
```

## 配置管理

### 1. 环境变量配置
```bash
# 复制模板
cp .env.example .env

# 编辑配置
nano .env

# 验证配置
python test_config.py

# 重新加载服务
docker-compose up -d --force-recreate backend
```

### 2. 系统配置更新
```python
# 在数据库中更新配置
from app.models.system_config import SystemConfigService
from app.core.database import get_sync_db

db = next(get_sync_db())
SystemConfigService.set_config_sync(db, "asr_model_type", "whisper", "ASR模型", "配置")
```

### 3. TUS 阈值动态更新
```python
# 更新 TUS 文件大小阈值
from app.services.file_size_detector import update_global_threshold
update_global_threshold(20)  # 设置为 20MB
```

## 测试任务

### 1. API 测试
```bash
# 运行所有 API 测试
pytest tests/test_video_api.py -v

# 测试特定端点
curl -X POST http://localhost:8001/api/v1/videos/download \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"url": "https://www.youtube.com/watch?v=test", "project_id": 1}'
```

### 2. WebSocket 测试
```bash
# 测试 WebSocket 连接
python test_websocket_connection.py

# 手动测试
wscat -c ws://localhost:8001/ws/progress/<token>
```

### 3. 完整流程测试
```bash
# 端到端测试
python test_complete_flow.py

# TUS 集成测试
python test_tus_integration.py

# 容错测试
python test_youtube_fault_tolerance.py
```

## 安全维护

### 1. 证书更新
```bash
# 更新 SSL 证书 (如使用 HTTPS)
./setup_ssl.sh <domain>

# 检查证书有效期
openssl x509 -in cert.pem -noout -dates
```

### 2. 密钥轮换
```bash
# 生成新的 JWT 密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 更新环境变量
# 编辑 .env 文件中的 SECRET_KEY

# 重启服务
docker-compose restart backend celery-worker
```

### 3. 访问控制
```bash
# 检查用户权限
docker-compose exec mysql mysql -u youtube_user -pyoutube_password -e "SELECT * FROM users;"

# 清理过期会话
# 编写清理脚本或手动清理
```

## 监控和日志

### 1. 系统监控
```bash
# 实时系统资源
htop

# Docker 容器状态
docker stats

# 网络连接
netstat -tulpn | grep :8001
```

### 2. 日志分析
```bash
# 查看错误日志
docker-compose logs backend | grep ERROR

# 查看特定时间段日志
docker-compose logs --since="2024-01-01T00:00:00" backend

# 导出日志
docker-compose logs backend > backend.log
```

### 3. 性能分析
```bash
# 数据库查询分析
docker-compose exec mysql mysql -u youtube_user -pyoutube_password -e "SHOW FULL PROCESSLIST;"

# 慢查询日志
# 需要在 MySQL 配置中启用慢查询日志
```

## 部署相关

### 1. 新环境部署
```bash
# 克隆项目
git clone <repository-url>
cd EchoClip

# 运行自动部署
./deploy.sh <PUBLIC_IP> <PRIVATE_IP>

# 验证部署
curl http://localhost:8001/health
```

### 2. 服务更新
```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d

# 运行迁移 (如需要)
cd backend
alembic upgrade head
```

### 3. 回滚操作
```bash
# 代码回滚
git checkout <previous-commit>

# 数据库回滚
alembic downgrade <revision>

# 服务回滚
docker-compose down
# 使用之前的 docker-compose.yml
docker-compose up -d
```

## 开发技巧

### 1. 调试技巧
```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用 IPython (推荐)
import IPython; IPython.embed()

# 查看变量
print(f"Variable: {variable}")

# 查看对象属性
print(dir(obj))
```

### 2. 日志记录
```python
import logging
logger = logging.getLogger(__name__)

# 记录信息
logger.info("Processing video: %s", video_id)
logger.error("Error processing video: %s", str(e))
```

### 3. 代码优化
```bash
# 代码格式化
black backend/
isort backend/

# 代码检查
flake8 backend/
pylint app/

# 类型检查
mypy app/
```

## 常用查询和操作

### 数据库查询
```sql
-- 查看处理任务状态
SELECT id, status, created_at FROM processing_tasks ORDER BY created_at DESC;

-- 查看用户项目
SELECT p.name, COUNT(v.id) as video_count 
FROM projects p 
LEFT JOIN videos v ON p.id = v.project_id 
WHERE p.user_id = 1 
GROUP BY p.id;

-- 清理过期任务
DELETE FROM processing_tasks 
WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY) 
AND status IN ('completed', 'failed');
```

### Redis 操作
```bash
# 连接 Redis
docker-compose exec redis redis-cli

# 查看所有键
KEYS *

# 查看特定键
GET tus_callback:task123

# 清理所有数据
FLUSHDB
```

### MinIO 操作
```bash
# 连接 MinIO
docker-compose exec minio mc ls local/

# 查看存储桶
mc ls local/youtube-videos/

# 下载文件
mc cp local/youtube-videos/video.mp4 ./video.mp4
```