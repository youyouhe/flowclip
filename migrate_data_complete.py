#!/usr/bin/env python3
"""
Complete data migration script: SQLite → MySQL
Handles all 15 tables with proper data type conversion
"""

import sqlite3
import pymysql
import json
from datetime import datetime
from pathlib import Path
import sys

def migrate_all_data():
    """Migrate all data from SQLite to MySQL for all 15 tables"""
    
    sqlite_path = Path('backend/youtube_slicer.db')
    if not sqlite_path.exists():
        print("❌ SQLite database not found")
        return False
    
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4',
        'autocommit': False
    }
    
    try:
        # Connect to databases
        mysql_conn = pymysql.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor()
        
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        print("🔍 Starting complete data migration...")
        
        # Get all tables from SQLite
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        sqlite_tables = [row[0] for row in sqlite_cursor.fetchall()]
        
        # Process tables in dependency order to avoid foreign key issues
        table_order = [
            'alembic_version',
            'users',
            'projects',
            'videos',
            'audio_tracks',
            'transcripts',
            'processing_status',
            'processing_tasks',
            'processing_task_logs',
            'analysis_results',
            'llm_analyses',
            'slices',
            'sub_slices',
            'video_slices',
            'video_sub_slices'
        ]
        
        total_records = 0
        
        for table in table_order:
            if table not in sqlite_tables:
                print(f"⚠️  {table} not found in SQLite")
                continue
                
            print(f"📊 Processing: {table}")
            
            # Get data from SQLite
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            
            if not rows:
                print(f"   ⚠️  No data in {table}")
                continue
            
            # Get column names
            columns = [desc[0] for desc in sqlite_cursor.description]
            
            # Build insert query
            placeholders = ', '.join(['%s'] * len(columns))
            insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Insert data into MySQL
            inserted_count = 0
            for row in rows:
                try:
                    # Convert data types for MySQL compatibility
                    values = []
                    for value in row:
                        if value is None:
                            values.append(None)
                        elif isinstance(value, str):
                            # Handle JSON strings and regular strings
                            if value.startswith('{') or value.startswith('['):
                                try:
                                    # Keep JSON strings as-is, MySQL will handle JSON
                                    values.append(value)
                                except:
                                    values.append(value)
                            else:
                                values.append(value)
                        elif isinstance(value, bytes):
                            values.append(value.decode('utf-8'))
                        else:
                            values.append(value)
                    
                    mysql_cursor.execute(insert_query, values)
                    inserted_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Error in {table}: {e}")
                    continue
            
            mysql_conn.commit()
            total_records += inserted_count
            print(f"   ✅ Migrated {inserted_count} records from {table}")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Total records migrated: {total_records}")
        
        # Verify data
        mysql_cursor.execute("SHOW TABLES")
        mysql_tables = [row[0] for row in mysql_cursor.fetchall()]
        
        print(f"\n📋 Tables in MySQL: {len(mysql_tables)}")
        for table in sorted(mysql_tables):
            mysql_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = mysql_cursor.fetchone()[0]
            print(f"  - {table}: {count} records")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        if 'mysql_conn' in locals():
            mysql_conn.rollback()
        return False
    finally:
        if 'mysql_conn' in locals():
            mysql_conn.close()
        if 'sqlite_conn' in locals():
            sqlite_conn.close()

def test_connection():
    """Test MySQL connection"""
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
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"✅ MySQL connected: {version[0]}")
        
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 Current tables: {len(tables)}")
        for table in sorted(tables):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count}")
            
        conn.close()
        return True
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_connection()
    else:
        migrate_all_data()