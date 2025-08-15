# 任务模块说明

为了更好地组织代码和提高可维护性，我们将原来庞大的`video_tasks.py`文件拆分成了多个子模块。

## 模块结构

```
tasks/
├── video_tasks.py              # 主模块，导入所有子任务
└── subtasks/                   # 子任务模块目录
    ├── __init__.py             # 包初始化文件
    ├── simple_task.py          # 简单任务（如add）
    ├── download_task.py        # 视频下载任务
    ├── audio_task.py           # 音频提取任务
    ├── srt_task.py             # 字幕生成任务
    ├── slice_task.py           # 视频切片处理任务
    ├── capcut_task.py          # CapCut导出任务
    └── task_utils.py           # 共享工具函数
```

## 各模块功能说明

### simple_task.py
- `add(x, y)`: 简单的加法任务，用于测试Celery连接

### download_task.py
- `download_video()`: 从YouTube下载视频并上传到MinIO

### audio_task.py
- `extract_audio()`: 从视频中提取音频

### srt_task.py
- `generate_srt()`: 生成SRT字幕文件

### slice_task.py
- `process_video_slices()`: 处理视频切片任务

### capcut_task.py
- `export_slice_to_capcut()`: 导出切片到CapCut

### task_utils.py
- `run_async()`: 运行异步代码的辅助函数
- `update_task_status()`: 更新任务状态的通用函数
- `_wait_for_task_sync()`: 同步等待任务完成

## 使用方式

### 导入任务
```python
# 导入特定任务
from app.tasks.video_tasks import download_video, extract_audio

# 或者导入所有任务
from app.tasks.video_tasks import *
```

### 调用任务
```python
# 调用任务与之前相同
task = download_video.delay(video_url, project_id, user_id)
```

## 优势

1. **模块化**: 每个任务独立在一个文件中，便于维护和理解
2. **可读性**: 代码结构更清晰，减少了单个文件的复杂度
3. **可维护性**: 修改特定任务时只需关注对应的文件
4. **向后兼容**: 通过`video_tasks.py`保持了原有的导入方式