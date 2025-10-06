#!/usr/bin/env python3
"""
测试脚本：检查TUS配置项
用于检查数据库中是否存在tus_use_standalone_callback配置项
"""

import sys
import os

# 添加backend目录到Python路径
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

def check_tus_configs():
    """检查数据库中的TUS配置项"""
    try:
        from app.core.database import get_sync_db
        from app.services.system_config_service import SystemConfigService
        from app.models.system_config import SystemConfig

        print("🔍 正在检查数据库中的TUS配置项...")

        with get_sync_db() as db:
            # 1. 检查tus_use_standalone_callback配置
            print("\n1️⃣ 检查tus_use_standalone_callback配置:")
            config = db.query(SystemConfig).filter(SystemConfig.key == 'tus_use_standalone_callback').first()
            if config:
                print(f"   ✅ 配置存在: {config.key} = {config.value} ({config.name})")
                print(f"   📝 描述: {config.description}")
                print(f"   📂 分类: {config.category}")
            else:
                print("   ❌ tus_use_standalone_callback 配置不存在")

            # 2. 检查tus_use_global_callback配置
            print("\n2️⃣ 检查tus_use_global_callback配置:")
            config = db.query(SystemConfig).filter(SystemConfig.key == 'tus_use_global_callback').first()
            if config:
                print(f"   ✅ 配置存在: {config.key} = {config.value} ({config.name})")
                print(f"   📝 描述: {config.description}")
                print(f"   📂 分类: {config.category}")
            else:
                print("   ❌ tus_use_global_callback 配置不存在")

            # 3. 检查所有TUS相关配置
            print("\n3️⃣ 所有TUS相关配置:")
            configs = db.query(SystemConfig).filter(SystemConfig.key.like('tus_%')).all()
            if configs:
                for config in configs:
                    print(f"   • {config.key} = {config.value} ({config.name})")
                    if config.description:
                        print(f"     📝 {config.description}")
                    if config.category:
                        print(f"     📂 分类: {config.category}")
                    print()
            else:
                print("   ❌ 没有找到任何TUS配置")

            # 4. 检查配置映射表
            print("\n4️⃣ 配置服务中的TUS配置映射:")
            if hasattr(SystemConfigService, 'CONFIG_MAPPING'):
                tus_configs = {k: v for k, v in SystemConfigService.CONFIG_MAPPING.items() if k.startswith('tus_')}
                if tus_configs:
                    for key, attr in tus_configs.items():
                        print(f"   • {key} -> {attr}")
                else:
                    print("   ❌ 配置映射表中没有TUS配置")
            else:
                print("   ❌ SystemConfigService没有CONFIG_MAPPING属性")

            # 5. 检查默认配置文件
            print("\n5️⃣ 检查config.py中的TUS配置:")
            try:
                from app.core.config import settings
                tus_attrs = [attr for attr in dir(settings) if attr.startswith('tus_')]
                if tus_attrs:
                    for attr in tus_attrs:
                        value = getattr(settings, attr)
                        print(f"   • {attr} = {value}")
                else:
                    print("   ❌ config.py中没有TUS配置")
            except Exception as e:
                print(f"   ❌ 无法读取config.py: {e}")

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()

def check_config_init():
    """检查配置初始化脚本"""
    print("\n6️⃣ 检查配置初始化脚本:")
    init_script = os.path.join(os.path.dirname(__file__), 'backend', 'init_system_config.py')
    if os.path.exists(init_script):
        print(f"   ✅ 初始化脚本存在: {init_script}")
        try:
            with open(init_script, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'tus_use_standalone_callback' in content:
                    print("   ✅ 脚本包含tus_use_standalone_callback配置")
                else:
                    print("   ❌ 脚本不包含tus_use_standalone_callback配置")

                if 'tus_use_global_callback' in content:
                    print("   ✅ 脚本包含tus_use_global_callback配置")
                else:
                    print("   ❌ 脚本不包含tus_use_global_callback配置")
        except Exception as e:
            print(f"   ❌ 读取脚本失败: {e}")
    else:
        print(f"   ❌ 初始化脚本不存在: {init_script}")

def main():
    """主函数"""
    print("=" * 60)
    print("🔍 TUS配置检查工具")
    print("=" * 60)

    check_tus_configs()
    check_config_init()

    print("\n" + "=" * 60)
    print("📋 总结:")
    print("1. 如果tus_use_standalone_callback配置不存在，说明数据库中没有这个配置项")
    print("2. 如果配置存在但页面看不到，可能是前端没有显示这个配置项")
    print("3. 要使用固定9090端口，需要设置:")
    print("   - tus_use_standalone_callback = false")
    print("   - tus_use_global_callback = true")
    print("=" * 60)

if __name__ == "__main__":
    main()