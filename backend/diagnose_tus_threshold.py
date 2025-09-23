# 诊断脚本：检查TUS阈值配置问题
import sys
import os

# 添加项目路径
sys.path.append('/home/cat/EchoClip/backend')

from app.core.config import settings
from app.core.database import get_sync_db
from app.services.system_config_service import SystemConfigService

print("=== 诊断TUS阈值配置问题 ===")

# 1. 检查settings中的值
print(f"1. Settings中的tus_file_size_threshold_mb: {getattr(settings, 'tus_file_size_threshold_mb', 'Not found')}")

# 2. 从数据库获取所有配置
db = get_sync_db()
try:
    db_configs = SystemConfigService.get_all_configs_sync(db)
    print(f"2. 数据库中的tus_file_size_threshold_mb: {db_configs.get('tus_file_size_threshold_mb', 'Not found')}")

    # 3. 检查数据库中特定配置项
    specific_config = SystemConfigService.get_config(db, 'tus_file_size_threshold_mb')
    print(f"3. 通过get_config获取的值: {specific_config}")

    # 4. 手动更新settings
    print("4. 手动更新settings...")
    SystemConfigService.update_settings_from_db_sync(db)

    # 5. 再次检查settings中的值
    print(f"5. 更新后settings中的tus_file_size_threshold_mb: {getattr(settings, 'tus_file_size_threshold_mb', 'Not found')}")

finally:
    db.close()

# 6. 检查FileSizeDetector
from app.services.file_size_detector import file_size_detector
print(f"6. FileSizeDetector阈值: {file_size_detector.threshold_mb}MB")

# 7. 手动创建新的FileSizeDetector实例
from app.services.file_size_detector import FileSizeDetector
new_detector = FileSizeDetector()
print(f"7. 新FileSizeDetector实例阈值: {new_detector.threshold_mb}MB")