from fastapi import APIRouter, HTTPException
import requests
import logging
from app.core.config import settings

router = APIRouter(tags=["asr"])

# 创建logger
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_asr_status():
    """获取ASR服务状态"""
    try:
        # 测试ASR服务端点来判断服务是否在线
        logger.info(f"ASR服务URL: {settings.asr_service_url}")
        response = requests.get(f"{settings.asr_service_url}/health", timeout=5)
        logger.info(f"ASR服务健康检查响应状态码: {response.status_code}")
        return {"status": "online" if response.status_code == 200 else "offline"}
    except Exception as e:
        logger.error(f"ASR服务状态检查失败: {str(e)}")
        return {"status": "offline"}