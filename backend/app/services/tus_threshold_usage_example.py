"""
TUS阈值动态更新使用示例

这个文件展示了如何在应用程序中使用动态更新TUS文件大小阈值的功能。
"""

import logging
from app.core.database import get_sync_db
from app.services.system_config_service import SystemConfigService
from app.services.file_size_detector import file_size_detector, asr_strategy_selector, update_global_threshold

logger = logging.getLogger(__name__)


def example_usage():
    """
    使用示例：展示如何动态更新TUS阈值配置
    """
    print("=== TUS阈值动态更新使用示例 ===")

    # 1. 查看当前的阈值配置
    print(f"当前TUS阈值: {file_size_detector.threshold_mb}MB")

    # 2. 模拟用户通过UI更改数据库中的配置
    db = get_sync_db()
    try:
        # 更新数据库中的TUS阈值配置
        SystemConfigService.set_config_sync(
            db,
            "tus_file_size_threshold_mb",
            "20",  # 新的阈值为20MB
            "TUS文件大小阈值(MB)",
            "其他服务配置"
        )
        print("已更新数据库中的TUS阈值配置为20MB")

        # 注意：由于我们在set_config_sync中添加了自动更新机制，
        # 全局阈值配置应该已经自动更新了

        # 3. 验证全局阈值是否已更新
        print(f"更新后TUS阈值: {file_size_detector.threshold_mb}MB")

        # 4. 手动更新阈值（如果需要）
        # update_global_threshold(25)  # 手动设置为25MB
        # print(f"手动更新后TUS阈值: {file_size_detector.threshold_mb}MB")

        # 5. 测试文件大小检测
        test_file_sizes = [5 * 1024 * 1024, 15 * 1024 * 1024, 25 * 1024 * 1024]  # 5MB, 15MB, 25MB
        for file_size in test_file_sizes:
            # 模拟文件大小检测（不实际检测文件）
            use_tus = file_size >= (file_size_detector.threshold_mb * 1024 * 1024)
            strategy = "TUS" if use_tus else "Standard"
            print(f"文件大小: {file_size / (1024 * 1024):.1f}MB, 使用策略: {strategy}")

    except Exception as e:
        logger.error(f"示例执行失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    example_usage()