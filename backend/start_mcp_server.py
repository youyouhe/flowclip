#!/usr/bin/env python3
"""
启动 MCP 服务器
"""

import logging
import uvicorn
from app.mcp_server import mcp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """启动MCP服务器"""
    try:
        logger.info("正在启动 Flowclip MCP 服务器...")
        
        # 设置服务器
        mcp.setup_server()
        
        # 显示工具信息
        logger.info(f"MCP服务器名称: {mcp.name}")
        logger.info(f"MCP服务器描述: {mcp.description}")
        logger.info(f"总计工具数量: {len(mcp.tools)}")
        
        if mcp.tools:
            logger.info("可用工具:")
            for tool in mcp.tools:
                name = tool.name if hasattr(tool, 'name') else str(tool)
                logger.info(f"  - {name} ({len(name)} chars)")
                
            # 检查名称长度
            long_names = [t for t in mcp.tools if len(getattr(t, 'name', str(t))) > 63]
            if long_names:
                logger.warning(f"发现 {len(long_names)} 个超长工具名称")
                for tool in long_names:
                    name = tool.name if hasattr(tool, 'name') else str(tool)
                    logger.warning(f"  超长名称: {name} ({len(name)} chars)")
            else:
                logger.info("✅ 所有工具名称都在63字符以内")
        
        # 挂载HTTP服务器
        mcp.mount_http()
        
        # 启动服务器
        logger.info("MCP服务器启动在 http://0.0.0.0:8002")
        logger.info("使用 Ctrl+C 停止服务器")
        
        uvicorn.run(
            mcp.fastapi,  # 使用MCP包装的FastAPI应用
            host="0.0.0.0",
            port=8002,
            log_level="info"
        )
        
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"启动MCP服务器失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()