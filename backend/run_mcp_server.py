#!/usr/bin/env python3
"""
Standalone MCP Server for YouTube Slicer
This script runs the MCP server on a separate port to avoid conflicts with the main FastAPI app
"""

import os
import sys
import logging
import uvicorn

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.mcp_server import mcp, app

if __name__ == "__main__":
    # Mount HTTP transport for MCP server
    mcp.mount_http()
    
    # Run the MCP server on a different port (8002) to avoid conflict with FastAPI (8001)
    logger.debug("Starting MCP server on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="debug")
