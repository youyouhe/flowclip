from fastapi import APIRouter, HTTPException
import requests
import logging
from app.core.config import settings

router = APIRouter(
    tags=["asr"],
    responses={404: {"description": "未找到"}},
)

# 创建logger
logger = logging.getLogger(__name__)

@router.get("/status",
    summary="检查ASR服务状态",
    description="通过向ASR服务发送健康检查请求来验证服务是否在线。该端点会尝试连接到配置的ASR服务URL并检查其健康状态。",
    responses={
        200: {
            "description": "成功返回ASR服务状态",
            "content": {
                "application/json": {
                    "example": {
                        "status": "online"
                    }
                }
            }
        },
        503: {"description": "服务不可用"}
    }
, operation_id="asr_status")
async def get_asr_status():
    """
    获取ASR服务状态
    
    通过向ASR服务发送健康检查请求来验证服务是否在线。
    该端点会尝试连接到配置的ASR服务URL并检查其健康状态。
    
    Returns:
        dict: 包含服务状态的字典
            - status (str): 服务状态，"online"表示在线，"offline"表示离线
            
    Example:
        {
            "status": "online"
        }
    """
    try:
        # 测试ASR服务端点来判断服务是否在线
        logger.info(f"ASR服务URL: {settings.asr_service_url}")
        response = requests.get(f"{settings.asr_service_url}/health", timeout=5)
        logger.info(f"ASR服务健康检查响应状态码: {response.status_code}")
        return {"status": "online" if response.status_code == 200 else "offline"}
    except Exception as e:
        logger.error(f"ASR服务状态检查失败: {str(e)}")
        return {"status": "offline"}