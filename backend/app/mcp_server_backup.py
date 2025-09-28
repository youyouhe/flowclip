#!/usr/bin/env python3
"""
MCP Server implementation for Flowclip API
This module converts the FastAPI application into an MCP server with optimized tool naming
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from jose import jwt
import datetime
from pydantic import BaseModel

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

# 延迟导入应用以避免循环依赖
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

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(mcp.fastapi, host="0.0.0.0", port=8002)
def get_api_info() -> dict:
    """获取Flowclip API的基本信息"""
    return {
        "name": "Flowclip API", 
        "version": "1.0.0",
        "description": "视频处理和切片的综合API",
        "selected_features": [
            "用户登录认证",
            "ASR服务状态查询",
            "CapCut集成和切片导出",
            "LLM智能对话",
            "项目管理",
            "视频音频提取",
            "字幕生成",
            "视频切片处理",
            "任务日志查询",
            "系统服务状态监控"
        ],
        "total_endpoints": 14,
        "status": "优化版本 - 仅包含核心功能"
    }

@mcp.tool(name="get_available_tools")
def get_available_tools() -> list:
    """获取当前MCP服务器中可用的工具列表"""
    return [
        {"tool": "login", "description": "用户登录认证", "method": "POST"},
        {"tool": "asr_status", "description": "ASR服务状态检查", "method": "GET"},
        {"tool": "capcut_status", "description": "CapCut服务状态", "method": "GET"},
        {"tool": "export_slice", "description": "导出视频切片到CapCut", "method": "POST"},
        {"tool": "llm_chat", "description": "LLM智能对话", "method": "POST"},
        {"tool": "list_projects", "description": "获取项目列表", "method": "GET"},
        {"tool": "create_project", "description": "创建新项目", "method": "POST"},
        {"tool": "get_project_videos", "description": "获取项目中的视频", "method": "GET"},
        {"tool": "extract_audio", "description": "从视频提取音频", "method": "POST"},
        {"tool": "generate_srt", "description": "生成字幕文件", "method": "POST"},
        {"tool": "process_slices", "description": "处理视频切片", "method": "POST"},
        {"tool": "validate_slices", "description": "验证切片数据", "method": "POST"},
        {"tool": "get_task_logs", "description": "获取任务日志", "method": "GET"},
        {"tool": "service_status", "description": "检查系统服务状态", "method": "GET"}
    ]

@mcp.tool(name="get_workflow_guide")
def get_workflow_guide() -> dict:
    """获取基于筛选端点的工作流程指南"""
    return {
        "authentication": {
            "step": 1,
            "tool": "login",
            "description": "首先使用login工具进行用户认证"
        },
        "project_setup": {
            "step": 2,
            "tools": ["list_projects", "create_project"],
            "description": "管理项目 - 查看现有项目或创建新项目"
        },
        "video_processing": {
            "step": 3,
            "tools": ["extract_audio", "generate_srt"],
            "description": "处理视频 - 提取音频并生成字幕"
        },
        "video_slicing": {
            "step": 4,
            "tools": ["validate_slices", "process_slices"],
            "description": "视频切片 - 验证数据并处理切片"
        },
        "integration": {
            "step": 5,
            "tools": ["export_slice", "llm_chat"],
            "description": "集成功能 - 导出到CapCut或使用LLM对话"
        },
        "monitoring": {
            "step": 6,
            "tools": ["get_task_logs", "asr_status", "capcut_status", "service_status"],
            "description": "监控状态 - 查看任务日志和各服务状态"
        }
    }

# 添加资源定义 - 基于筛选的端点
@mcp.resource(uri="flowclip://api/info")
def api_resource() -> str:
    """Flowclip API资源信息"""
    return """
    Flowclip视频处理平台API (优化版)
    
    核心功能:
    - 用户认证和登录
    - 项目管理 (列表、创建、查看项目视频)
    - 视频处理 (音频提取、字幕生成)
    - 视频切片 (验证、处理)
    - 系统集成 (CapCut导出、LLM对话)
    - 状态监控 (ASR、CapCut、系统服务状态)
    - 任务日志查询
    
    总计14个精选API端点，专注核心业务功能。
    """

@mcp.resource(uri="flowclip://workflows/core")  
def core_workflows() -> str:
    """核心工作流程说明"""
    return """
    Flowclip核心工作流程:
    
    1. 认证登录
       - 使用 login 进行用户认证
    
    2. 项目管理  
       - 使用 list_projects 查看项目
       - 使用 create_project 创建新项目
       - 使用 get_project_videos 查看项目视频
    
    3. 视频处理
       - 使用 extract_audio 提取音频
       - 使用 generate_srt 生成字幕
    
    4. 视频切片
       - 使用 validate_slices 验证切片数据
       - 使用 process_slices 处理切片
    
    5. 集成功能
       - 使用 export_slice 导出到CapCut
       - 使用 llm_chat 进行AI对话
    
    6. 监控管理
       - 使用 get_task_logs 查看任务日志
       - 使用 asr_status, capcut_status, service_status 监控服务
    """

@mcp.resource(uri="flowclip://tools/reference")
def tools_reference() -> str:
    """工具参考手册"""
    return """
    Flowclip MCP工具参考:
    
    认证工具:
    - login: 用户登录认证
    
    项目工具:
    - list_projects: 获取项目列表
    - create_project: 创建新项目  
    - get_project_videos: 获取项目视频
    
    处理工具:
    - extract_audio: 提取视频音频
    - generate_srt: 生成字幕文件
    - validate_slices: 验证切片数据
    - process_slices: 处理视频切片
    
    集成工具:
    - export_slice: 导出切片到CapCut
    - llm_chat: LLM智能对话
    
    监控工具:
    - get_task_logs: 获取任务日志
    - asr_status: ASR服务状态
    - capcut_status: CapCut服务状态
    - service_status: 系统服务状态
    
    所有工具名称均在63字符以内，符合MCP规范。
    """

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)