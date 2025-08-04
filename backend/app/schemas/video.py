from pydantic import BaseModel, ConfigDict, HttpUrl
from typing import Optional, List
from datetime import datetime

class VideoBase(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

class VideoCreate(VideoBase):
    project_id: int
    url: str

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class VideoResponse(VideoBase):
    id: int
    project_id: int
    filename: Optional[str] = None
    file_path: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    thumbnail_url: Optional[str] = None
    status: str
    download_progress: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    project_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class VideoDownloadRequest(BaseModel):
    url: str
    project_id: int

class VideoUploadRequest(BaseModel):
    title: str
    description: Optional[str] = None

class PaginatedVideoResponse(BaseModel):
    videos: List[VideoResponse]
    pagination: dict
    total: int