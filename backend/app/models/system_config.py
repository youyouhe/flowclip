from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, index=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    category = Column(String(100))  # 数据库配置, Redis配置, MinIO配置, 安全配置, 其他服务配置
    is_sensitive = Column(Boolean, default=False)  # 敏感配置项(如密码)需要特殊处理
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())