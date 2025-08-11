from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class LLMAnalysisBase(BaseModel):
    analysis_data: List[Dict[str, Any]]
    cover_title: str
    status: str = "pending"
    is_validated: bool = False
    is_applied: bool = False

class LLMAnalysisCreate(LLMAnalysisBase):
    video_id: int

class LLMAnalysisUpdate(BaseModel):
    status: Optional[str] = None
    is_validated: Optional[bool] = None
    is_applied: Optional[bool] = None

class LLMAnalysis(LLMAnalysisBase):
    id: int
    video_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class VideoSliceBase(BaseModel):
    cover_title: str
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    start_time: float
    end_time: float
    duration: Optional[float] = None
    status: str = "pending"
    progress: float = 0.0

class VideoSliceCreate(VideoSliceBase):
    video_id: int
    llm_analysis_id: Optional[int] = None

class VideoSliceUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
    sliced_filename: Optional[str] = None
    sliced_file_path: Optional[str] = None
    file_size: Optional[int] = None

class VideoSlice(VideoSliceBase):
    id: int
    video_id: int
    llm_analysis_id: Optional[int] = None
    original_filename: Optional[str] = None
    sliced_filename: Optional[str] = None
    sliced_file_path: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    
    # CapCut导出相关字段
    capcut_status: Optional[str] = None
    capcut_task_id: Optional[str] = None
    capcut_draft_url: Optional[str] = None
    capcut_error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class VideoSubSliceBase(BaseModel):
    cover_title: str
    start_time: float
    end_time: float
    duration: Optional[float] = None
    status: str = "pending"
    progress: float = 0.0

class VideoSubSliceCreate(VideoSubSliceBase):
    slice_id: int

class VideoSubSliceUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
    sliced_filename: Optional[str] = None
    sliced_file_path: Optional[str] = None
    file_size: Optional[int] = None

class VideoSubSlice(VideoSubSliceBase):
    id: int
    slice_id: int
    sliced_filename: Optional[str] = None
    sliced_file_path: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class SliceValidationRequest(BaseModel):
    """切片验证请求"""
    video_id: int
    analysis_data: List[Dict[str, Any]]
    cover_title: str

class SliceValidationResponse(BaseModel):
    """切片验证响应"""
    is_valid: bool
    message: str
    analysis_id: Optional[int] = None
    errors: Optional[List[str]] = None

class SliceProcessRequest(BaseModel):
    """切片处理请求"""
    analysis_id: int
    slice_items: List[Dict[str, Any]]  # 需要处理的切片项

class SliceProcessResponse(BaseModel):
    """切片处理响应"""
    message: str
    task_id: str
    total_slices: int
    processed_slices: int = 0