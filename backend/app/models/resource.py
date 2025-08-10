from sqlalchemy import Column, Integer, String, DateTime, func, Float, Boolean, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# 多对多关系表：资源-标签
resource_tags = Table(
    'resource_tags_mapping',
    Base.metadata,
    Column('resource_id', Integer, ForeignKey('resources.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('resource_tags.id', ondelete='CASCADE'), primary_key=True)
)

class ResourceTag(Base):
    """资源标签模型"""
    __tablename__ = "resource_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    tag_type = Column(String(50), nullable=False, index=True)  # audio, video, image, general
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ResourceTag(id={self.id}, name='{self.name}', type='{self.tag_type}')>"

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)
    file_size = Column(Float, nullable=False)  # 文件大小（字节）
    mime_type = Column(String(100), nullable=False)
    file_type = Column(String(50), nullable=False, index=True)  # video, audio, image
    duration = Column(Float, nullable=True)  # 音频/视频时长（秒）
    width = Column(Integer, nullable=True)  # 图片/视频宽度
    height = Column(Integer, nullable=True)  # 图片/视频高度
    description = Column(String(1000), nullable=True)
    is_public = Column(Boolean, default=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    download_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # 关系
    tags = relationship("ResourceTag", secondary=resource_tags, back_populates="resources")
    
    def __repr__(self):
        return f"<Resource(id={self.id}, filename='{self.filename}', type='{self.file_type}')>"

class ResourceTagRelation(Base):
    """资源标签关系表（多对多）"""
    __tablename__ = "resource_tag_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey('resources.id', ondelete='CASCADE'), nullable=False)
    tag_id = Column(Integer, ForeignKey('resource_tags.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    __table_args__ = (
        {'extend_existing': True}
    )

# 为ResourceTag添加反向关系
ResourceTag.resources = relationship("Resource", secondary=resource_tags, back_populates="tags")