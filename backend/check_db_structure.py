#!/usr/bin/env python3
"""
检查数据库当前状态，特别是videos表的结构
"""
import pymysql

def check_database_structure():
    """检查数据库结构"""
    
    # MySQL连接配置
    db_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4'
    }
    
    print(f"连接MySQL: {db_config['host']}:{db_config['port']}")
    
    try:
        # 创建连接
        connection = pymysql.connect(**db_config)
        
        with connection.cursor() as cursor:
            # 检查videos表结构
            cursor.execute("DESCRIBE videos")
            columns = cursor.fetchall()
            
            print("\n=== videos表当前结构 ===")
            for col in columns:
                field = col[0] if col[0] is not None else "NULL"
                type_str = col[1] if col[1] is not None else "NULL"
                null_str = col[2] if col[2] is not None else "NULL"
                key_str = col[3] if col[3] is not None else "NULL"
                default_str = col[4] if col[4] is not None else "NULL"
                extra_str = col[5] if col[5] is not None else "NULL"
                print(f"{field:<25} {type_str:<15} {null_str:<10} {key_str:<10} {default_str:<15} {extra_str:<10}")
            
            # 检查alembic版本表
            try:
                cursor.execute("SELECT version_num FROM alembic_version ORDER BY version_num")
                versions = cursor.fetchall()
                print(f"\n=== 已应用的alembic版本 ===")
                for version in versions:
                    print(f"  {version[0]}")
            except pymysql.Error as e:
                print(f"\n=== alembic_version表不存在或查询失败: {e} ===")
            
            # 检查processing_status表
            try:
                cursor.execute("DESCRIBE processing_status")
                columns = cursor.fetchall()
                print(f"\n=== processing_status表结构 ===")
                for col in columns:
                    field = col[0] if col[0] is not None else "NULL"
                    type_str = col[1] if col[1] is not None else "NULL"
                    null_str = col[2] if col[2] is not None else "NULL"
                    key_str = col[3] if col[3] is not None else "NULL"
                    default_str = col[4] if col[4] is not None else "NULL"
                    extra_str = col[5] if col[5] is not None else "NULL"
                    print(f"{field:<25} {type_str:<15} {null_str:<10} {key_str:<10} {default_str:<15} {extra_str:<10}")
            except pymysql.Error as e:
                print(f"\n=== processing_status表不存在或查询失败: {e} ===")
                
        connection.close()
        return True
                
    except pymysql.Error as e:
        print(f"连接MySQL失败: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False

if __name__ == "__main__":
    check_database_structure()