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

def load_system_configs():
    """从数据库加载系统配置"""
    try:
        # 显式加载环境变量
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        load_dotenv(dotenv_path)
        
        # 导入必要的模块
        from app.core.database import get_sync_db
        from app.services.system_config_service import SystemConfigService
        
        # 获取数据库会话并加载配置
        db = get_sync_db()
        SystemConfigService.update_settings_from_db_sync(db)
        db.close()
        
        logger.info("系统配置从数据库加载成功")
        return True
    except Exception as e:
        logger.error(f"从数据库加载系统配置失败: {e}")
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
    global reload_thread
    reload_thread = threading.Thread(target=reload_configs_periodically, args=(60,), daemon=True)
    reload_thread.start()
    
    # 获取命令行参数
    if len(sys.argv) < 2:
        logger.error("请指定要启动的服务类型: worker 或 beat")
        sys.exit(1)
    
    service_type = sys.argv[1]
    
    if service_type == "worker":
        # 启动 Celery Worker
        from app.core.celery import celery_app
        # 移除第一个参数(service_type)，保留其余参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        celery_app.worker_main()
    elif service_type == "beat":
        # 启动 Celery Beat
        from app.core.celery import celery_app
        # 移除第一个参数(service_type)，保留其余参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        celery_app.start()
    else:
        logger.error(f"不支持的服务类型: {service_type}，请使用 worker 或 beat")
        sys.exit(1)