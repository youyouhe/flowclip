# Processing Tasks 清理系统说明

## 概述

Processing Tasks 清理系统用于定期清理 `processing_tasks` 表中的僵尸任务和过期记录，防止数据库积累过多无用数据影响系统性能。

## 清理策略

### 1. 超时运行中的任务
- **条件**: 任务状态为 `RUNNING` 且超过 24 小时仍在运行
- **处理**: 标记为 `FAILURE` 状态，并记录超时原因
- **原因**: 任务可能因进程崩溃、网络问题或其他异常导致无法正常完成

### 2. 长期等待中的任务
- **条件**: 任务状态为 `PENDING` 且超过 2 小时仍在等待
- **处理**: 标记为 `FAILURE` 状态，并记录等待超时原因
- **原因**: 任务可能因队列积压、资源不足或其他问题无法被调度

### 3. 过期的失败任务
- **条件**: 任务状态为 `FAILURE` 且超过 7 天
- **处理**: 直接删除记录
- **原因**: 失败任务已保留足够时间用于排查问题，可以安全删除

### 4. 过期的成功任务
- **条件**: 任务状态为 `SUCCESS` 且超过 30 天
- **处理**: 直接删除记录
- **原因**: 成功任务已完成，保留过久无实际意义

## 使用方法

### 1. 自动定时清理 (推荐)

系统已配置 Celery Beat 定时任务，自动执行清理：

- **每天凌晨1点**: 执行试运行清理，仅查看需要清理的任务
- **每天凌晨2点**: 执行实际清理任务
- **每小时**: 重新加载系统配置

启动 Celery Worker 和 Beat：
```bash
# 启动 Celery Worker
celery -A app.core.celery worker --loglevel=info

# 启动 Celery Beat (定时任务调度器)
celery -A app.core.celery beat --loglevel=info
```

### 2. 手动执行清理

使用手动执行脚本进行清理或查看统计信息：

#### 基本用法
```bash
# 进入项目目录
cd /path/to/EchoClip/backend

# 执行标准清理
python scripts/run_cleanup.py

# 试运行模式（仅查看，不执行）
python scripts/run_cleanup.py --dry-run
```

#### 自定义参数
```bash
# 自定义超时时间
python scripts/run_cleanup.py --running-timeout 12 --failure-retention 3

# 只查看统计信息
python scripts/run_cleanup.py --stats-only
```

#### 强制清理特定任务
```bash
# 强制清理 5 天前的失败任务
python scripts/run_cleanup.py --force-status failure --older-than 5

# 强制清理 1 天前的等待任务
python scripts/run_cleanup.py --force-status pending --older-than 1
```

### 3. 直接使用清理脚本

```bash
# 基本清理
python scripts/cleanup_processing_tasks.py

# 试运行模式
python scripts/cleanup_processing_tasks.py --dry-run

# 自定义参数
python scripts/cleanup_processing_tasks.py \
    --running-timeout 12 \
    --pending-timeout 1 \
    --failure-retention 3 \
    --success-retention 7
```

## 监控和日志

### 1. 日志查看

清理任务的日志会输出到 Celery Worker 的日志中：

```bash
# 查看 Celery Worker 日志
tail -f logs/celery-worker.log

# 或者如果使用 Docker
docker-compose logs -f celery-worker
```

### 2. 数据库监控

定期检查 `processing_tasks` 表的状态：

```sql
-- 查看任务状态分布
SELECT status, COUNT(*) as count
FROM processing_tasks
GROUP BY status;

-- 查看超时的运行任务
SELECT id, task_type, started_at, status
FROM processing_tasks
WHERE status = 'RUNNING'
  AND started_at < NOW() - INTERVAL 24 HOUR;

-- 查看长期等待的任务
SELECT id, task_type, created_at, status
FROM processing_tasks
WHERE status = 'PENDING'
  AND created_at < NOW() - INTERVAL 2 HOUR;
```

### 3. 统计信息

使用脚本查看详细统计：
```bash
python scripts/run_cleanup.py --stats-only
```

输出示例：
```
==================================================
Processing Tasks 当前统计信息
==================================================
总任务数: 15420

按状态统计:
  pending      :     12 (  0.1%)
  running      :      3 (  0.0%)
  success      :  14850 ( 96.3%)
  failure      :    500 (  3.2%)
  retry        :     55 (  0.4%)

按类型统计:
  download           :   5000 ( 32.4%)
  extract_audio      :   5000 ( 32.4%)
  generate_srt       :   5000 ( 32.4%)
  video_slice        :    300 (  1.9%)
  capcut_export      :    100 (  0.6%)
  jianying_export    :     20 (  0.1%)

最近24小时创建的任务: 150

需要关注的任务:
  超时运行中的任务 (>24小时): 2
  长期等待中的任务 (>2小时): 5
==================================================
```

## 配置说明

### 1. 清理参数配置

可以在脚本中调整以下参数：

- `running_timeout_hours`: 运行中任务超时时间（默认: 24小时）
- `pending_timeout_hours`: 等待中任务超时时间（默认: 2小时）
- `failure_retention_days`: 失败任务保留天数（默认: 7天）
- `success_retention_days`: 成功任务保留天数（默认: 30天）

### 2. Celery Beat 调度配置

在 `app/core/celery.py` 中可以调整定时任务执行时间：

```python
celery_app.conf.beat_schedule = {
    'cleanup-processing-tasks': {
        'task': 'cleanup_processing_tasks',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
    },
    'cleanup-processing-tasks-dry-run': {
        'task': 'cleanup_processing_tasks_dry_run',
        'schedule': crontab(hour=1, minute=0),  # 每天凌晨1点
    }
}
```

## 故障排除

### 1. 清理任务未执行

**症状**: 定时清理任务没有自动执行
**排查步骤**:
1. 检查 Celery Beat 是否正常运行
2. 检查 Celery Worker 是否正常运行
3. 检查数据库连接是否正常
4. 查看 Celery 日志中的错误信息

### 2. 任务清理失败

**症状**: 清理任务执行但实际未清理数据
**排查步骤**:
1. 检查数据库权限
2. 检查外键约束
3. 使用 `--dry-run` 模式查看具体任务状态
4. 检查清理逻辑是否符合预期

### 3. 性能问题

**症状**: 清理任务执行时间过长或影响系统性能
**优化建议**:
1. 调整 `batch_size` 参数
2. 在低峰期执行清理任务
3. 考虑分批处理大量数据
4. 确保数据库索引正确配置

## 最佳实践

1. **定期监控**: 定期检查任务统计和清理日志
2. **试运行验证**: 在生产环境执行前，先用试运行模式验证
3. **备份数据**: 在大规模清理前备份重要数据
4. **合理配置**: 根据业务需要调整保留时间和超时设置
5. **日志记录**: 保留清理操作的详细日志用于审计

## 相关文件

- `scripts/cleanup_processing_tasks.py`: 核心清理逻辑
- `scripts/run_cleanup.py`: 手动执行脚本
- `app/tasks/cleanup_tasks.py`: Celery 定时任务
- `app/core/celery.py`: Celery 配置和调度设置
- `app/models/processing_task.py`: 数据模型定义
- `app/core/constants.py`: 常量定义