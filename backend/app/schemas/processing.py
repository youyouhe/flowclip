from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.constants import ProcessingTaskType, ProcessingTaskStatus, ProcessingStage

class ProcessingTaskResponse(BaseModel):
    """处理任务响应模型"""
    id: int
    video_id: int
    task_type: str
    task_name: str
    celery_task_id: Optional[str]
    status: str
    progress: float
    stage: Optional[str]
    message: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: float
    retry_count: int
    max_retries: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    
    class Config:
        from_attributes = True

class ProcessingStatusResponse(BaseModel):
    """处理状态响应模型"""
    video_id: int
    overall_status: str
    overall_progress: float
    current_stage: Optional[str]
    
    download: Dict[str, Any]
    extract_audio: Dict[str, Any]
    split_audio: Dict[str, Any]
    generate_srt: Dict[str, Any]
    
    error_count: int
    last_error: Optional[str]
    
    class Config:
        from_attributes = True

class ProcessingTaskLogResponse(BaseModel):
    """处理任务日志响应模型"""
    id: int
    task_id: int
    old_status: Optional[str]
    new_status: str
    message: str
    details: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TaskStatusResponse(BaseModel):
    """任务状态响应模型"""
    task_id: str
    status: str
    progress: float
    stage: Optional[str]
    stage_description: Optional[str]
    message: Optional[str]
    error: Optional[str]
    result: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True

class VideoProcessingStatusResponse(BaseModel):
    """视频处理状态响应模型"""
    video_id: int
    title: str
    status: str
    processing_stage: Optional[str]
    processing_progress: float
    processing_message: Optional[str]
    processing_error: Optional[str]
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    
    tasks: List[ProcessingTaskResponse]
    overall_status: Dict[str, Any]
    
    class Config:
        from_attributes = True