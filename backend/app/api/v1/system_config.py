from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from app.core.database import get_db, get_sync_db_context
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
import aiohttp
import json
import asyncio

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
        
        # 如果更新了MinIO相关配置，重载MinIO客户端
        minio_updated = any(config.key.startswith('minio_') for config in configs)
        if minio_updated:
            try:
                from app.services.minio_client import minio_service
                minio_service.reload_config()
                logger.info("MinIO客户端配置已重载")
            except Exception as e:
                logger.error(f"重载MinIO客户端配置失败: {e}")
        
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
            
            # 确保URL格式正确
            if not asr_service_url.startswith(('http://', 'https://')):
                asr_service_url = f"http://{asr_service_url}"
            
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
                
        elif service_name.lower() == "llm":
            # LLM服务健康检查
            openrouter_api_key = get_config("openrouter_api_key", settings.openrouter_api_key)
            llm_base_url = get_config("llm_base_url", settings.llm_base_url)
            
            logger.info(f"LLM配置: base_url={llm_base_url}, checking API key")
            
            if not openrouter_api_key or openrouter_api_key == "your-key-here":
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message="OpenRouter API密钥未设置或为占位符"
                )
            
            if not llm_base_url:
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message="LLM基础URL未设置"
                )
            
            try:
                # 测试LLM服务连接
                from app.services.llm_service import llm_service
                
                # 动态更新LLM服务的配置
                with get_sync_db_context() as db:
                    SystemConfigService.update_settings_from_db_sync(db)
                
                # 重新初始化LLM服务以使用最新的配置
                models = await llm_service.get_available_models(filter_provider="google")
                
                if models:
                    return ServiceStatus(
                        service=service_name,
                        status="online",
                        message=f"LLM服务正常，基础URL: {llm_base_url}，可使用 {len(models)} 个模型"
                    )
                else:
                    return ServiceStatus(
                        service=service_name,
                        status="offline",
                        message="无法获取模型列表，请检查API密钥、基础URL和网络连接"
                    )
            except Exception as e:
                logger.error(f"LLM连接失败: {str(e)}")
                return ServiceStatus(
                    service=service_name,
                    status="offline",
                    message=f"LLM连接失败: {str(e)}"
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


class AsrTestResponse(BaseModel):
    """ASR测试响应模型"""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None


@router.post("/test-asr", response_model=AsrTestResponse)
async def test_asr_service(
    file: UploadFile = File(...),
    model_type: str = Form("whisper"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """测试ASR服务"""
    try:
        logger.info(f"开始测试ASR服务，模型类型: {model_type}")
        
        # 获取数据库中的配置
        db_configs = await SystemConfigService.get_all_configs(db)
        
        # 获取ASR服务配置
        asr_service_url = db_configs.get("asr_service_url", settings.asr_service_url)
        asr_model_type = db_configs.get("asr_model_type", getattr(settings, "asr_model_type", "whisper"))
        
        logger.info(f"ASR配置: url={asr_service_url}, model_type={asr_model_type}")
        
        # 根据模型类型确定服务URL和端点
        if model_type == "whisper":
            # 确保URL指向whisper服务(5001端口)
            if ":5002" in asr_service_url:
                asr_service_url = asr_service_url.replace(":5002", ":5001")
            elif ":5001" not in asr_service_url:
                asr_service_url = "http://192.168.8.107:5001"
            
            # 确保URL格式正确
            if not asr_service_url.startswith(('http://', 'https://')):
                asr_service_url = f"http://{asr_service_url}"
            
            base_url = asr_service_url.rstrip('/')
            endpoint = f"{base_url}/inference" if not base_url.endswith('/inference') else base_url
            params = {
                "response_format": "srt",
                "language": "auto"
            }
        else:  # sense模型
            # 确保URL指向sense服务(5002端口)
            if ":5001" in asr_service_url:
                asr_service_url = asr_service_url.replace(":5001", ":5002")
            elif ":5002" not in asr_service_url:
                asr_service_url = "http://192.168.8.107:5002"
            
            # 确保URL格式正确
            if not asr_service_url.startswith(('http://', 'https://')):
                asr_service_url = f"http://{asr_service_url}"
            
            base_url = asr_service_url.rstrip('/')
            endpoint = f"{base_url}/asr" if not base_url.endswith('/asr') else base_url
            params = {
                "lang": "zh"
            }
        
        logger.info(f"ASR请求配置: endpoint={endpoint}, params={params}")
        
        # 读取上传的文件内容
        file_content = await file.read()
        logger.info(f"文件大小: {len(file_content)} bytes")
        
        # 使用aiohttp发送请求
        async with aiohttp.ClientSession() as session:
            # 准备请求数据
            data = aiohttp.FormData()
            data.add_field('file', file_content, filename=file.filename, content_type=file.content_type)
            
            # 添加参数
            for key, value in params.items():
                data.add_field(key, str(value))
            
            try:
                async with session.post(endpoint, data=data, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    logger.info(f"ASR服务响应状态: {response.status}")
                    
                    if response.status == 200:
                        # 处理响应
                        if model_type == "whisper":
                            # Whisper模型返回JSON格式
                            response_data = await response.json()
                            if response_data.get("code") == 0:
                                result_text = response_data.get("data", "")
                                return AsrTestResponse(success=True, result=result_text)
                            else:
                                error_msg = response_data.get("msg", "ASR服务返回错误")
                                return AsrTestResponse(success=False, error=error_msg)
                        else:
                            # Sense模型直接返回文本
                            result_text = await response.text()
                            return AsrTestResponse(success=True, result=result_text)
                    else:
                        error_text = await response.text()
                        logger.error(f"ASR服务错误响应: {response.status}, {error_text}")
                        return AsrTestResponse(success=False, error=f"ASR服务返回错误状态码: {response.status}")
                        
            except asyncio.TimeoutError:
                logger.error("ASR服务请求超时")
                return AsrTestResponse(success=False, error="ASR服务请求超时")
            except Exception as e:
                logger.error(f"ASR服务请求失败: {str(e)}")
                return AsrTestResponse(success=False, error=f"ASR服务请求失败: {str(e)}")
                
    except Exception as e:
        logger.error(f"ASR测试失败: {str(e)}")
        return AsrTestResponse(success=False, error=f"ASR测试失败: {str(e)}")