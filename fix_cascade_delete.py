#!/usr/bin/env python3
"""
更新所有外键约束为 CASCADE DELETE
"""

import pymysql

def update_cascade_delete():
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4'
    }

    conn = pymysql.connect(**mysql_config)
    cursor = conn.cursor()

    try:
        cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
        
        # Get all foreign key constraints
        cursor.execute('''
            SELECT 
                kcu.TABLE_NAME,
                kcu.CONSTRAINT_NAME,
                kcu.COLUMN_NAME,
                kcu.REFERENCED_TABLE_NAME,
                kcu.REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc 
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            WHERE kcu.TABLE_SCHEMA = 'youtube_slicer' 
                AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY kcu.TABLE_NAME;
        ''')
        
        constraints = cursor.fetchall()
        
        for table, constraint_name, column, ref_table, ref_column in constraints:
            # Drop existing constraint
            try:
                cursor.execute(f'ALTER TABLE {table} DROP FOREIGN KEY {constraint_name}')
                print(f'✅ 删除 {table}.{constraint_name}')
            except Exception as e:
                print(f'⚠️ 删除 {table}.{constraint_name} 失败: {e}')
            
            # Add new constraint with CASCADE DELETE
            try:
                cursor.execute(f'''
                    ALTER TABLE {table} 
                    ADD CONSTRAINT {constraint_name} 
                    FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column}) 
                    ON DELETE CASCADE ON UPDATE CASCADE
                ''')
                print(f'✅ 添加 {table}.{constraint_name} (CASCADE DELETE)')
            except Exception as e:
                print(f'⚠️ 添加 {table}.{constraint_name} 失败: {e}')
        
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
        conn.commit()
        print('✅ 所有外键约束已更新为 CASCADE DELETE')
        
    except Exception as e:
        print(f'❌ 更新失败: {e}')
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_cascade_delete()