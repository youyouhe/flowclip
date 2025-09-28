#!/usr/bin/env python3
"""
Standalone MCP Server for Flowclip with Error Handling
This script runs the MCP server with proper error handling and fallback modes
"""

import os
import sys
import logging
import uvicorn

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def fix_environment():
    """修复环境变量问题"""
    try:
        # 修复MinIO endpoint为空的问题
        if not os.environ.get('MINIO_PUBLIC_ENDPOINT'):
            minio_endpoint = os.environ.get('MINIO_ENDPOINT', 'localhost:9000')
            if minio_endpoint.startswith('minio:'):
                # Docker环境，使用localhost
                os.environ['MINIO_PUBLIC_ENDPOINT'] = minio_endpoint.replace('minio:', 'localhost:')
            else:
                os.environ['MINIO_PUBLIC_ENDPOINT'] = minio_endpoint
            logger.info(f"已修复MINIO_PUBLIC_ENDPOINT: {os.environ['MINIO_PUBLIC_ENDPOINT']}")

        # 设置其他可能缺失的环境变量
        default_env = {
            'DATABASE_URL': 'sqlite+aiosqlite:///./youtube_slicer.db',
            'REDIS_URL': 'redis://localhost:6379',
            'SECRET_KEY': 'mcp-server-secret-key-for-testing',
        }
        
        for key, value in default_env.items():
            if not os.environ.get(key):
                os.environ[key] = value
                logger.info(f"设置默认环境变量 {key}")
                
    except Exception as e:
        logger.warning(f"修复环境变量时出错: {e}")

def main():
    """主函数"""
    try:
        # 修复环境问题
        fix_environment()
        
        # 导入MCP服务器
        logger.info("正在导入MCP服务器...")
        from app.mcp_server import mcp
        
        # 检查MCP对象
        if not hasattr(mcp, 'fastapi'):
            raise Exception("MCP服务器没有fastapi属性")
            
        app = mcp.fastapi
        logger.info(f"MCP服务器已加载: {mcp.name}")
        
        # Mount HTTP transport for MCP server
        logger.info("正在挂载MCP HTTP传输...")
        mcp.mount_http()
        
        # Run the MCP server on port 8002
        logger.info("启动MCP服务器在端口8002...")
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8002, 
            log_level="info",
            # 添加更多配置以提高稳定性
            timeout_keep_alive=300,
            limit_concurrency=100,
            limit_max_requests=1000
        )
        
    except ImportError as e:
        logger.error(f"导入错误: {e}")
        logger.info("可能需要安装依赖或检查环境配置")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"启动MCP服务器失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()