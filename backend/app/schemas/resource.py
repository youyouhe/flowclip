from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ResourceTagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tag_type: str = Field(..., pattern="^(audio|video|image|general)$")

class ResourceTagCreate(ResourceTagBase):
    pass

class ResourceTagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tag_type: Optional[str] = Field(None, pattern="^(audio|video|image|general)$")
    is_active: Optional[bool] = None

class ResourceTag(ResourceTagBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ResourceBase(BaseModel):
    filename: str = Field(..., max_length=255)
    original_filename: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: bool = True

class ResourceCreate(ResourceBase):
    file_path: str
    file_size: float
    mime_type: str
    file_type: str = Field(..., pattern="^(video|audio|image)$")
    duration: Optional[float] = Field(None, ge=0)
    width: Optional[int] = Field(None, ge=0)
    height: Optional[int] = Field(None, ge=0)
    tag_ids: List[int] = []

class ResourceUpdate(BaseModel):
    filename: Optional[str] = Field(None, max_length=255)
    original_filename: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = None
    tag_ids: Optional[List[int]] = None

class Resource(ResourceBase):
    id: int
    file_path: str
    file_size: float
    mime_type: str
    file_type: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    download_count: int = 0
    view_count: int = 0
    created_by: int
    created_at: datetime
    updated_at: datetime
    tags: List[ResourceTag] = []
    
    class Config:
        from_attributes = True

class ResourceQuery(BaseModel):
    file_type: Optional[str] = Field(None, pattern="^(video|audio|image|all)$")
    tag_id: Optional[int] = None
    search: Optional[str] = None
    tags: Optional[str] = None  # 逗号分隔的标签名
    is_public: Optional[bool] = None
    created_by: Optional[int] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    
class ResourceSearchResult(BaseModel):
    resources: List[Resource]
    total: int
    page: int
    page_size: int
    total_pages: int