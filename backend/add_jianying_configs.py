#!/usr/bin/env python3
"""
添加Jianying相关系统配置记录

执行方法：
python add_jianying_configs.py

或通过alembic升级后重新启动应用
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import get_db_session
from app.models.system_config import SystemConfig

# Jianying相关配置项
JIANYING_CONFIGS = [
    {
        'key': 'jianying_api_url',
        'value': '',
        'description': 'Jianying API服务的URL地址，用于剪映视频编辑功能',
        'category': '其他服务配置',
        'default_value': ''
    },
    {
        'key': 'jianying_api_key',
        'value': '',
        'description': 'Jianying API密钥，用于访问剪映服务',
        'category': '其他服务配置',
        'default_value': ''
    },
    {
        'key': 'jianying_draft_folder',
        'value': '剪映草稿',
        'description': 'Jianying导出的默认草稿保存文件夹路径，支持Windows和Unix路径格式',
        'category': '其他服务配置',
        'default_value': '剪映草稿'
    }
]


async def add_jianying_configs():
    """添加Jianying相关配置到数据库"""
    print("开始添加Jianying系统配置...")

    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            added_count = 0
            updated_count = 0

            for config_data in JIANYING_CONFIGS:
                # 检查配置是否已存在
                existing_config = await db.execute(
                    f"SELECT * FROM system_configs WHERE key = '{config_data['key']}'"
                )
                existing = existing_config.fetchone()

                if existing:
                    print(f"配置 '{config_data['key']}' 已存在，跳过添加")
                    updated_count += 1
                else:
                    # 创建新配置
                    new_config = SystemConfig(
                        key=config_data['key'],
                        value=config_data['value'],
                        description=config_data['description'],
                        category=config_data['category']
                    )

                    db.add(new_config)
                    added_count += 1
                    print(f"✓ 添加配置: {config_data['key']}")

            # 提交所有更改
            await db.commit()

            print(f"\n配置添加完成!")
            print(f"新增配置: {added_count} 个")
            print(f"已存在配置: {updated_count} 个")

            # 验证添加结果
            print("\n验证Jianying配置:")
            for config_data in JIANYING_CONFIGS:
                verify_result = await db.execute(
                    f"SELECT key, value, description FROM system_configs WHERE key = '{config_data['key']}'"
                )
                record = verify_result.fetchone()
                if record:
                    print(f"✓ {record[0]}: {record[2][:50]}...")
                else:
                    print(f"✗ {config_data['key']}: 未找到")

    except Exception as e:
        print(f"添加配置时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


async def check_system_configs_table():
    """检查system_configs表是否存在"""
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'system_configs'
            """)
            table_exists = result.fetchone()[0] > 0

            if not table_exists:
                print("❌ system_configs表不存在，请先运行数据库迁移")
                return False

            print("✓ system_configs表存在")

            # 检查现有的jianying配置
            result = await db.execute("""
                SELECT key, value FROM system_configs
                WHERE key LIKE '%jianying%' OR key LIKE '%剪映%'
            """)
            existing_configs = result.fetchall()

            if existing_configs:
                print(f"找到 {len(existing_configs)} 个现有的jianying相关配置:")
                for config in existing_configs:
                    print(f"  - {config[0]}: {config[1] if config[1] else '(空)'}")
            else:
                print("未找到现有的jianying相关配置")

            return True

    except Exception as e:
        print(f"检查系统配置表时发生错误: {e}")
        return False


async def main():
    """主函数"""
    print("Jianying系统配置初始化脚本")
    print("=" * 50)

    # 检查system_configs表
    if not await check_system_configs_table():
        sys.exit(1)

    print()

    # 添加配置
    success = await add_jianying_configs()

    if success:
        print("\n🎉 Jianying系统配置初始化完成!")
        print("\n下一步:")
        print("1. 运行数据库迁移: alembic upgrade head")
        print("2. 重启应用服务")
        print("3. 在系统配置页面中配置Jianying相关参数")
    else:
        print("\n❌ Jianying系统配置初始化失败!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())