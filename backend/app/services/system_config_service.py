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
        "asr_model_type": "asr_model_type",
        "openrouter_api_key": "openrouter_api_key",
        "capcut_api_url": "capcut_api_url",
        "capcut_api_key": "capcut_api_key",
        "capcut_draft_folder": "capcut_draft_folder",

        # TUS配置
        "tus_api_url": "tus_api_url",
        "tus_upload_url": "tus_upload_url",
        "tus_callback_port": "tus_callback_port",
        "tus_callback_host": "tus_callback_host",
        "tus_file_size_threshold_mb": "tus_file_size_threshold_mb",
        "tus_enable_routing": "tus_enable_routing",
        "tus_max_retries": "tus_max_retries",
        "tus_timeout_seconds": "tus_timeout_seconds",

        # LLM配置
        "llm_base_url": "llm_base_url",
        "llm_model_type": "llm_model_type",
        "llm_system_prompt": "llm_system_prompt",
        "llm_temperature": "llm_temperature",
        "llm_max_tokens": "llm_max_tokens",
    }

    # 类型转换映射：定义配置项的数据类型
    TYPE_MAPPING = {
        # 整数类型
        "mysql_port": int,
        "tus_callback_port": int,
        "tus_file_size_threshold_mb": int,
        "tus_max_retries": int,
        "tus_timeout_seconds": int,
        "llm_temperature": float,
        "llm_max_tokens": int,

        # 布尔类型
        "tus_enable_routing": lambda x: str(x).lower() in ('true', '1', 'yes', 'on'),
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

        # 如果更新的是TUS阈值配置，则自动更新全局阈值
        if key == "tus_file_size_threshold_mb":
            from app.services.file_size_detector import update_global_threshold
            try:
                threshold_mb = int(value)
                update_global_threshold(threshold_mb)
            except (ValueError, TypeError):
                pass  # 如果转换失败，保持原有配置

        return config

    @staticmethod
    def set_config_sync(db: Session, key: str, value: str, description: str = "", category: str = "") -> SystemConfig:
        """设置配置项的同步版本"""
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

        # 如果更新的是TUS阈值配置，则自动更新全局阈值
        if key == "tus_file_size_threshold_mb":
            from app.services.file_size_detector import update_global_threshold
            try:
                threshold_mb = int(value)
                update_global_threshold(threshold_mb)
            except (ValueError, TypeError):
                pass  # 如果转换失败，保持原有配置

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
            if db_key in db_configs and db_configs[db_key].strip():
                # 获取原始值
                raw_value = db_configs[db_key]
                converted_value = raw_value

                # 进行类型转换
                if db_key in SystemConfigService.TYPE_MAPPING:
                    try:
                        converter = SystemConfigService.TYPE_MAPPING[db_key]
                        converted_value = converter(raw_value)
                        #print(f"DEBUG: 类型转换 {db_key}: '{raw_value}' -> {converted_value} ({type(converted_value).__name__})")
                    except Exception as conv_error:
                        print(f"WARNING: 配置项 {db_key} 类型转换失败: {raw_value} -> {conv_error}，使用原值")

                setattr(settings, settings_attr, converted_value)
    
    @staticmethod
    def update_settings_from_db_sync(db: Session):
        """从数据库更新settings配置的同步版本"""
        db_configs = SystemConfigService.get_all_configs_sync(db)
        # print(f"DEBUG: 从数据库获取的配置: {db_configs}")
        
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
            if db_key in db_configs and db_configs[db_key].strip():
                # 获取原始值
                raw_value = db_configs[db_key]
                converted_value = raw_value

                # 进行类型转换
                if db_key in SystemConfigService.TYPE_MAPPING:
                    try:
                        converter = SystemConfigService.TYPE_MAPPING[db_key]
                        converted_value = converter(raw_value)
                        #print(f"DEBUG: 类型转换 {db_key}: '{raw_value}' -> {converted_value} ({type(converted_value).__name__})")
                    except Exception as conv_error:
                        print(f"WARNING: 配置项 {db_key} 类型转换失败: {raw_value} -> {conv_error}，使用原值")

                setattr(settings, settings_attr, converted_value)
        
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
            {"key": "asr_model_type", "label": "ASR模型类型", "category": "其他服务配置", "default": getattr(settings, 'asr_model_type', 'whisper'), "description": "选择ASR模型类型：whisper 或 sense"},
            {"key": "capcut_api_url", "label": "CapCut API URL", "category": "其他服务配置", "default": settings.capcut_api_url},
            {"key": "capcut_api_key", "label": "CapCut API密钥", "category": "其他服务配置", "default": settings.capcut_api_key or "", "sensitive": True, "description": "CapCut服务的API密钥"},
            {"key": "capcut_draft_folder", "label": "CapCut草稿文件夹路径", "category": "其他服务配置", "default": settings.capcut_draft_folder or "", "description": "CapCut草稿文件夹的完整路径"},

            # TUS配置
            {"key": "tus_api_url", "label": "TUS API URL", "category": "其他服务配置", "default": settings.tus_api_url, "description": "TUS ASR API服务器地址"},
            {"key": "tus_upload_url", "label": "TUS上传URL", "category": "其他服务配置", "default": settings.tus_upload_url, "description": "TUS上传服务器地址"},
            {"key": "tus_callback_port", "label": "TUS回调端口", "category": "其他服务配置", "default": str(settings.tus_callback_port), "description": "TUS回调监听端口"},
            {"key": "tus_callback_host", "label": "TUS回调主机", "category": "其他服务配置", "default": settings.tus_callback_host, "description": "TUS回调主机IP (auto=自动检测)"},
            {"key": "tus_file_size_threshold_mb", "label": "TUS文件大小阈值(MB)", "category": "其他服务配置", "default": str(settings.tus_file_size_threshold_mb), "description": "TUS协议使用的文件大小阈值(MB)"},
            {"key": "tus_enable_routing", "label": "启用TUS路由", "category": "其他服务配置", "default": str(settings.tus_enable_routing).lower(), "description": "是否启用TUS自动路由功能"},
            {"key": "tus_max_retries", "label": "TUS最大重试次数", "category": "其他服务配置", "default": str(settings.tus_max_retries), "description": "TUS操作的最大重试次数"},
            {"key": "tus_timeout_seconds", "label": "TUS超时时间(秒)", "category": "其他服务配置", "default": str(settings.tus_timeout_seconds), "description": "TUS操作的超时时间(秒) - 应设置为小于Celery任务硬时间限制(1800秒)"},
            
            # LLM配置
            {"key": "openrouter_api_key", "label": "OpenRouter API密钥", "category": "LLM配置", "default": settings.openrouter_api_key or "", "sensitive": True},
            {"key": "llm_base_url", "label": "LLM服务基础URL", "category": "LLM配置", "default": getattr(settings, 'llm_base_url', 'https://openrouter.ai/api/v1'), "description": "LLM服务的基础URL，例如OpenRouter API的URL"},
            {"key": "llm_model_type", "label": "LLM模型类型", "category": "LLM配置", "default": getattr(settings, 'llm_model_type', 'google/gemini-2.5-flash'), "description": "选择LLM模型类型：google/gemini-2.5-flash, google/gemini-2.5-flash-lite, openai/gpt-4, openai/gpt-3.5-turbo"},
            {"key": "llm_system_prompt", "label": "LLM系统提示词", "category": "LLM配置", "default": settings.llm_system_prompt, "description": "LLM系统提示词，用于指导AI如何处理视频内容"},
            {"key": "llm_temperature", "label": "LLM温度参数", "category": "LLM配置", "default": str(getattr(settings, 'llm_temperature', '0.7')), "description": "控制LLM输出随机性的参数，范围0-1，值越大越随机"},
            {"key": "llm_max_tokens", "label": "LLM最大令牌数", "category": "LLM配置", "default": str(getattr(settings, 'llm_max_tokens', '65535')), "description": "LLM生成的最大令牌数，影响回答长度"},
        ]