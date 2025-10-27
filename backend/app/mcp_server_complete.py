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

# 所有已经设置了operation_id的操作 - 28个精选工具（移除了管理类工具）
ALLOWED_OPERATIONS = [
    # ASR服务 (1个)
    'asr_status',

    # 认证相关 (2个)
    'login',
    'get_current_user',

    # CapCut集成 (2个)
    'capcut_status',
    'export_slice',

    # Jianying集成 (1个)
    'export_jianying_slice',

    # LLM聊天 (3个)
    'llm_chat',
    'get_models',
    'get_system_prompt',

    # 项目管理 (3个)
    'list_projects',
    'get_project',
    'get_project_videos',

    # 处理任务日志 (4个)
    'get_logs',
    'get_task_logs',
    'get_video_logs',
    'get_logs_stats',

    # 视频处理核心功能 (4个)
    'extract_audio',
    'generate_srt',
    'get_task_status',
    'get_processing_status',

    # 系统配置 (2个)
    'service_status',
    'test_asr',

    # 视频基础操作 (4个)
    'list_videos',
    'list_active_videos',
    'get_video',
    'update_video',

    # 视频下载 (4个)
    'download_video',
    'download_video_json',
    'get_video_download_url',
    'get_srt_content',

    # 状态查询 (5个)
    'get_video_status',
    'get_task_status_detail',
    'get_celery_task_status',
    'get_dashboard',
    'get_running_videos',

    # 视频切片处理 (6个)
    'validate_slices',
    'process_slices',
    'get_video_analyses',
    'get_video_slices',
    'get_slice_detail',
    'get_slice_sub_slices'
]

# 创建完整的MCP服务器
mcp = FastApiMCP(
    app,
    name="Flowclip API",
    description="Flowclip视频处理平台 - 29个精选工具，移除了管理类操作，专注于查询和处理功能",
    include_operations=ALLOWED_OPERATIONS,  # 包含所有29个精选操作
    describe_all_responses=True,
    describe_full_response_schema=True,
)

logger.info(f"🎉 完整MCP服务器创建完成！")
logger.info(f"📊 包含 {len(ALLOWED_OPERATIONS)} 个精选操作（已移除管理类工具）")
logger.info(f"🔧 所有工具名称都在20字符以内")

# 按类别显示工具
categories = {
    'ASR服务': ['asr_status'],
    '认证相关': ['login', 'get_current_user'],
    'CapCut集成': ['capcut_status', 'export_slice'],
    'Jianying集成': ['export_jianying_slice'],
    'LLM聊天': ['llm_chat', 'get_models', 'get_system_prompt'],
    '项目管理': ['list_projects', 'get_project', 'get_project_videos'],
    '处理日志': ['get_logs', 'get_task_logs', 'get_video_logs', 'get_logs_stats'],
    '视频处理': ['extract_audio', 'generate_srt', 'get_task_status', 'get_processing_status'],
    '系统配置': ['service_status', 'test_asr'],
    '视频管理': ['list_videos', 'list_active_videos', 'get_video', 'update_video'],
    '视频下载': ['download_video', 'download_video_json', 'get_video_download_url', 'get_srt_content'],
    '状态查询': ['get_video_status', 'get_task_status_detail', 'get_celery_task_status', 'get_dashboard', 'get_running_videos'],
    '视频切片': ['validate_slices', 'process_slices', 'get_video_analyses', 'get_video_slices', 'get_slice_detail', 'get_slice_sub_slices']
}

for category, tools in categories.items():
    logger.info(f"  {category}: {len(tools)}个工具")

if __name__ == "__main__":
    # Run the MCP server with HTTP transport
    mcp.mount_http()
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)