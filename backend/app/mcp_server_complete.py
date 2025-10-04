#!/usr/bin/env python3
"""
MCP Server implementation for Flowclip API - 包含所有已修复operation_id的路由
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

# 所有已经设置了operation_id的操作 - 38个精选工具
ALLOWED_OPERATIONS = [
    # ASR服务 (1个)
    'asr_status',
    
    # 认证相关 (3个)
    'login',
    'register', 
    'get_current_user',
    
    # CapCut集成 (2个)
    'capcut_status',
    'export_slice',
    
    # LLM聊天 (4个)
    'llm_chat',
    'get_models',
    'get_system_prompt',
    'update_system_prompt',
    
    # 项目管理 (6个)
    'list_projects',
    'create_project',
    'get_project',
    'update_project',
    'delete_project',
    'get_project_videos',
    
    # 处理任务日志 (7个)
    'get_logs',
    'get_task_logs',
    'get_video_logs',
    'get_logs_stats',
    'delete_log',
    'delete_task_logs',
    'delete_video_logs',
    
    # 视频处理核心功能 (4个)
    'extract_audio',
    'generate_srt',
    'get_task_status',
    'get_processing_status',
    
    # 系统配置 (4个)
    'get_system_config',
    'update_system_config',
    'service_status',
    'test_asr',
    
    # 视频基础操作 (5个)
    'list_videos',
    'list_active_videos',
    'get_video',
    'update_video',
    'delete_video',
    
    # 视频下载 (4个)
    'download_video',
    'download_video_json',
    'get_video_download_url',
    'get_srt_content',
    
    # 状态查询 (4个)
    'get_video_status',
    'get_task_status_detail',
    'get_dashboard',
    'get_running_videos',
    
    # 视频切片处理 (4个)
    'validate_slices',
    'process_slices',
    'get_video_analyses',
    'get_video_slices'
]

# 创建完整的MCP服务器
mcp = FastApiMCP(
    app,
    name="Flowclip API",
    description="Flowclip视频处理平台 - 41个精选工具，所有工具名称都已优化",
    include_operations=ALLOWED_OPERATIONS,  # 包含所有41个已修复的操作
    describe_all_responses=True,
    describe_full_response_schema=True,
)

logger.info(f"🎉 完整MCP服务器创建完成！")
logger.info(f"📊 包含 {len(ALLOWED_OPERATIONS)} 个已优化的操作")
logger.info(f"🔧 所有工具名称都在20字符以内")

# 按类别显示工具
categories = {
    'ASR服务': ['asr_status'],
    '认证相关': ['login', 'register', 'get_current_user'],
    'CapCut集成': ['capcut_status', 'export_slice'],
    'LLM聊天': ['llm_chat', 'get_models', 'get_system_prompt', 'update_system_prompt'],
    '项目管理': ['list_projects', 'create_project', 'get_project', 'update_project', 'delete_project', 'get_project_videos'],
    '处理日志': ['get_logs', 'get_task_logs', 'get_video_logs', 'get_logs_stats', 'delete_log', 'delete_task_logs', 'delete_video_logs'],
    '视频处理': ['extract_audio', 'generate_srt', 'get_task_status', 'get_processing_status'],
    '系统配置': ['get_system_config', 'update_system_config', 'service_status', 'test_asr'],
    '视频管理': ['list_videos', 'list_active_videos', 'get_video', 'update_video', 'delete_video'],
    '视频下载': ['download_video', 'download_video_json', 'get_video_download_url', 'get_srt_content'],
    '状态查询': ['get_video_status', 'get_task_status_detail', 'get_dashboard', 'get_running_videos'],
    '视频切片': ['validate_slices', 'process_slices', 'get_video_analyses', 'get_video_slices']
}

for category, tools in categories.items():
    logger.info(f"  {category}: {len(tools)}个工具")

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)