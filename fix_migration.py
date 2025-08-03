#!/usr/bin/env python3
"""
Simple migration script to create MySQL tables and migrate data
"""

import asyncio
import sqlite3
import json
import pymysql
from pathlib import Path
import sys

def create_mysql_tables_direct():
    """Create MySQL tables directly using SQL"""
    
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
        
        # Create tables in correct order (dependencies first)
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                avatar_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_superuser BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id INT NOT NULL,
                title VARCHAR(500),
                description TEXT,
                url VARCHAR(1000),
                filename VARCHAR(500),
                file_path VARCHAR(1000),
                duration FLOAT,
                file_size INT,
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                INDEX idx_project_id (project_id),
                INDEX idx_status (status),
                UNIQUE KEY unique_url_project (url, project_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS processing_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_type VARCHAR(50) NOT NULL,
                video_id INT NOT NULL,
                user_id INT NOT NULL,
                celery_task_id VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                progress FLOAT DEFAULT 0.0,
                message TEXT,
                stage VARCHAR(50),
                output_data JSON,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_status (status),
                INDEX idx_celery_task_id (celery_task_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS video_slices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                video_id INT NOT NULL,
                llm_analysis_id INT,
                cover_title VARCHAR(255),
                title VARCHAR(255),
                description TEXT,
                tags JSON,
                start_time VARCHAR(50),
                end_time VARCHAR(50),
                duration FLOAT,
                original_filename VARCHAR(500),
                sliced_filename VARCHAR(500),
                sliced_file_path VARCHAR(1000),
                file_size INT,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS video_sub_slices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                slice_id INT NOT NULL,
                cover_title VARCHAR(255),
                start_time VARCHAR(50),
                end_time VARCHAR(50),
                duration FLOAT,
                sliced_filename VARCHAR(500),
                sliced_file_path VARCHAR(1000),
                file_size INT,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (slice_id) REFERENCES video_slices(id) ON DELETE CASCADE,
                INDEX idx_slice_id (slice_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS llm_analyses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                video_id INT NOT NULL,
                user_id INT NOT NULL,
                prompt TEXT,
                response_data JSON,
                status VARCHAR(50) DEFAULT 'pending',
                is_applied BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_status (status)
            )
            """
        ]
        
        for sql in tables_sql:
            cursor.execute(sql)
            
        conn.commit()
        print("✅ MySQL tables created successfully")
        
    except Exception as e:
        print(f"❌ Error creating MySQL tables: {e}")
        conn.rollback()
    finally:
        conn.close()

def migrate_data():
    """Migrate data from SQLite to MySQL"""
    
    sqlite_path = Path('backend/youtube_slicer.db')
    if not sqlite_path.exists():
        print("❌ SQLite database not found")
        return
    
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4'
    }
    
    try:
        # Connect to MySQL
        mysql_conn = pymysql.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor()
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        print("🔍 Starting data migration...")
        
        # Get table list from SQLite
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in sqlite_cursor.fetchall()]
        
        # Process tables in dependency order
        table_order = [
            'users',
            'projects', 
            'videos',
            'processing_tasks',
            'video_slices',
            'video_sub_slices',
            'llm_analyses'
        ]
        
        total_records = 0
        
        for table in table_order:
            if table not in tables:
                continue
                
            print(f"📊 Processing table: {table}")
            
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
                values = list(row)
                
                # Handle NULL values and JSON
                values = [None if v is None else v for v in values]
                
                try:
                    mysql_cursor.execute(insert_query, values)
                    inserted_count += 1
                except Exception as e:
                    print(f"   ❌ Error inserting row: {e}")
                    continue
            
            mysql_conn.commit()
            total_records += inserted_count
            print(f"   ✅ Migrated {inserted_count} records from {table}")
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Total records migrated: {total_records}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        if 'mysql_conn' in locals():
            mysql_conn.rollback()
    finally:
        if 'mysql_conn' in locals():
            mysql_conn.close()
        if 'sqlite_conn' in locals():
            sqlite_conn.close()

if __name__ == "__main__":
    print("🚀 YouTube Slicer Database Migration Tool")
    print("=" * 50)
    
    print("\nOptions:")
    print("1. Create MySQL tables only")
    print("2. Migrate data from SQLite to MySQL")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        create_mysql_tables_direct()
    elif choice == "2":
        create_mysql_tables_direct()
        migrate_data()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid option")