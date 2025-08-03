#!/usr/bin/env python3
"""
Debug videos table migration issue
"""

import sqlite3
import pymysql
import json

def debug_videos_migration():
    """Debug videos table migration"""
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect('backend/youtube_slicer.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to MySQL
    mysql_conn = pymysql.connect(
        host='localhost', port=3307, user='youtube_user',
        password='youtube_password', database='youtube_slicer'
    )
    mysql_cursor = mysql_conn.cursor()
    
    print("🔍 Debugging videos table migration...")
    
    # 1. Check SQLite table structure
    sqlite_cursor.execute("PRAGMA table_info(videos)")
    sqlite_cols = sqlite_cursor.fetchall()
    print(f"\n📊 SQLite videos table columns ({len(sqlite_cols)}):")
    for i, col in enumerate(sqlite_cols):
        print(f"  {i}: {col[1]} {col[2]}")
    
    # 2. Check first few rows
    sqlite_cursor.execute("SELECT * FROM videos LIMIT 3")
    rows = sqlite_cursor.fetchall()
    print(f"\n📋 First 3 rows:")
    for i, row in enumerate(rows):
        print(f"  Row {i+1}: {len(row)} columns")
        for j, val in enumerate(row):
            print(f"    {sqlite_cols[j][1]}: {repr(val)} ({type(val)})")
    
    # 3. Check for problematic data
    sqlite_cursor.execute("SELECT COUNT(*) FROM videos")
    total_rows = sqlite_cursor.fetchone()[0]
    print(f"\n📊 Total rows in SQLite: {total_rows}")
    
    # 4. Check for NULL values in critical fields
    critical_fields = ['processing_progress', 'download_progress', 'created_at', 'updated_at']
    for field in critical_fields:
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM videos WHERE {field} IS NULL OR {field} = ''")
        null_count = sqlite_cursor.fetchone()[0]
        print(f"  {field} NULL/empty: {null_count}")
    
    # 5. Try manual insert with simplified data
    mysql_cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTO_INCREMENT,
        project_id INTEGER NOT NULL,
        title VARCHAR(500),
        description TEXT,
        url VARCHAR(500),
        filename VARCHAR(500),
        file_path VARCHAR(1000),
        duration FLOAT,
        file_size INTEGER,
        thumbnail_url VARCHAR(1000),
        status VARCHAR(50) DEFAULT 'pending',
        download_progress FLOAT DEFAULT 0.0,
        processing_stage VARCHAR(50),
        processing_progress FLOAT DEFAULT 0.0,
        processing_message VARCHAR(500),
        processing_error TEXT,
        processing_started_at TIMESTAMP NULL,
        processing_completed_at TIMESTAMP NULL,
        processing_metadata JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """)
    
    # 6. Test insert first row
    if rows:
        row = rows[0]
        try:
            # Clean the data
            clean_row = list(row)
            for i, val in enumerate(clean_row):
                if val == '' or val == '{}':
                    clean_row[i] = None
                elif sqlite_cols[i][2] == 'FLOAT' and isinstance(val, str):
                    try:
                        clean_row[i] = float(val) if val else 0.0
                    except:
                        clean_row[i] = 0.0
            
            mysql_cursor.execute("""
            INSERT INTO videos (
                id, project_id, title, description, url, filename, file_path, 
                duration, file_size, thumbnail_url, status, download_progress,
                processing_stage, processing_progress, processing_message, processing_error,
                processing_started_at, processing_completed_at, processing_metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, clean_row)
            mysql_conn.commit()
            print("✅ First row inserted successfully")
            
        except Exception as e:
            print(f"❌ Insert failed: {e}")
            print(f"Row data: {clean_row}")
    
    # 7. Final verification
    mysql_cursor.execute("SELECT COUNT(*) FROM videos")
    mysql_count = mysql_cursor.fetchone()[0]
    print(f"\n📊 MySQL videos table: {mysql_count} rows")
    
    sqlite_conn.close()
    mysql_conn.close()

if __name__ == "__main__":
    debug_videos_migration()