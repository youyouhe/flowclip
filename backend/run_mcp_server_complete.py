#!/usr/bin/env python3
"""
Standalone MCP Server for Flowclip - 完整版包含所有已修复的工具
"""

import os
import sys
import logging
import uvicorn

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.mcp_server_complete import mcp, app

if __name__ == "__main__":
    # Mount HTTP transport for MCP server
    mcp.mount_http()
    
    # Run the MCP server on port 8002
    logger.info("🚀 启动完整版MCP服务器（39个优化工具）在端口8002...")
    logger.info("🎯 所有API都已设置operation_id，工具名称简短清晰")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")