from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class LLMAnalysis(Base):
    """LLM分析结果模型"""
    __tablename__ = "llm_analyses"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    
    # 分析数据
    analysis_data = Column(JSON, nullable=False)  # 存储完整的JSON分析结果
    cover_title = Column(String(500), nullable=False)  # 主cover_title，用于分组管理
    
    # 状态
    status = Column(String(50), default="pending")  # pending, validated, applied, failed
    is_validated = Column(Boolean, default=False)  # 是否已验证
    is_applied = Column(Boolean, default=False)  # 是否已应用到切片
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    validated_at = Column(DateTime(timezone=True))  # 验证时间
    applied_at = Column(DateTime(timezone=True))  # 应用时间
    
    # 关联
    video = relationship("Video", back_populates="llm_analyses")

class VideoSlice(Base):
    """视频切片模型（基于LLM分析结果）"""
    __tablename__ = "video_slices"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    llm_analysis_id = Column(Integer, ForeignKey("llm_analyses.id"), nullable=True)
    
    # 基础信息
    cover_title = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    tags = Column(JSON)  # 标签数组
    
    # 时间信息
    start_time = Column(Float, nullable=False)  # 开始时间（秒）
    end_time = Column(Float, nullable=False)  # 结束时间（秒）
    duration = Column(Float)  # 持续时间（秒）
    
    # 文件信息
    original_filename = Column(String(500))  # 原始文件名
    sliced_filename = Column(String(500))  # 切片后文件名
    sliced_file_path = Column(String(1000))  # 切片文件在MinIO中的路径
    file_size = Column(Integer)  # 文件大小（字节）
    
    # 状态
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)  # 处理进度
    error_message = Column(Text)  # 错误信息
    
    # CapCut 导出状态
    capcut_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    capcut_task_id = Column(String(255), nullable=True)  # Celery任务ID
    capcut_draft_url = Column(Text, nullable=True)  # CapCut草稿文件URL
    capcut_error_message = Column(Text, nullable=True)  # CapCut导出错误信息
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))  # 处理完成时间
    
    # 关联
    video = relationship("Video", back_populates="video_slices")
    llm_analysis = relationship("LLMAnalysis")
    sub_slices = relationship("VideoSubSlice", back_populates="parent_slice", cascade="all, delete-orphan")

class VideoSubSlice(Base):
    """视频子切片模型"""
    __tablename__ = "video_sub_slices"

    id = Column(Integer, primary_key=True, index=True)
    slice_id = Column(Integer, ForeignKey("video_slices.id"), nullable=False)
    
    # 基础信息
    cover_title = Column(String(500), nullable=False)
    
    # 时间信息
    start_time = Column(Float, nullable=False)  # 开始时间（秒）
    end_time = Column(Float, nullable=False)  # 结束时间（秒）
    duration = Column(Float)  # 持续时间（秒）
    
    # 文件信息
    sliced_filename = Column(String(500))  # 切片后文件名
    sliced_file_path = Column(String(1000))  # 切片文件在MinIO中的路径
    file_size = Column(Integer)  # 文件大小（字节）
    
    # 状态
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)  # 处理进度
    error_message = Column(Text)  # 错误信息
    
    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))  # 处理完成时间
    
    # 关联
    parent_slice = relationship("VideoSlice", back_populates="sub_slices")