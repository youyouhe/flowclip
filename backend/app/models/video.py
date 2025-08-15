from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(500))
    description = Column(Text)
    url = Column(String(500))  # Original YouTube URL
    filename = Column(String(500))
    file_path = Column(String(1000))  # Path in MinIO
    duration = Column(Float)  # Duration in seconds
    file_size = Column(Integer)  # File size in bytes
    thumbnail_url = Column(String(1000))
    status = Column(String(50), default="pending")  # pending, downloading, downloaded, processing, completed, failed
    download_progress = Column(Float, default=0.0)  # 0-100
    
    # 处理状态管理
    processing_stage = Column(String(50), default=None)  # 当前处理阶段
    processing_progress = Column(Float, default=0.0)  # 整体处理进度 0-100
    processing_message = Column(String(500), default="")  # 处理状态消息
    processing_error = Column(Text, default="")  # 错误信息
    processing_started_at = Column(DateTime(timezone=True))  # 处理开始时间
    processing_completed_at = Column(DateTime(timezone=True))  # 处理完成时间
    processing_metadata = Column(JSON, default={})  # 处理过程的元数据
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="videos")
    slices = relationship("Slice", back_populates="video", cascade="all, delete-orphan")
    audio_tracks = relationship("AudioTrack", back_populates="video", cascade="all, delete-orphan")
    transcripts = relationship("Transcript", back_populates="video", cascade="all, delete-orphan")
    processing_tasks = relationship("ProcessingTask", back_populates="video", cascade="all, delete-orphan")
    processing_status = relationship("ProcessingStatus", back_populates="video", uselist=False, cascade="all, delete-orphan")
    llm_analyses = relationship("LLMAnalysis", back_populates="video", cascade="all, delete-orphan")
    video_slices = relationship("VideoSlice", back_populates="video", cascade="all, delete-orphan")