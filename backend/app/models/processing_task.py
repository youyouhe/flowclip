from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage

class ProcessingTask(Base):
    """处理任务模型，用于跟踪每个处理步骤的状态"""
    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    task_type = Column(String(50), nullable=False)  # ProcessingTaskType
    task_name = Column(String(200), nullable=False)  # 任务名称
    celery_task_id = Column(String(255), unique=True, index=True)  # Celery任务ID
    
    # 状态信息
    status = Column(String(50), default=ProcessingTaskStatus.PENDING)  # ProcessingTaskStatus
    progress = Column(Float, default=0.0)  # 0-100
    stage = Column(String(50), default=None)  # ProcessingStage
    message = Column(String(500), default="")  # 状态消息
    error_message = Column(Text, default="")  # 错误信息
    
    # 输入输出
    input_data = Column(JSON, default={})  # 输入参数
    output_data = Column(JSON, default={})  # 输出结果
    
    # 性能统计
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float, default=0.0)  # 处理耗时
    
    # 重试信息
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # 元数据
    task_metadata = Column(JSON, default={})  # 额外元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="processing_tasks")
    task_logs = relationship("ProcessingTaskLog", back_populates="task", cascade="all, delete-orphan")

    @property
    def is_completed(self):
        """检查任务是否已完成"""
        return self.status in [ProcessingTaskStatus.SUCCESS, ProcessingTaskStatus.FAILURE]
    
    @property
    def is_successful(self):
        """检查任务是否成功"""
        return self.status == ProcessingTaskStatus.SUCCESS
    
    @property
    def is_failed(self):
        """检查任务是否失败"""
        return self.status == ProcessingTaskStatus.FAILURE
    
    @property
    def stage_description(self):
        """获取阶段的描述"""
        from app.core.constants import PROCESSING_STAGE_DESCRIPTIONS
        return PROCESSING_STAGE_DESCRIPTIONS.get(self.stage, self.stage or "未知阶段")

class ProcessingTaskLog(Base):
    """处理任务日志模型，记录状态变化历史"""
    __tablename__ = "processing_task_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("processing_tasks.id"), nullable=False)
    
    # 状态变化
    old_status = Column(String(50))
    new_status = Column(String(50))
    message = Column(String(500))
    details = Column(JSON, default={})
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    task = relationship("ProcessingTask", back_populates="task_logs")

class ProcessingStatus(Base):
    """处理状态汇总模型，用于快速查询整体状态"""
    __tablename__ = "processing_status"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, unique=True)
    
    # 整体状态
    overall_status = Column(String(50), default=ProcessingTaskStatus.PENDING)
    overall_progress = Column(Float, default=0.0)
    current_stage = Column(String(50))
    
    # 各阶段状态
    download_status = Column(String(50), default=ProcessingTaskStatus.PENDING)
    download_progress = Column(Float, default=0.0)
    
    extract_audio_status = Column(String(50), default=ProcessingTaskStatus.PENDING)
    extract_audio_progress = Column(Float, default=0.0)
    
    split_audio_status = Column(String(50), default=ProcessingTaskStatus.PENDING)
    split_audio_progress = Column(Float, default=0.0)
    
    generate_srt_status = Column(String(50), default=ProcessingTaskStatus.PENDING)
    generate_srt_progress = Column(Float, default=0.0)
    
    # 错误信息
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    # 更新时间
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    video = relationship("Video")