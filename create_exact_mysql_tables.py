#!/usr/bin/env python3
"""
Create MySQL tables with EXACT schema matching SQLite
Based on actual PRAGMA table_info() from your database
"""

import pymysql

def create_exact_tables():
    """Create MySQL tables with exact schema matching your SQLite"""
    
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
        
        # Drop existing tables
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        # Exact schema matching SQLite - based on your actual database
        sql_commands = [
            # 1. alembic_version
            """
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL,
                PRIMARY KEY (version_num)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 2. users - WITH google_id (was missing!)
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                email VARCHAR(255) NOT NULL,
                username VARCHAR(255) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                google_id VARCHAR(255),
                avatar_url VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                is_superuser BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_email (email(255)),
                UNIQUE KEY unique_username (username(255)),
                UNIQUE KEY unique_google_id (google_id(255))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 3. projects - WITH status field (was missing!)
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                user_id INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 4. videos - exact columns
            """
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                project_id INTEGER NOT NULL,
                title VARCHAR(500),
                description TEXT,
                url VARCHAR(1000),
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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                INDEX idx_project_id (project_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 5. audio_tracks - exact columns
            """
            CREATE TABLE audio_tracks (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                original_filename VARCHAR(500),
                audio_filename VARCHAR(500),
                file_path VARCHAR(1000),
                duration FLOAT,
                file_size INTEGER,
                format VARCHAR(50),
                bitrate INTEGER,
                sample_rate INTEGER,
                channels INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 6. transcripts - exact columns with audio_track_id
            """
            CREATE TABLE transcripts (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                audio_track_id INTEGER,
                content TEXT,
                segments JSON,
                language VARCHAR(50) DEFAULT 'zh-CN',
                total_segments INTEGER,
                processing_time FLOAT,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                FOREIGN KEY (audio_track_id) REFERENCES audio_tracks(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_audio_track_id (audio_track_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 7. processing_status - exact columns
            """
            CREATE TABLE processing_status (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                overall_status VARCHAR(50) DEFAULT 'pending',
                overall_progress FLOAT DEFAULT 0.0,
                current_stage VARCHAR(50),
                current_progress FLOAT DEFAULT 0.0,
                current_message VARCHAR(500),
                stage_details JSON,
                estimated_remaining_time INTEGER,
                started_at TIMESTAMP NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 8. processing_tasks - exact columns
            """
            CREATE TABLE processing_tasks (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                task_type VARCHAR(50) NOT NULL,
                task_name VARCHAR(200),
                celery_task_id VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                progress FLOAT DEFAULT 0.0,
                message TEXT,
                stage VARCHAR(50),
                output_data JSON,
                error_message TEXT,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_celery_task_id (celery_task_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 9. processing_task_logs - exact columns
            """
            CREATE TABLE processing_task_logs (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                task_id INTEGER NOT NULL,
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                message VARCHAR(500),
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES processing_tasks(id) ON DELETE CASCADE,
                INDEX idx_task_id (task_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 10. analysis_results - exact columns
            """
            CREATE TABLE analysis_results (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                transcript_id INTEGER,
                analysis_type VARCHAR(50) NOT NULL,
                content_summary TEXT,
                key_points JSON,
                recommendations JSON,
                metadata JSON,
                confidence_score FLOAT,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_analysis_type (analysis_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 11. llm_analyses - exact columns
            """
            CREATE TABLE llm_analyses (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                analysis_data JSON,
                cover_title VARCHAR(500),
                title VARCHAR(500),
                description TEXT,
                tags JSON,
                start_time VARCHAR(50),
                end_time VARCHAR(50),
                duration FLOAT,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 12. slices - exact columns
            """
            CREATE TABLE slices (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                title VARCHAR(500),
                description TEXT,
                tags JSON,
                start_time FLOAT,
                end_time FLOAT,
                duration FLOAT,
                file_path VARCHAR(1000),
                file_size INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 13. sub_slices - exact columns
            """
            CREATE TABLE sub_slices (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                slice_id INTEGER NOT NULL,
                title VARCHAR(500),
                description TEXT,
                start_time FLOAT,
                end_time FLOAT,
                duration FLOAT,
                file_path VARCHAR(1000),
                file_size INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (slice_id) REFERENCES slices(id) ON DELETE CASCADE,
                INDEX idx_slice_id (slice_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 14. video_slices - exact columns
            """
            CREATE TABLE video_slices (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                video_id INTEGER NOT NULL,
                llm_analysis_id INTEGER,
                cover_title VARCHAR(500),
                title VARCHAR(500),
                description TEXT,
                tags JSON,
                start_time VARCHAR(50),
                end_time VARCHAR(50),
                duration FLOAT,
                original_filename VARCHAR(500),
                sliced_filename VARCHAR(500),
                sliced_file_path VARCHAR(1000),
                file_size INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                FOREIGN KEY (llm_analysis_id) REFERENCES llm_analyses(id) ON DELETE CASCADE,
                INDEX idx_video_id (video_id),
                INDEX idx_llm_analysis_id (llm_analysis_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            
            # 15. video_sub_slices - exact columns
            """
            CREATE TABLE video_sub_slices (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                slice_id INTEGER NOT NULL,
                cover_title VARCHAR(500),
                title VARCHAR(500),
                description TEXT,
                tags JSON,
                start_time VARCHAR(50),
                end_time VARCHAR(50),
                duration FLOAT,
                sliced_filename VARCHAR(500),
                sliced_file_path VARCHAR(1000),
                file_size INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (slice_id) REFERENCES video_slices(id) ON DELETE CASCADE,
                INDEX idx_slice_id (slice_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        ]
        
        for sql in sql_commands:
            cursor.execute(sql)
            
        conn.commit()
        
        # Verify exact schema match
        cursor.execute("SHOW TABLES")
        mysql_tables = [row[0] for row in cursor.fetchall()]
        
        print("✅ Exact MySQL schema created!")
        print(f"📊 Tables created: {len(mysql_tables)}")
        
        # Show schema comparisons
        print("\n🔍 Schema verification:")
        for table in sorted(mysql_tables):
            cursor.execute(f"DESCRIBE {table}")
            mysql_cols = [row[0] for row in cursor.fetchall()]
            print(f"  {table}: {len(mysql_cols)} columns")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating exact MySQL tables: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_exact_tables()