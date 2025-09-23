"""
TUS阈值更新服务
当数据库中的tus_file_size_threshold_mb配置项发生变化时，调用此服务来更新全局阈值配置
"""

import logging
from app.core.database import get_sync_db
from app.services.system_config_service import SystemConfigService
from app.services.file_size_detector import update_global_threshold

logger = logging.getLogger(__name__)


def update_tus_threshold_from_db():
    """
    从数据库读取最新的TUS文件大小阈值配置，并更新全局实例
    """
    try:
        # 获取数据库会话
        db = get_sync_db()

        # 从数据库加载配置到settings
        SystemConfigService.update_settings_from_db_sync(db)

        # 从settings获取最新的阈值配置
        from app.core.config import settings
        new_threshold = getattr(settings, 'tus_file_size_threshold_mb', 10)

        # 更新全局阈值配置
        update_global_threshold(new_threshold)

        logger.info(f"成功更新TUS阈值配置为: {new_threshold}MB")

        # 关闭数据库会话
        db.close()

        return True
    except Exception as e:
        logger.error(f"更新TUS阈值配置失败: {e}", exc_info=True)
        return False


# 使用示例:
# 在适当的地方（例如，当检测到数据库配置发生变化时）调用此函数
# update_tus_threshold_from_db()