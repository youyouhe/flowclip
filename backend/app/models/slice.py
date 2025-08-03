from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Slice(Base):
    __tablename__ = "slices"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    
    # Metadata
    title = Column(String(500), nullable=False)
    description = Column(Text)
    tags = Column(JSON)  # Array of tags
    
    # Timing
    start_time = Column(Float, nullable=False)  # Start time in seconds
    end_time = Column(Float, nullable=False)    # End time in seconds
    duration = Column(Float)  # Calculated duration
    
    # Content
    thumbnail_url = Column(String(1000))
    video_url = Column(String(1000))  # Path in MinIO
    
    # Analysis results
    content_summary = Column(Text)
    key_points = Column(JSON)  # Array of key points
    hashtags = Column(JSON)    # Array of hashtags
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    uploaded_to_youtube = Column(Boolean, default=False)
    youtube_video_id = Column(String(100))
    youtube_url = Column(String(1000))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="slices")
    sub_slices = relationship("SubSlice", back_populates="parent_slice", cascade="all, delete-orphan")

class SubSlice(Base):
    __tablename__ = "sub_slices"

    id = Column(Integer, primary_key=True, index=True)
    slice_id = Column(Integer, ForeignKey("slices.id"), nullable=False)
    
    # Metadata
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Timing (relative to parent slice)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    
    # Content
    video_url = Column(String(1000))
    
    # Status
    status = Column(String(50), default="pending")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    parent_slice = relationship("Slice", back_populates="sub_slices")