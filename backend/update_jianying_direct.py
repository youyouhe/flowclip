#!/usr/bin/env python3
"""
直接更新数据库表结构和配置，不使用alembic
用于现有系统添加Jianying支持
"""

import os
import sys
import pymysql
from getpass import getpass

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def get_db_connection():
    """获取数据库连接"""
    print("请输入数据库连接信息:")

    # 从用户输入获取数据库连接信息
    host = input("数据库主机 (默认: localhost): ").strip() or "localhost"
    port = input("数据库端口 (默认: 3306): ").strip() or "3306"
    user = input("数据库用户名: ").strip()
    password = getpass("数据库密码: ")
    database = input("数据库名 (默认: youtube_slicer): ").strip() or "youtube_slicer"

    try:
        connection = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            charset='utf8mb4',
            autocommit=False
        )
        print("✅ 数据库连接成功!")
        return connection
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def check_table_exists(connection, table_name):
    """检查表是否存在"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = %s
            """, (table_name,))
            return cursor.fetchone()[0] > 0
    except Exception as e:
        print(f"❌ 检查表 {table_name} 失败: {e}")
        return False

def check_column_exists(connection, table_name, column_name):
    """检查列是否存在"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                AND table_name = %s
                AND column_name = %s
            """, (table_name, column_name))
            return cursor.fetchone()[0] > 0
    except Exception as e:
        print(f"❌ 检查列 {column_name} 失败: {e}")
        return False

def add_jianying_columns(connection):
    """添加jianying相关列到video_slices表"""
    print("\n🔧 检查并添加jianying字段到video_slices表...")

    jianying_columns = [
        ("jianying_status", "VARCHAR(50)", "pending", "Jianying导出状态"),
        ("jianying_task_id", "VARCHAR(255)", "NULL", "Jianying导出的Celery任务ID"),
        ("jianying_draft_url", "TEXT", "NULL", "Jianying草稿文件URL"),
        ("jianying_error_message", "TEXT", "NULL", "Jianying导出错误信息")
    ]

    columns_added = 0

    for column_name, column_type, default_value, comment in jianying_columns:
        if not check_column_exists(connection, "video_slices", column_name):
            try:
                with connection.cursor() as cursor:
                    sql = f"ALTER TABLE video_slices ADD COLUMN {column_name} {column_type}"
                    if default_value != "NULL":
                        sql += f" DEFAULT '{default_value}'"
                    if comment:
                        sql += f" COMMENT '{comment}'"

                    print(f"  ➕ 添加列: {column_name}")
                    cursor.execute(sql)
                    columns_added += 1
            except Exception as e:
                print(f"  ❌ 添加列 {column_name} 失败: {e}")
                return False
        else:
            print(f"  ✅ 列已存在: {column_name}")

    if columns_added > 0:
        print(f"🎉 成功添加 {columns_added} 个jianying字段!")
    else:
        print("ℹ️  所有jianying字段都已存在")

    return True

def add_jianying_configs(connection):
    """添加jianying配置到system_configs表"""
    print("\n⚙️ 检查并添加jianying系统配置...")

    jianying_configs = [
        ("jianying_api_url", "", "Jianying API服务的URL地址，用于剪映视频编辑功能", "其他服务配置"),
        ("jianying_api_key", "", "Jianying API密钥，用于访问剪映服务", "其他服务配置"),
        ("jianying_draft_folder", "剪映草稿", "Jianying导出的默认草稿保存文件夹路径，支持Windows和Unix路径格式", "其他服务配置")
    ]

    configs_added = 0

    for key, value, description, category in jianying_configs:
        try:
            with connection.cursor() as cursor:
                # 检查配置是否已存在
                cursor.execute(
                    "SELECT COUNT(*) FROM system_configs WHERE `key` = %s",
                    (key,)
                )

                if cursor.fetchone()[0] == 0:
                    # 插入新配置
                    cursor.execute("""
                        INSERT INTO system_configs (key, value, description, category, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                    """, (key, value, description, category))
                    print(f"  ➕ 添加配置: {key}")
                    configs_added += 1
                else:
                    print(f"  ✅ 配置已存在: {key}")
        except Exception as e:
            print(f"  ❌ 处理配置 {key} 失败: {e}")
            return False

    if configs_added > 0:
        print(f"🎉 成功添加 {configs_added} 个jianying配置!")
    else:
        print("ℹ️  所有jianying配置都已存在")

    return True

def verify_updates(connection):
    """验证更新结果"""
    print("\n🔍 验证更新结果...")

    # 验证表结构
    print("\n📋 video_slices表的jianying字段:")
    jianying_fields = ["jianying_status", "jianying_task_id", "jianying_draft_url", "jianying_error_message"]

    for field in jianying_fields:
        if check_column_exists(connection, "video_slices", field):
            print(f"  ✅ {field}")
        else:
            print(f"  ❌ {field} - 缺失")

    # 验证配置记录
    print("\n⚙️ system_configs表的jianying配置:")
    jianying_config_keys = ["jianying_api_url", "jianying_api_key", "jianying_draft_folder"]

    try:
        with connection.cursor() as cursor:
            for key in jianying_config_keys:
                cursor.execute(
                    "SELECT value FROM system_configs WHERE `key` = %s",
                    (key,)
                )
                result = cursor.fetchone()
                if result:
                    print(f"  ✅ {key}: {result[0] if result[0] else '(空)'}")
                else:
                    print(f"  ❌ {key} - 缺失")
    except Exception as e:
        print(f"  ❌ 验证配置失败: {e}")

def main():
    """主函数"""
    print("Jianying数据库更新脚本")
    print("=" * 50)

    # 获取数据库连接
    connection = get_db_connection()
    if not connection:
        print("❌ 无法建立数据库连接，退出")
        sys.exit(1)

    try:
        # 检查必要的表
        if not check_table_exists(connection, "video_slices"):
            print("❌ video_slices表不存在，请先初始化数据库")
            sys.exit(1)

        if not check_table_exists(connection, "system_configs"):
            print("❌ system_configs表不存在，请先初始化数据库")
            sys.exit(1)

        # 添加jianying字段
        if not add_jianying_columns(connection):
            print("❌ 添加jianying字段失败")
            connection.rollback()
            sys.exit(1)

        # 添加jianying配置
        if not add_jianying_configs(connection):
            print("❌ 添加jianying配置失败")
            connection.rollback()
            sys.exit(1)

        # 提交更改
        connection.commit()
        print("\n💾 所有更改已提交到数据库")

        # 验证结果
        verify_updates(connection)

        print("\n🎉 Jianying数据库更新完成!")
        print("\n下一步:")
        print("1. 重启应用服务")
        print("2. 在系统配置页面中配置Jianying参数")

    except Exception as e:
        print(f"❌ 更新过程中发生错误: {e}")
        connection.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        connection.close()
        print("\n数据库连接已关闭")

if __name__ == "__main__":
    main()