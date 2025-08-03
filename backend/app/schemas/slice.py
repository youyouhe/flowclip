from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime

class SliceBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: float
    end_time: float
    tags: Optional[List[str]] = None

class SliceCreate(SliceBase):
    video_id: int

class SliceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None

class SliceResponse(SliceBase):
    id: int
    video_id: int
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    content_summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    status: str
    uploaded_to_youtube: bool
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SubSliceBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: float
    end_time: float

class SubSliceCreate(SubSliceBase):
    slice_id: int

class SubSliceResponse(SubSliceBase):
    id: int
    slice_id: int
    video_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SliceWithSubSlices(SliceResponse):
    sub_slices: List[SubSliceResponse] = []