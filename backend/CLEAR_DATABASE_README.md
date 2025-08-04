# 数据库清空工具使用说明

## 脚本文件

### 1. `clear_database.py` - 主要清空工具
- **功能**: 清空数据库和 MinIO 存储中的所有数据
- **位置**: `/backend/clear_database.py`
- **用法**: `python clear_database.py`

### 2. `backup_database.py` - 数据库备份工具  
- **功能**: 备份数据库中的重要配置和用户信息
- **位置**: `/backend/backup_database.py`
- **用法**: `python backup_database.py`

## 使用步骤

### 1. 备份数据（可选）
```bash
cd backend
python backup_database.py
```
这将创建一个 JSON 备份文件，包含用户和项目的基本信息。

### 2. 清空数据库和存储
```bash
cd backend
python clear_database.py
```

脚本会要求确认：
- 输入 `YES` 确认清空数据库
- 输入 `y` 或 `yes` 确认清空 MinIO 文件

### 3. 重新初始化系统
清空完成后，按以下步骤重新初始化：

```bash
# 重新创建测试用户
python create_test_user.py

# 运行数据库迁移
alembic upgrade head

# 重启后端服务
# 重启 Celery Worker
```

## 清空的内容

### 数据库表：
- `users` - 用户表
- `projects` - 项目表  
- `videos` - 视频表
- `slices` - 切片表
- `sub_slices` - 子切片表
- `llm_analyses` - LLM分析表
- `video_slices` - 视频切片表
- `video_sub_slices` - 视频子切片表
- `transcripts` - 字幕表
- `analysis_results` - 分析结果表
- `processing_tasks` - 处理任务表
- `processing_task_logs` - 处理任务日志表
- `processing_status` - 处理状态表
- `audio_tracks` - 音频轨道表

### MinIO 存储：
- 所有上传的视频文件
- 提取的音频文件
- 分割的音频段
- 生成的字幕文件 (.srt)
- 切片后的视频文件

## 注意事项

⚠️ **重要提醒**:
1. 此操作不可恢复，请确保已备份重要数据
2. 清空后需要重新创建用户和项目
3. 所有正在进行的处理任务会被中断
4. 前端可能需要刷新页面或重新登录

## 故障排除

### 常见问题：

1. **连接数据库失败**
   - 检查 MySQL 服务是否运行
   - 确认数据库连接配置正确

2. **连接 MinIO 失败**  
   - 检查 MinIO 服务是否运行
   - 确认 MinIO 连接配置正确

3. **权限错误**
   - 确保运行脚本的用户有足够的权限
   - 检查数据库和 MinIO 的访问权限

### 重置后的测试流程：

1. 访问前端并重新登录
2. 创建新项目
3. 下载 YouTube 视频进行测试
4. 测试完整的处理流程（下载→提取音频→生成字幕→LLM分析→切片）