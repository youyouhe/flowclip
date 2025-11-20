from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.services.minio_client import minio_service
from app.services.llm_service import llm_service
from app.core.config import settings
import os
import tempfile
import logging

# 设置日志
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["llm"],
    responses={404: {"description": "未找到"}},
)

class ChatRequest(BaseModel):
    """聊天请求模型"""
    message: str
    video_id: Optional[int] = None
    system_prompt: Optional[str] = None
    use_srt_context: bool = False

class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    usage: Optional[Dict[str, Any]] = None
    model: str
    video_context_used: bool = False

class SystemPromptRequest(BaseModel):
    """系统提示词请求模型"""
    system_prompt: str

class SystemPromptResponse(BaseModel):
    """系统提示词响应模型"""
    message: str
    current_prompt: str

@router.get("/test-long-request", operation_id="test_long_request")
async def test_long_request(request: Request):
    """
    测试长时间请求 - 用于诊断网络连接问题
    模拟LLM请求的处理时间，但不实际调用LLM服务
    """
    import asyncio
    import time
    
    start_time = time.time()
    
    # 记录请求来源信息
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    referer = request.headers.get("referer", "No referer")
    
    logger.info(f"🚀 开始长时间请求测试 - {start_time}")
    logger.info(f"🔍 请求来源: IP={client_ip}, UA={user_agent}, Referer={referer}")
    
    # 模拟LLM处理时间（60秒）
    logger.info("⏳ 开始60秒睡眠...")
    await asyncio.sleep(60)
    logger.info("✅ 60秒睡眠完成")
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    logger.info(f"🎉 测试完成 - 总耗时: {processing_time:.2f}秒")
    
    return {
        "success": True,
        "message": "长时间请求测试完成",
        "processing_time_seconds": round(processing_time, 2),
        "start_time": start_time,
        "end_time": end_time
    }

@router.post("/chat", response_model=ChatResponse,
    summary="与LLM对话",
    description="与大型语言模型进行对话。支持使用视频内容作为上下文进行分析，也可以进行简单的对话。",
    responses={
        200: {
            "description": "成功返回LLM响应",
            "content": {
                "application/json": {
                    "example": {
                        "response": "这是LLM的回复内容",
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                        "model": "google/gemini-2.5-flash",
                        "video_context_used": True
                    }
                }
            }
        },
        404: {"description": "视频未找到"},
        500: {"description": "服务器内部错误"}
    }
, operation_id="llm_chat")
async def chat_with_llm(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    与LLM对话
    
    与大型语言模型进行对话。支持使用视频内容作为上下文进行分析，也可以进行简单的对话。
    如果请求中包含video_id且use_srt_context为True，则会使用视频的SRT字幕内容作为上下文。
    
    Args:
        request (ChatRequest): 聊天请求参数
            - message (str): 用户的聊天消息
            - video_id (Optional[int]): 视频ID，用于视频内容分析
            - system_prompt (Optional[str]): 系统提示词
            - use_srt_context (bool): 是否使用SRT字幕内容作为上下文
        current_user (User): 当前认证用户
        db (AsyncSession): 数据库会话依赖
        
    Returns:
        ChatResponse: LLM响应结果
            - response (str): LLM的回复内容
            - usage (Optional[Dict[str, Any]]): 令牌使用情况
            - model (str): 使用的模型名称
            - video_context_used (bool): 是否使用了视频上下文
            
    Raises:
        HTTPException: 当视频未找到或LLM对话失败时抛出异常
    """
    
    logger.info(f"收到LLM聊天请求 - 用户: {current_user.id}, 消息: {request.message[:50]}...")
    logger.info(f"请求参数 - video_id: {request.video_id}, use_srt_context: {request.use_srt_context}")
    
    try:
        srt_content = None
        video_context_used = False
        
        # 如果需要使用SRT上下文且提供了video_id
        if request.use_srt_context and request.video_id:
            logger.info(f"尝试获取SRT文件 - video_id: {request.video_id}")
            
            # 验证视频属于当前用户
            stmt = select(Video).join(Project).where(
                Video.id == request.video_id,
                Project.user_id == current_user.id
            )
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                logger.warning(f"视频未找到 - video_id: {request.video_id}, user_id: {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )
            
            logger.info(f"找到视频: {video.title}")
            
            # 构建SRT文件对象名称
            srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
            logger.info(f"检查SRT文件: {srt_object_name}")
            
            # 检查SRT文件是否存在
            file_exists = await minio_service.file_exists(srt_object_name)
            logger.info(f"SRT文件存在: {file_exists}")
            
            if file_exists:
                # 下载SRT文件内容
                try:
                    logger.info("开始下载SRT文件...")
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as temp_file:
                        # 获取文件内容
                        response = minio_service.internal_client.get_object(
                            settings.minio_bucket_name,
                            srt_object_name
                        )
                        
                        # 读取SRT内容
                        srt_content = response.read().decode('utf-8')
                        temp_file.write(srt_content)
                        temp_file_path = temp_file.name
                    
                    # 清理临时文件
                    os.unlink(temp_file_path)
                    video_context_used = True
                    logger.info(f"SRT文件读取成功，内容长度: {len(srt_content)}")
                    
                except Exception as e:
                    logger.error(f"读取SRT文件失败: {e}")
                    srt_content = None
        else:
            logger.info("不使用SRT上下文或未提供video_id")
        
        # 根据是否有SRT内容选择不同的处理方式
        if srt_content and video_context_used:
            logger.info("使用视频内容分析模式")
            # 使用视频内容分析
            llm_response = await llm_service.analyze_video_content(
                srt_content=srt_content,
                user_question=request.message,
                system_prompt=request.system_prompt
            )
        else:
            logger.info("使用简单对话模式")
            # 简单对话
            llm_response = await llm_service.simple_chat(
                message=request.message,
                system_prompt=request.system_prompt
            )
        
        logger.info(f"LLM响应: {llm_response}")
        
        # 提取回复内容
        response_text = ""
        usage_info = None

        if 'choices' in llm_response and len(llm_response['choices']) > 0:
            choice = llm_response['choices'][0]
            if 'message' in choice and 'content' in choice['message']:
                # 优先使用解析后的JSON内容，本地修改
                if 'parsed_content' in llm_response:
                    logger.info("使用解析后的JSON内容")
                    if isinstance(llm_response['parsed_content'], str):
                        response_text = llm_response['parsed_content']
                    else:
                        # 如果是JSON对象，格式化为字符串
                        import json
                        response_text = json.dumps(llm_response['parsed_content'], ensure_ascii=False, indent=2)
                else:
                    # 如果没有解析后的内容，使用原始content
                    response_text = choice['message']['content']
        
        if 'usage' in llm_response:
            usage_info = llm_response['usage']
        
        logger.info(f"聊天请求成功 - 响应长度: {len(response_text)}")
        
        return ChatResponse(
            response=response_text,
            usage=usage_info,
            model=llm_response.get('model', 'unknown'),
            video_context_used=video_context_used
        )
        
    except Exception as e:
        logger.error(f"LLM聊天请求失败: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM对话失败: {str(e)}"
        )

@router.post("/system-prompt", response_model=SystemPromptResponse,
    summary="更新系统提示词",
    description="更新LLM对话的系统提示词。该设置仅在当前会话中生效。",
    responses={
        200: {
            "description": "成功更新系统提示词",
            "content": {
                "application/json": {
                    "example": {
                        "message": "系统提示词已更新，将在下次对话中生效",
                        "current_prompt": "你是一个AI助手..."
                    }
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
, operation_id="update_system_prompt")
async def update_system_prompt(
    request: SystemPromptRequest,
    current_user: User = Depends(get_current_user)
):
    """
    更新系统提示词（仅用于当前会话）
    
    更新LLM对话的系统提示词。该设置仅在当前会话中生效。
    
    Args:
        request (SystemPromptRequest): 系统提示词请求参数
            - system_prompt (str): 新的系统提示词
        current_user (User): 当前认证用户
        
    Returns:
        SystemPromptResponse: 更新结果
            - message (str): 操作结果消息
            - current_prompt (str): 当前设置的提示词（截取前100个字符）
            
    Raises:
        HTTPException: 当更新失败时抛出异常
    """
    
    try:
        # 这里只是返回成功消息，实际的系统提示词在每个请求中传递
        # 因为环境变量不能动态更新
        return SystemPromptResponse(
            message="系统提示词已更新，将在下次对话中生效",
            current_prompt=request.system_prompt[:100] + "..." if len(request.system_prompt) > 100 else request.system_prompt
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新系统提示词失败: {str(e)}"
        )

@router.get("/system-prompt",
    summary="获取当前系统提示词",
    description="获取当前设置的LLM系统提示词。",
    responses={
        200: {
            "description": "成功返回当前系统提示词",
            "content": {
                "application/json": {
                    "example": {
                        "system_prompt": "你是一个AI助手..."
                    }
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
, operation_id="get_system_prompt")
async def get_current_system_prompt():
    """
    获取当前系统提示词
    
    获取当前设置的LLM系统提示词。
    
    Returns:
        dict: 包含当前系统提示词的字典
            - system_prompt (str): 当前的系统提示词
            
    Raises:
        HTTPException: 当获取失败时抛出异常
    """
    
    try:
        from app.services.llm_service import llm_service
        # 获取当前配置而不是直接访问不存在的属性
        config = llm_service._get_current_config()
        return {
            "system_prompt": config['default_system_prompt']
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统提示词失败: {str(e)}"
        )

@router.get("/models",
    summary="获取可用的模型列表",
    description="获取LLM服务中可用的模型列表。该接口会从OpenRouter API动态获取Google模型列表，如果获取失败则返回默认模型。",
    responses={
        200: {
            "description": "成功返回模型列表",
            "content": {
                "application/json": {
                    "example": {
                        "models": [
                            {
                                "id": "google/gemini-2.5-flash",
                                "name": "Gemini 2.5 Flash",
                                "description": "默认使用的Gemini模型"
                            }
                        ]
                    }
                }
            }
        },
        500: {"description": "服务器内部错误"}
    }
, operation_id="get_models")
async def get_available_models():
    """
    获取可用的模型列表
    
    获取LLM服务中可用的模型列表。该接口会从OpenRouter API动态获取Google模型列表，
    如果获取失败则返回默认模型。
    
    Returns:
        dict: 包含模型列表的字典
            - models (List[Dict]): 模型信息列表
                - id (str): 模型ID
                - name (str): 模型名称
                - description (str): 模型描述
                
    Raises:
        HTTPException: 当获取模型列表失败时抛出异常
    """
    
    try:
        # 从OpenRouter API动态获取Google模型列表
        openrouter_models = await llm_service.get_available_models(filter_provider="google")
        
        # 如果无法获取模型列表，返回默认模型
        if not openrouter_models:
            logger.warning("无法从OpenRouter获取模型列表，返回默认模型")
            return {
                "models": [
                    {
                        "id": "google/gemini-2.5-flash",
                        "name": "Gemini 2.5 Flash",
                        "description": "默认使用的Gemini模型"
                    }
                ]
            }
        
        # 转换模型格式
        models = []
        for model in openrouter_models:
            models.append({
                "id": model.get("id"),
                "name": model.get("name", model.get("id")),
                "description": model.get("description", "")
            })
        
        return {
            "models": models
        }
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {type(e).__name__}: {str(e)}")
        # 出错时返回默认模型列表
        return {
            "models": [
                {
                    "id": "google/gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "description": "默认使用的Gemini模型"
                }
            ]
        }