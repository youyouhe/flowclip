#!/usr/bin/env python3
"""
MCP Server implementation for Flowclip API - 仅包含已修复operation_id的路由
"""

import os
import sys
import logging
from fastapi_mcp import FastApiMCP

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Import the FastAPI app
from app.main import app

# Enable info logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 只包含已经明确设置了operation_id的操作
ALLOWED_OPERATIONS = [
    # 已修复的认证路由
    'login',
    'register', 
    'get_current_user',
    
    # 已修复的项目路由
    'list_projects',
    'create_project',
    
    # 已修复的视频切片路由
    'validate_slices',
    'process_slices'
]

# 创建MCP服务器 - 只包含已修复的操作
mcp = FastApiMCP(
    app,
    name="Flowclip API",
    description="Flowclip视频处理平台 - 7个已修复的工具",
    include_operations=ALLOWED_OPERATIONS,  # 只包含这7个已修复的操作
    describe_all_responses=False,
    describe_full_response_schema=False,
)

logger.info(f"MCP服务器创建完成，包含 {len(ALLOWED_OPERATIONS)} 个已修复的操作")
logger.info(f"操作列表: {', '.join(ALLOWED_OPERATIONS)}")

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)