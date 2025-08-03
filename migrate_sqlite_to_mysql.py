#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to MySQL
"""

import asyncio
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import sys

# Add backend to path for imports
sys.path.append('backend')

# MySQL connection
import pymysql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate_sqlite_to_mysql():
    """Migrate data from SQLite to MySQL"""
    
    sqlite_path = Path('backend/youtube_slicer.db')
    if not sqlite_path.exists():
        print("❌ SQLite database not found")
        return
    
    # MySQL connection parameters
    mysql_config = {
        'host': 'localhost',
        'port': 3307,
        'user': 'youtube_user',
        'password': 'youtube_password',
        'database': 'youtube_slicer',
        'charset': 'utf8mb4'
    }
    
    try:
        # First, create tables using SQLAlchemy
        print("🔧 Creating MySQL tables...")
        await create_mysql_tables()
        
        # Connect to MySQL
        mysql_conn = pymysql.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor()
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        print("🔍 Starting migration from SQLite to MySQL...")
        
        # Get table list from SQLite
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in sqlite_cursor.fetchall()]
        
        total_records = 0
        
        for table in tables:
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
            for row in rows:
                # Convert data types for MySQL compatibility
                values = []
                for value in row:
                    if isinstance(value, str):
                        try:
                            # Try to parse as JSON if it looks like JSON
                            if value.startswith('{') or value.startswith('['):
                                json.loads(value)
                        except:
                            pass
                    elif value is None:
                        value = None
                    elif isinstance(value, (int, float)):
                        pass  # Keep as is
                    elif isinstance(value, bytes):
                        value = value.decode('utf-8')
                    
                    values.append(value)
                
                try:
                    mysql_cursor.execute(insert_query, values)
                    total_records += 1
                except Exception as e:
                    print(f"   ❌ Error inserting into {table}: {e}")
                    continue
            
            print(f"   ✅ Migrated {len(rows)} records from {table}")
        
        mysql_conn.commit()
        
        print(f"\n🎉 Migration completed successfully!")
        print(f"📊 Total records migrated: {total_records}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'mysql_conn' in locals():
            mysql_conn.rollback()
    finally:
        if 'mysql_conn' in locals():
            mysql_conn.close()
        if 'sqlite_conn' in locals():
            sqlite_conn.close()

async def create_mysql_tables():
    """Create tables in MySQL"""
    
    try:
        print("🔧 Creating MySQL tables...")
        
        # Import after path setup
        import sys
        sys.path.append('backend')
        
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import declarative_base
        from app.models import *  # Import all models
        
        # Use MySQL URL directly
        mysql_url = "mysql+aiomysql://youtube_user:youtube_password@localhost:3307/youtube_slicer"
        engine = create_async_engine(mysql_url)
        
        from sqlalchemy.orm import DeclarativeBase
        class Base(DeclarativeBase):
            pass
            
        # Import all models to register them
        from app.models.user import User
        from app.models.project import Project
        from app.models.video import Video
        from app.models.video_slice import VideoSlice
        from app.models.video_sub_slice import VideoSubSlice
        from app.models.audio_track import AudioTrack
        from app.models.transcript import Transcript
        from app.models.processing_task import ProcessingTask
        from app.models.llm_analysis import LLMAnalysis
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        print("✅ MySQL tables created successfully")
        
    except Exception as e:
        print(f"❌ Error creating MySQL tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 YouTube Slicer Database Migration Tool")
    print("=" * 50)
    
    print("\nOptions:")
    print("1. Create MySQL tables only")
    print("2. Migrate data from SQLite to MySQL")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(create_mysql_tables())
    elif choice == "2":
        asyncio.run(migrate_sqlite_to_mysql())
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid option")