#!/usr/bin/env python3
"""
系统配置初始化脚本
将环境变量中的配置写入MySQL数据库
"""

import os
import sys
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_system_config(max_retries=5, retry_delay=2):
    """初始化系统配置"""
    # 从环境变量获取数据库连接信息
    mysql_host = os.environ.get('MYSQL_HOST', 'mysql')  # 默认使用docker-compose中的服务名
    mysql_port = os.environ.get('MYSQL_PORT', '3306')
    mysql_user = os.environ.get('MYSQL_USER', 'youtube_user')
    mysql_password = os.environ.get('MYSQL_PASSWORD', 'youtube_password')
    mysql_database = os.environ.get('MYSQL_DATABASE', 'youtube_slicer')
    
    # 构建数据库URL
    database_url = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
    
    logger.info(f"Connecting to database: {mysql_host}:{mysql_port}/{mysql_database}")
    
    for attempt in range(max_retries):
        try:
            # 创建数据库引擎和会话
            engine = create_engine(database_url, echo=False, pool_pre_ping=True, 
                                 connect_args={"connect_timeout": 10},
                                 pool_recycle=3600)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            # 测试数据库连接
            db.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            
            # 确保system_configs表存在
            from app.core.database import Base
            from app.models.system_config import SystemConfig
            Base.metadata.create_all(bind=engine)
            
            # 获取环境变量中的配置
            configs = {
                # 数据库配置
                "mysql_host": mysql_host,
                "mysql_port": mysql_port,
                "mysql_user": mysql_user,
                "mysql_password": mysql_password,
                "mysql_database": mysql_database,
                
                # Redis配置
                "redis_url": os.environ.get('REDIS_URL', 'redis://redis:6379'),
                
                # MinIO配置
                "minio_endpoint": os.environ.get('MINIO_ENDPOINT', 'minio:9000'),
                "minio_public_endpoint": os.environ.get('MINIO_PUBLIC_ENDPOINT', ''),
                "minio_access_key": os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
                "minio_secret_key": os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
                "minio_bucket_name": os.environ.get('MINIO_BUCKET_NAME', 'youtube-videos'),
                
                # 安全配置
                "secret_key": os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production'),
                
                # ASR配置
                "asr_service_url": os.environ.get('ASR_SERVICE_URL', ''),
                "asr_model_type": os.environ.get('ASR_MODEL_TYPE', 'whisper'),
                "asr_api_key": os.environ.get('ASR_API_KEY', ''),

                # LLM配置
                "openrouter_api_key": os.environ.get('OPENROUTER_API_KEY', ''),
                "llm_model_type": os.environ.get('LLM_MODEL_TYPE', 'google/gemini-2.5-flash'),
                "llm_base_url": os.environ.get('LLM_BASE_URL', 'openrouter.ai/api/v1'),
                "llm_temperature": os.environ.get('LLM_TEMPERATURE', '0.7'),
                "llm_max_tokens": os.environ.get('LLM_MAX_TOKENS', '4000'),
                "llm_system_prompt": os.environ.get('LLM_SYSTEM_PROMPT', ''),

                # CapCut和Jianying配置
                "capcut_api_url": os.environ.get('CAPCUT_API_URL', ''),
                "capcut_api_key": os.environ.get('CAPCUT_API_KEY', ''),
                "jianying_api_url": os.environ.get('JIANYING_API_URL', ''),
                "jianying_api_key": os.environ.get('JIANYING_API_KEY', ''),
                "jianying_draft_folder": os.environ.get('JIANYING_DRAFT_FOLDER', '剪映草稿'),

                # TUS ASR配置
                "tus_api_url": os.environ.get('TUS_API_URL', ''),
                "tus_upload_url": os.environ.get('TUS_UPLOAD_URL', ''),
                "tus_file_size_threshold_mb": os.environ.get('TUS_FILE_SIZE_THRESHOLD_MB', '10'),
                "tus_enable_routing": os.environ.get('TUS_ENABLE_ROUTING', 'true'),
                "tus_max_retries": os.environ.get('TUS_MAX_RETRIES', '3'),
                "tus_timeout_seconds": os.environ.get('TUS_TIMEOUT_SECONDS', '1500'),
                
                # Server配置
                "public_ip": os.environ.get('PUBLIC_IP', ''),
                "private_ip": os.environ.get('PRIVATE_IP', ''),
                "frontend_url": os.environ.get('FRONTEND_URL', ''),
                "api_url": os.environ.get('API_URL', ''),
            }
            
            # 将配置写入数据库
            updated_count = 0
            created_count = 0
            
            for key, value in configs.items():
                # 检查配置项是否已存在
                existing_config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                
                if existing_config:
                    # 更新现有配置
                    if existing_config.value != str(value):
                        existing_config.value = str(value)
                        logger.info(f"Updated config: {key} = {value}")
                        updated_count += 1
                    else:
                        logger.debug(f"Config unchanged: {key} = {value}")
                else:
                    # 创建新配置
                    new_config = SystemConfig(
                        key=key,
                        value=str(value),
                        category=get_config_category(key)
                    )
                    db.add(new_config)
                    logger.info(f"Created config: {key} = {value}")
                    created_count += 1
            
            # 提交更改
            db.commit()
            logger.info(f"System configuration initialized successfully: {created_count} created, {updated_count} updated")
            return True
            
        except OperationalError as e:
            logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                raise
        except SQLAlchemyError as e:
            logger.error(f"Database error during system configuration initialization: {e}")
            if 'db' in locals():
                db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to initialize system configuration: {e}")
            if 'db' in locals():
                db.rollback()
            raise
        finally:
            if 'db' in locals():
                db.close()
    
    return False

def get_config_category(key):
    """获取配置项的分类"""
    if key.startswith('mysql_'):
        return "数据库配置"
    elif key.startswith('redis_'):
        return "Redis配置"
    elif key.startswith('minio_'):
        return "MinIO配置"
    elif key.startswith('tus_'):
        return "TUS ASR配置"
    elif key in ['secret_key']:
        return "安全配置"
    elif key in ['public_ip', 'private_ip', 'frontend_url', 'api_url']:
        return "服务器配置"
    elif key.startswith('asr_') or key.startswith('openrouter_') or key.startswith('llm_') or key.startswith('capcut_') or key.startswith('jianying_'):
        return "其他服务配置"
    else:
        return "其他服务配置"

if __name__ == "__main__":
    try:
        success = init_system_config()
        if success:
            logger.info("System configuration initialization completed successfully")
        else:
            logger.error("System configuration initialization failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"System configuration initialization failed: {e}")
        sys.exit(1)