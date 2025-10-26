"""系统常量定义"""

from enum import Enum

class VideoStatus(str, Enum):
    """视频处理状态枚举"""
    PENDING = "pending"              # 等待处理
    DOWNLOADING = "downloading"      # 正在下载
    DOWNLOADED = "downloaded"        # 下载完成
    PROCESSING = "processing"        # 处理中
    COMPLETED = "completed"          # 处理完成
    FAILED = "failed"                # 处理失败
    CANCELLED = "cancelled"          # 已取消

class AudioStatus(str, Enum):
    """音频处理状态枚举"""
    PENDING = "pending"              # 等待处理
    EXTRACTING = "extracting"        # 正在提取
    EXTRACTED = "extracted"          # 提取完成
    PROCESSING = "processing"        # 处理中
    COMPLETED = "completed"          # 处理完成
    FAILED = "failed"                # 处理失败

class TranscriptStatus(str, Enum):
    """字幕生成状态枚举"""
    PENDING = "pending"              # 等待处理
    PROCESSING = "processing"        # 处理中
    COMPLETED = "completed"          # 处理完成
    FAILED = "failed"                # 处理失败

class ProcessingTaskType(str, Enum):
    """处理任务类型枚举"""
    DOWNLOAD = "download"            # 视频下载
    EXTRACT_AUDIO = "extract_audio"  # 提取音频
    GENERATE_SRT = "generate_srt"    # 生成字幕
    VIDEO_SLICE = "video_slice"      # 视频切片
    CAPCUT_EXPORT = "capcut_export"  # CapCut导出
    JIANYING_EXPORT = "jianying_export"  # Jianying导出
    PROCESS_COMPLETE = "process_complete"  # 完整处理流程

class ProcessingTaskStatus(str, Enum):
    """处理任务状态枚举"""
    PENDING = "pending"              # 等待执行
    RUNNING = "running"              # 运行中
    SUCCESS = "success"              # 执行成功
    FAILURE = "failure"              # 执行失败
    RETRY = "retry"                  # 重试中
    REVOKED = "revoked"              # 已撤销

class ProcessingStage(str, Enum):
    """处理阶段枚举"""
    DOWNLOAD = "download"            # 下载阶段
    EXTRACT_AUDIO = "extract_audio"  # 提取音频阶段
    GENERATE_SRT = "generate_srt"    # 生成字幕阶段
    ANALYZE_CONTENT = "analyze_content"  # 内容分析阶段
    SLICE_VIDEO = "slice_video"      # 视频切片阶段
    CAPCUT_EXPORT = "capcut_export"  # CapCut导出阶段
    JIANYING_EXPORT = "jianying_export"  # Jianying导出阶段
    COMPLETED = "completed"          # 完成

# 状态映射
CELERY_TO_DB_STATUS_MAP = {
    "PENDING": ProcessingTaskStatus.PENDING,
    "STARTED": ProcessingTaskStatus.RUNNING,
    "SUCCESS": ProcessingTaskStatus.SUCCESS,
    "FAILURE": ProcessingTaskStatus.FAILURE,
    "RETRY": ProcessingTaskStatus.RETRY,
    "REVOKED": ProcessingTaskStatus.REVOKED,
}

# 处理阶段的中文描述
PROCESSING_STAGE_DESCRIPTIONS = {
    ProcessingStage.DOWNLOAD: "下载视频",
    ProcessingStage.EXTRACT_AUDIO: "提取音频",
    ProcessingStage.GENERATE_SRT: "生成字幕",
    ProcessingStage.ANALYZE_CONTENT: "内容分析",
    ProcessingStage.SLICE_VIDEO: "视频切片",
    ProcessingStage.CAPCUT_EXPORT: "CapCut导出",
    ProcessingStage.JIANYING_EXPORT: "剪映导出",
    ProcessingStage.COMPLETED: "处理完成"
}

# 状态对应的颜色
STATUS_COLORS = {
    VideoStatus.PENDING: "#8c8c8c",
    VideoStatus.DOWNLOADING: "#1890ff",
    VideoStatus.DOWNLOADED: "#52c41a",
    VideoStatus.PROCESSING: "#faad14",
    VideoStatus.COMPLETED: "#52c41a",
    VideoStatus.FAILED: "#ff4d4f",
    VideoStatus.CANCELLED: "#8c8c8c",
    ProcessingTaskStatus.PENDING: "#8c8c8c",
    ProcessingTaskStatus.RUNNING: "#1890ff",
    ProcessingTaskStatus.SUCCESS: "#52c41a",
    ProcessingTaskStatus.FAILURE: "#ff4d4f",
    ProcessingTaskStatus.RETRY: "#faad14",
    ProcessingTaskStatus.REVOKED: "#8c8c8c",
}

# 系统限制常量
MAX_VIDEO_DURATION_MINUTES = 150  # 最大允许视频时长（分钟）
MAX_VIDEO_DURATION_SECONDS = MAX_VIDEO_DURATION_MINUTES * 60  # 转换为秒数