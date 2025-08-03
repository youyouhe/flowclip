from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    audio_track_id = Column(Integer, ForeignKey("audio_tracks.id"), nullable=False)
    
    # Content
    content = Column(Text)  # Full transcript text
    segments = Column(JSON)  # Array of segments with start/end times and text
    language = Column(String(10))  # Language code (e.g., 'en', 'zh')
    confidence = Column(Float)  # ASR confidence score
    
    # File info
    file_path = Column(String(1000))  # SRT file path in MinIO
    
    # Processing info
    model = Column(String(100))  # ASR model used
    processing_time = Column(Float)  # Processing time in seconds
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="transcripts")
    audio_track = relationship("AudioTrack", back_populates="transcripts")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    transcript_id = Column(Integer, ForeignKey("transcripts.id"), nullable=False)
    
    # Analysis type
    analysis_type = Column(String(50))  # 'content_summary', 'slice_recommendation', etc.
    
    # Results
    content_summary = Column(Text)
    key_points = Column(JSON)  # Array of key points
    slice_recommendations = Column(JSON)  # Array of recommended slices
    tags = Column(JSON)  # Array of suggested tags
    
    # LLM info
    model = Column(String(100))  # LLM model used
    prompt = Column(Text)  # Prompt used
    processing_time = Column(Float)
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video")
    transcript = relationship("Transcript")