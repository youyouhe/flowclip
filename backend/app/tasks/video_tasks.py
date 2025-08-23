"""视频处理任务模块 - 导入所有子任务"""

# 从子模块导入所有Celery任务
from .subtasks.simple_task import add
from .subtasks.download_task import download_video
from .subtasks.audio_task import extract_audio
from .subtasks.video_audio_task import extract_video_audio
from .subtasks.slice_audio_task import extract_slice_audio
from .subtasks.sub_slice_audio_task import extract_sub_slice_audio
from .subtasks.srt_task import generate_srt
from .subtasks.slice_task import process_video_slices
from .subtasks.capcut_task import export_slice_to_capcut
from .subtasks import task_utils

# 为了向后兼容，也可以在这里重新导出工具函数
run_async = task_utils.run_async
update_task_status = task_utils.update_task_status
_wait_for_task_sync = task_utils._wait_for_task_sync

__all__ = [
    'add',
    'download_video', 
    'extract_audio',
    'extract_video_audio',
    'extract_slice_audio',
    'extract_sub_slice_audio',
    'generate_srt',
    'process_video_slices',
    'export_slice_to_capcut',
    'run_async',
    'update_task_status',
    '_wait_for_task_sync'
]