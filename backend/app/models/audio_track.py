from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    
    # File info
    filename = Column(String(500))
    file_path = Column(String(1000))  # Path in MinIO
    duration = Column(Float)
    file_size = Column(Integer)
    format = Column(String(50))
    
    # Status
    status = Column(String(50), default="pending")  # pending, extracting, extracted, failed
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    video = relationship("Video", back_populates="audio_tracks")
    transcripts = relationship("Transcript", back_populates="audio_track", cascade="all, delete-orphan")