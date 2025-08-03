#!/usr/bin/env python3
"""
清除MySQL所有表的工具脚本
每次迁移前运行，确保干净的环境
"""

import pymysql
import sys

def clear_mysql_tables():
    """清除MySQL中的所有表"""
    
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4'
    }
    
    try:
        conn = pymysql.connect(**mysql_config)
        cursor = conn.cursor()
        
        # 禁用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 获取所有表
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        
        if not tables:
            print("✅ MySQL数据库已经是空的")
            return
        
        print(f"🧹 正在清除 {len(tables)} 个表...")
        
        # 删除所有表
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            print(f"   已删除: {table}")
        
        # 重新启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        conn.commit()
        print("✅ 所有MySQL表已清除")
        
    except Exception as e:
        print(f"❌ 清除MySQL表失败: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()
    
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        clear_mysql_tables()
    else:
        response = input("确定要清除MySQL中的所有表吗？(y/N): ")
        if response.lower() == 'y':
            clear_mysql_tables()
        else:
            print("取消操作")