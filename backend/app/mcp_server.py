#!/usr/bin/env python3
"""
MCP Server implementation for Flowclip API
This module converts the FastAPI application into an MCP server with optimized tool naming
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Enable info logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_mcp_operation_ids(app: FastAPI):
    """
    为所有路由设置简短的operation_id，确保MCP工具名称不超过63个字符
    """
    
    # 定义operation_id映射表 - 基于用户筛选的14个核心端点
    operation_id_map = {
        # ASR服务状态
        ('GET', '/api/v1/asr/status'): 'asr_status',
        
        # 认证相关
        ('POST', '/api/v1/auth/login'): 'login',
        
        # CapCut集成
        ('GET', '/api/v1/capcut/status'): 'capcut_status',
        ('POST', '/api/v1/capcut/export-slice/{slice_id}'): 'export_slice',
        
        # LLM聊天
        ('POST', '/api/v1/llm/chat'): 'llm_chat',
        
        # 处理任务日志
        ('GET', '/api/v1/processing/logs/task/{task_id}'): 'get_task_logs',
        
        # 项目管理
        ('GET', '/api/v1/projects/'): 'list_projects',
        ('POST', '/api/v1/projects/'): 'create_project',
        ('GET', '/api/v1/projects/{project_id}/videos'): 'get_project_videos',
        
        # 系统服务状态
        ('GET', '/api/v1/system/system-config/service-status/{service_name}'): 'service_status',
        
        # 视频处理核心功能
        ('POST', '/api/v1/processing/{video_id}/extract-audio'): 'extract_audio',
        ('POST', '/api/v1/processing/{video_id}/generate-srt'): 'generate_srt',
        
        # 视频切片处理
        ('POST', '/api/v1/video-slice/process-slices'): 'process_slices',
        ('POST', '/api/v1/video-slice/validate-slice-data'): 'validate_slices',
    }
    
    # 遍历所有路由并设置operation_id
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            for method in route.methods:
                if method != 'HEAD':  # 跳过HEAD方法
                    key = (method, route.path)
                    if key in operation_id_map:
                        # 设置operation_id
                        if hasattr(route, 'operation_id'):
                            route.operation_id = operation_id_map[key]
                        elif hasattr(route, 'endpoint') and hasattr(route.endpoint, '__name__'):
                            # 某些情况下可能需要通过其他方式设置
                            logger.debug(f"Setting operation_id for {method} {route.path}: {operation_id_map[key]}")
    
    logger.info(f"已为 {len(operation_id_map)} 个路由设置operation_id")

# 定义核心标签，用于过滤MCP工具 - 基于用户筛选
CORE_TAGS = [
    "asr",           # ASR服务状态
    "auth",          # 认证相关  
    "capcut",        # CapCut集成
    "llm",           # LLM聊天
    "processing",    # 视频处理和日志
    "projects",      # 项目管理
    "system",        # 系统服务状态
    "video-slice",   # 视频切片
]

def create_mcp_server():
    """创建MCP服务器"""
    try:
        # Import the FastAPI app
        from app.main import app
        
        # 设置所有路由的operation_id
        setup_mcp_operation_ids(app)
        
        # 创建MCP服务器，只包含核心功能标签
        mcp = FastApiMCP(
            app,
            name="Flowclip API",
            description="Flowclip视频处理平台 - 提供视频下载、处理、分析和切片功能",
            include_tags=CORE_TAGS,
            describe_all_responses=False,  # 简化响应描述
            describe_full_response_schema=False,  # 简化响应架构
        )
        
        return mcp
        
    except Exception as e:
        logger.error(f"创建MCP服务器失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 如果无法导入完整应用，创建一个简单的测试应用
        logger.info("使用简化测试应用创建MCP服务器")
        
        test_app = FastAPI(
            title="Flowclip API",
            description="Flowclip视频处理平台",
            version="1.0.0"
        )
        
        @test_app.post("/api/v1/auth/login", tags=["auth"], operation_id="login")
        async def login():
            return {"message": "Please use the full application"}
            
        @test_app.get("/health", operation_id="health_check") 
        async def health():
            return {"status": "MCP server running in test mode"}
        
        return FastApiMCP(
            test_app,
            name="Flowclip API (Test Mode)",
            description="Flowclip测试模式",
            include_tags=["auth"],
        )

# 创建MCP服务器实例  
mcp = create_mcp_server()

# 导出app以便外部导入
app = mcp.fastapi if hasattr(mcp, 'fastapi') else None

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(mcp.fastapi, host="0.0.0.0", port=8002)