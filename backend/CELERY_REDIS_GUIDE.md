# Celery和Redis连接问题解决指南

本指南包含了解决Celery与Redis连接问题的各种工具和方法。

## 问题诊断

首先，我们创建了一个诊断工具来检查Redis连接是否正常：

```bash
python test_redis_connection.py
```

如果Redis连接正常，但Celery任务仍然失败，可能是以下原因：

1. Celery配置问题
2. Redis URL格式问题
3. 任务定义复杂度问题
4. CORS配置问题(对API请求有影响)

## 简单Celery测试

我们创建了一个最小化的Celery任务测试脚本，用于验证基础连接：

```bash
# 先启动一个专门的Worker
cd backend
celery -A test_celery_simple worker --loglevel=info

# 在另一个终端运行测试任务
python test_celery_simple.py
```

如果这个简单测试能够成功，但实际项目中的任务失败，则问题可能出在项目的任务定义或配置上。

## Celery命令对比

原始命令：
```bash
celery -A app.core.celery:celery_app worker --loglevel=info --pool=solo
```

新命令：
```bash
celery -A app.core.celery worker --loglevel=info --concurrency=2
```

主要区别：
- `:celery_app`指定具体对象 vs 只指定模块路径
- `--pool=solo`(单进程模式) vs `--concurrency=2`(双进程模式)

## 故障排除步骤

1. **Redis连接检查**
   ```bash
   python test_redis_connection.py
   ```

2. **尝试最简单的Celery任务**
   ```bash
   # 先启动Worker
   celery -A test_celery_simple worker --loglevel=info
   
   # 然后在另一个终端运行
   python test_celery_simple.py
   ```

3. **检查环境变量**
   确保`.env`文件中的`REDIS_URL`指向正确的地址：
   ```
   REDIS_URL=redis://192.168.8.107:6379
   ```

4. **尝试单进程模式**
   ```bash
   celery -A app.core.celery:celery_app worker --loglevel=info --pool=solo
   ```

5. **查看Celery任务日志**
   增加日志级别查看更详细信息：
   ```bash
   celery -A app.core.celery:celery_app worker --loglevel=debug --pool=solo
   ```

## 如果问题仍然存在

如果以上步骤都无法解决问题，考虑以下方案：

1. 暂时使用同步处理方式，跳过Celery
2. 检查Docker中的Redis配置
3. 尝试在Docker容器中运行Celery worker

## 参考配置

正确的Celery配置应当如下：

```python
from celery import Celery
import os
from dotenv import load_dotenv

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path)

# 直接从环境变量获取Redis URL
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

celery_app = Celery(
    "youtube_slicer",
    broker=redis_url,
    backend=redis_url,
    include=["app.tasks.video_tasks"]
)

# 基础配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry=True,
    broker_connection_max_retries=5,
)