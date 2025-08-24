from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.system_config import SystemConfig
from app.services.system_config_service import SystemConfigService
from app.core.config import settings
from pydantic import BaseModel
from sqlalchemy import select
import aiomysql
import redis
import requests
import logging

router = APIRouter()

# 创建logger
logger = logging.getLogger(__name__)

class ConfigItem(BaseModel):
    key: str
    value: str
    description: str = ""
    category: str = ""

class ConfigResponse(BaseModel):
    key: str
    value: str
    description: str = ""
    category: str = ""
    default: str = ""

@router.get("/system-config", response_model=List[ConfigResponse])
async def get_system_configs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取所有系统配置项"""
    # 获取数据库中的配置
    db_configs = await SystemConfigService.get_all_configs(db)
    
    # 获取所有可配置项
    configurable_items = SystemConfigService.get_configurable_items()
    
    # 合并数据库配置和默认配置
    result = []
    for item in configurable_items:
        key = item["key"]
        value = db_configs.get(key, item["default"])
        result.append(ConfigResponse(
            key=key,
            value=value,
            description=item.get("description", ""),
            category=item["category"],
            default=item["default"]
        ))
    
    return result

@router.post("/system-config", response_model=ConfigItem)
async def update_system_config(
    config: ConfigItem,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """更新系统配置项"""
    try:
        # 保存到数据库
        db_config = await SystemConfigService.set_config(
            db, 
            config.key, 
            config.value, 
            config.description,
            config.category
        )
        
        # 更新当前settings
        await SystemConfigService.update_settings_from_db(db)
        
        return ConfigItem(
            key=db_config.key,
            value=db_config.value,
            description=db_config.description,
            category=db_config.category
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/system-config/batch")
async def update_system_configs(
    configs: List[ConfigItem],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """批量更新系统配置项"""
    try:
        updated_configs = []
        for config in configs:
            # 保存到数据库
            db_config = await SystemConfigService.set_config(
                db, 
                config.key, 
                config.value, 
                config.description,
                config.category
            )
            updated_configs.append(ConfigItem(
                key=db_config.key,
                value=db_config.value,
                description=db_config.description,
                category=db_config.category
            ))
        
        # 更新当前settings
        await SystemConfigService.update_settings_from_db(db)
        
        return updated_configs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class ServiceStatus(BaseModel):
    service: str
    status: str  # "online", "offline", "checking"
    message: str = ""

@router.post("/system-config/reload-configs")
async def reload_system_configs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """触发所有Celery worker重新加载系统配置"""
    try:
        # 更新当前settings
        await SystemConfigService.update_settings_from_db(db)
        
        # 触发所有Celery worker重新加载配置
        from app.core.celery import reload_system_configs
        # 在所有worker上执行任务
        result = reload_system_configs.apply_async()
        
        return {
            "status": "success", 
            "message": "系统配置重新加载任务已发送到所有Celery worker",
            "task_id": result.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/system-config/service-status/{service_name}", response_model=ServiceStatus)
async def check_service_status(
    service_name: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """检查外部服务状态"""
    try:
        # 获取数据库中的配置
        db_configs = await SystemConfigService.get_all_configs(db)
        
        # 获取服务配置
        service_configs = {}
        for key, value in db_configs.items():
            if service_name.lower() in key.lower() or (
                service_name.lower() == "mysql" and key.startswith("mysql_")
            ) or (
                service_name.lower() == "minio" and key.startswith("minio_")
            ) or (
                service_name.lower() == "redis" and key.startswith("redis_")
            ):
                service_configs[key] = value
        
        # 如果数据库中没有配置，则使用默认配置
        def get_config(key, default):
            return service_configs.get(key, getattr(settings, key, default))
        
        if service_name.lower() == "mysql":
            # MySQL健康检查
            host = get_config("mysql_host", settings.mysql_host)
            port = int(get_config("mysql_port", str(settings.mysql_port)))
            user = get_config("mysql_user", settings.mysql_user)
            password = get_config("mysql_password", settings.mysql_password)
            database = get_config("mysql_database", settings.mysql_database)
            
            logger.info(f"MySQL配置: host={host}, port={port}, user={user}, database={database}")
            
            try:
                connection = await aiomysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    db=database,
                    connect_timeout=5
                )
                connection.close()
                return ServiceStatus(
                    service=service_name,
                    status="online",
                    message="MySQL服务正常"
                )
            except Exception as e:
                logger.error(f"MySQL连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"MySQL连接失败: {str(e)}"
                )
                
        elif service_name.lower() == "redis":
            # Redis健康检查
            redis_url = get_config("redis_url", settings.redis_url)
            
            logger.info(f"Redis配置: url={redis_url}")
            
            try:
                r = redis.from_url(redis_url, socket_timeout=5)
                r.ping()
                return ServiceStatus(
                    service=service_name,
                    status="online",
                    message="Redis服务正常"
                )
            except Exception as e:
                logger.error(f"Redis连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"Redis连接失败: {str(e)}"
                )
                
        elif service_name.lower() == "minio":
            # MinIO健康检查
            minio_endpoint = get_config("minio_endpoint", settings.minio_endpoint)
            minio_access_key = get_config("minio_access_key", settings.minio_access_key)
            minio_secret_key = get_config("minio_secret_key", settings.minio_secret_key)
            
            # 构建健康检查URL
            protocol = "https" if settings.minio_secure else "http"
            health_url = f"{protocol}://{minio_endpoint}/minio/health/live"
            
            logger.info(f"MinIO配置: endpoint={minio_endpoint}, health_url={health_url}")
            
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    return ServiceStatus(
                        service=service_name,
                        status="online",
                        message="MinIO服务正常"
                    )
                else:
                    return ServiceStatus(
                        service=service_name,
                        status="offline",
                        message=f"MinIO健康检查失败，状态码: {response.status_code}"
                    )
            except Exception as e:
                logger.error(f"MinIO连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"MinIO连接失败: {str(e)}"
                )
                
        elif service_name.lower() == "asr":
            # ASR服务健康检查
            asr_service_url = get_config("asr_service_url", settings.asr_service_url)
            base_url = asr_service_url.rstrip('/')
            health_check_url = f"{base_url}/health"
            
            logger.info(f"ASR配置: checking url={health_check_url}")
            
            try:
                # 尝试访问/health端点
                response = requests.get(health_check_url, timeout=5)
                if response.status_code == 200 and response.json().get("status") == "healthy":
                    return ServiceStatus(
                        service=service_name,
                        status="online",
                        message="ASR服务正常"
                    )
                else:
                    return ServiceStatus(
                        service=service_name,
                        status="offline",
                        message=f"ASR健康检查失败，状态码: {response.status_code}"
                    )
            except Exception as e:
                logger.error(f"ASR连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"ASR连接失败: {str(e)}"
                )
                
        elif service_name.lower() == "capcut":
            # CapCut服务健康检查
            capcut_api_url = get_config("capcut_api_url", settings.capcut_api_url)
            
            logger.info(f"CapCut配置: url={capcut_api_url}")
            
            try:
                response = requests.post(f"{capcut_api_url}/create_draft", 
                                       json={"width": 1080, "height": 1920}, 
                                       timeout=5)
                if response.status_code == 200:
                    return ServiceStatus(
                        service=service_name,
                        status="online",
                        message="CapCut服务正常"
                    )
                else:
                    return ServiceStatus(
                        service=service_name,
                        status="offline",
                        message=f"CapCut健康检查失败，状态码: {response.status_code}"
                    )
            except Exception as e:
                logger.error(f"CapCut连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"CapCut连接失败: {str(e)}"
                )
                
        else:
            raise HTTPException(status_code=400, detail=f"不支持的服务: {service_name}")
            
    except Exception as e:
        logger.error(f"服务健康检查失败: {str(e)}")
        return ServiceStatus(
            service=service_name,
            status="offline",
            message=f"健康检查失败: {str(e)}"
        )