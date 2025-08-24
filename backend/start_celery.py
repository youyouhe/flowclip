#!/usr/bin/env python3
"""
Celery Worker 启动脚本
在启动 Celery Worker 之前从数据库加载系统配置
"""

import os
import sys
import logging
import signal
import threading
import time
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量用于控制配置重载线程
reload_thread = None
reload_stop_event = threading.Event()

def load_system_configs(max_retries=10, retry_interval=3):
    """从数据库加载系统配置，带重试机制"""
    for attempt in range(max_retries):
        try:
            # 显式加载环境变量
            dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            load_dotenv(dotenv_path)
            
            # 导入必要的模块
            from app.core.database import get_sync_db
            from app.services.system_config_service import SystemConfigService
            from app.core.config import settings
            from app.services.minio_client import minio_service
            
            # 打印加载前的配置
            logger.info(f"加载前的minio_public_endpoint: {settings.minio_public_endpoint}")
            
            # 获取数据库会话并加载配置
            db = get_sync_db()
            SystemConfigService.update_settings_from_db_sync(db)
            db.close()
            
            # 重新加载MinIO客户端配置
            minio_service.reload_config()
            
            # 打印加载后的配置
            logger.info(f"加载后的minio_public_endpoint: {settings.minio_public_endpoint}")
            logger.info("系统配置从数据库加载成功")
            return True
        except Exception as e:
            logger.warning(f"从数据库加载系统配置失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            import traceback
            logger.warning(f"详细错误信息: {traceback.format_exc()}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                logger.error(f"从数据库加载系统配置失败，已重试 {max_retries} 次")
                return False

def reload_configs_periodically(interval=60):
    """定期重新加载系统配置"""
    while not reload_stop_event.wait(interval):
        logger.info("定期重新加载系统配置...")
        load_system_configs()

def signal_handler(signum, frame):
    """信号处理函数，用于优雅关闭"""
    logger.info("收到信号，准备关闭...")
    reload_stop_event.set()
    if reload_thread and reload_thread.is_alive():
        reload_thread.join()
    sys.exit(0)

if __name__ == "__main__":
    import sys
    
    # 设置信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 加载系统配置
    if not load_system_configs():
        logger.warning("系统配置加载失败，将继续使用环境变量配置")
    
    # 启动定期重载配置的线程
    reload_thread = threading.Thread(target=reload_configs_periodically, args=(60,), daemon=True)
    reload_thread.start()
    
    # 获取命令行参数
    if len(sys.argv) < 2:
        logger.error("请指定要启动的服务类型: worker 或 beat")
        sys.exit(1)
    
    service_type = sys.argv[1]
    
    if service_type == "worker":
        # 启动 Celery Worker
        import subprocess
        import sys
        # 构造celery worker命令
        cmd = ["celery", "-A", "app.core.celery", "worker"] + sys.argv[2:]
        # 执行命令
        subprocess.run(cmd)
    elif service_type == "beat":
        # 启动 Celery Beat
        import subprocess
        import sys
        # 构造celery beat命令
        cmd = ["celery", "-A", "app.core.celery", "beat"] + sys.argv[2:]
        # 执行命令
        subprocess.run(cmd)
    else:
        logger.error(f"不支持的服务类型: {service_type}，请使用 worker 或 beat")
        sys.exit(1)