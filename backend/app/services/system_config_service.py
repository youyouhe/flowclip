from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.models.system_config import SystemConfig
from app.core.config import settings

class SystemConfigService:
    """系统配置服务类，用于管理数据库中的配置项"""
    
    # 配置项映射关系：key为数据库中的key，value为settings中的属性名
    CONFIG_MAPPING = {
        # 数据库配置
        "mysql_host": "mysql_host",
        "mysql_port": "mysql_port",
        "mysql_user": "mysql_user",
        "mysql_password": "mysql_password",
        "mysql_database": "mysql_database",
        "mysql_root_password": "mysql_root_password",
        
        # Redis配置
        "redis_url": "redis_url",
        
        # MinIO配置
        "minio_endpoint": "minio_endpoint",
        "minio_public_endpoint": "minio_public_endpoint",
        "minio_access_key": "minio_access_key",
        "minio_secret_key": "minio_secret_key",
        "minio_bucket_name": "minio_bucket_name",
        
        # 安全配置
        "secret_key": "secret_key",
        
        # 其他服务配置
        "asr_service_url": "asr_service_url",
        "openrouter_api_key": "openrouter_api_key",
        "capcut_api_url": "capcut_api_url",
        "capcut_draft_folder": "capcut_draft_folder",
    }
    
    @staticmethod
    async def get_all_configs(db: Session) -> Dict[str, str]:
        """获取所有配置项"""
        # 对于异步会话，使用select语句
        if hasattr(db, 'execute'):
            from sqlalchemy import select
            stmt = select(SystemConfig)
            result = await db.execute(stmt)
            configs = result.scalars().all()
        else:
            # 对于同步会话，使用query方法
            configs = db.query(SystemConfig).all()
        return {config.key: config.value for config in configs}

    @staticmethod
    def get_all_configs_sync(db: Session) -> Dict[str, str]:
        """获取所有配置项的同步版本"""
        configs = db.query(SystemConfig).all()
        return {config.key: config.value for config in configs}
    
    
    @staticmethod
    async def get_config(db: Session, key: str) -> Optional[str]:
        """获取单个配置项"""
        # 对于异步会话，使用select语句
        if hasattr(db, 'execute'):
            from sqlalchemy import select
            stmt = select(SystemConfig).where(SystemConfig.key == key)
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()
        else:
            # 对于同步会话，使用query方法
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        return config.value if config else None
    
    @staticmethod
    async def set_config(db: Session, key: str, value: str, description: str = "", category: str = "") -> SystemConfig:
        """设置配置项"""
        # 对于异步会话，使用select语句
        if hasattr(db, 'execute'):
            from sqlalchemy import select
            stmt = select(SystemConfig).where(SystemConfig.key == key)
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()
            if config:
                config.value = value
                config.description = description
                config.category = category
            else:
                config = SystemConfig(
                    key=key,
                    value=value,
                    description=description,
                    category=category
                )
                db.add(config)
            await db.commit()
            await db.refresh(config)
        else:
            # 对于同步会话，使用query方法
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if config:
                config.value = value
                config.description = description
                config.category = category
            else:
                config = SystemConfig(
                    key=key,
                    value=value,
                    description=description,
                    category=category
                )
                db.add(config)
            db.commit()
            db.refresh(config)
        return config
    
    @staticmethod
    async def update_settings_from_db(db: Session):
        """从数据库更新settings配置"""
        db_configs = await SystemConfigService.get_all_configs(db)
        
        # 更新数据库URL
        if "mysql_host" in db_configs and "mysql_port" in db_configs:
            host = db_configs.get("mysql_host", settings.mysql_host)
            port = db_configs.get("mysql_port", str(settings.mysql_port))
            user = db_configs.get("mysql_user", settings.mysql_user)
            password = db_configs.get("mysql_password", settings.mysql_password)
            database = db_configs.get("mysql_database", settings.mysql_database)
            settings.database_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        
        # 更新其他配置项
        for db_key, settings_attr in SystemConfigService.CONFIG_MAPPING.items():
            if db_key in db_configs:
                setattr(settings, settings_attr, db_configs[db_key])
    
    @staticmethod
    def update_settings_from_db_sync(db: Session):
        """从数据库更新settings配置的同步版本"""
        db_configs = SystemConfigService.get_all_configs_sync(db)
        print(f"DEBUG: 从数据库获取的配置: {db_configs}")
        
        # 更新数据库URL
        if "mysql_host" in db_configs and "mysql_port" in db_configs:
            host = db_configs.get("mysql_host", settings.mysql_host)
            port = db_configs.get("mysql_port", str(settings.mysql_port))
            user = db_configs.get("mysql_user", settings.mysql_user)
            password = db_configs.get("mysql_password", settings.mysql_password)
            database = db_configs.get("mysql_database", settings.mysql_database)
            settings.database_url = f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        
        # 更新其他配置项
        for db_key, settings_attr in SystemConfigService.CONFIG_MAPPING.items():
            if db_key in db_configs:
                print(f"DEBUG: 更新配置项 {db_key} 从 '{getattr(settings, settings_attr, None)}' 到 '{db_configs[db_key]}'")
                setattr(settings, settings_attr, db_configs[db_key])
        
        print(f"DEBUG: 更新后settings.minio_public_endpoint: {settings.minio_public_endpoint}")
    
    @staticmethod
    def get_configurable_items() -> List[Dict[str, str]]:
        """获取所有可配置的项目信息"""
        return [
            # 数据库配置
            {"key": "mysql_host", "label": "MySQL主机", "category": "数据库配置", "default": settings.mysql_host},
            {"key": "mysql_port", "label": "MySQL端口", "category": "数据库配置", "default": str(settings.mysql_port)},
            {"key": "mysql_user", "label": "MySQL用户名", "category": "数据库配置", "default": settings.mysql_user},
            {"key": "mysql_password", "label": "MySQL密码", "category": "数据库配置", "default": settings.mysql_password, "sensitive": True},
            {"key": "mysql_database", "label": "MySQL数据库名", "category": "数据库配置", "default": settings.mysql_database},
            {"key": "mysql_root_password", "label": "MySQL根密码", "category": "数据库配置", "default": "rootpassword", "sensitive": True},
            
            # Redis配置
            {"key": "redis_url", "label": "Redis URL", "category": "Redis配置", "default": settings.redis_url},
            
            # MinIO配置
            {"key": "minio_endpoint", "label": "MinIO端点", "category": "MinIO配置", "default": settings.minio_endpoint},
            {"key": "minio_public_endpoint", "label": "MinIO公共端点", "category": "MinIO配置", "default": settings.minio_public_endpoint or ""},
            {"key": "minio_access_key", "label": "MinIO访问密钥", "category": "MinIO配置", "default": settings.minio_access_key},
            {"key": "minio_secret_key", "label": "MinIO秘密密钥", "category": "MinIO配置", "default": settings.minio_secret_key, "sensitive": True},
            {"key": "minio_bucket_name", "label": "MinIO存储桶名", "category": "MinIO配置", "default": settings.minio_bucket_name},
            
            # 安全配置
            {"key": "secret_key", "label": "密钥", "category": "安全配置", "default": settings.secret_key, "sensitive": True},
            
            # 其他服务配置
            {"key": "asr_service_url", "label": "ASR服务URL", "category": "其他服务配置", "default": settings.asr_service_url},
            {"key": "openrouter_api_key", "label": "OpenRouter API密钥", "category": "其他服务配置", "default": settings.openrouter_api_key or "", "sensitive": True},
            {"key": "capcut_api_url", "label": "CapCut API URL", "category": "其他服务配置", "default": settings.capcut_api_url},
            {"key": "capcut_draft_folder", "label": "CapCut草稿文件夹路径", "category": "其他服务配置", "default": settings.capcut_draft_folder or "", "description": "CapCut草稿文件夹的完整路径"},
        ]