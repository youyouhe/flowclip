#!/usr/bin/env python3
"""
修复所有引用videos_backup的外键约束
"""

import pymysql

def fix_all_foreign_keys():
    """修复所有错误的外键约束"""
    
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
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 需要修复的表和外键映射
        foreign_key_fixes = {
            'processing_status': [('processing_status_FK_0_0', 'video_id', 'videos(id)')],
            'audio_tracks': [('audio_tracks_FK_0_0', 'video_id', 'videos(id)')],
            'transcripts': [
                ('transcripts_FK_0_0', 'video_id', 'videos(id)'),
                ('transcripts_FK_1_0', 'audio_track_id', 'audio_tracks(id)')
            ],
            'analysis_results': [
                ('analysis_results_FK_0_0', 'video_id', 'videos(id)'),
                ('analysis_results_FK_1_0', 'transcript_id', 'transcripts(id)')
            ],
            'llm_analyses': [('llm_analyses_FK_0_0', 'video_id', 'videos(id)')],
            'video_slices': [
                ('video_slices_FK_0_0', 'video_id', 'videos(id)'),
                ('video_slices_FK_1_0', 'llm_analysis_id', 'llm_analyses(id)')
            ],
            'video_sub_slices': [('video_sub_slices_FK_0_0', 'slice_id', 'video_slices(id)')]
        }
        
        for table, constraints in foreign_key_fixes.items():
            for constraint_name, column, ref_table in constraints:
                try:
                    # 删除错误的外键
                    cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {constraint_name}")
                    print(f"✅ 删除 {table}.{constraint_name}")
                except pymysql.err.InternalError as e:
                    if "Can't DROP" in str(e):
                        print(f"⚠️ {table}.{constraint_name} 不存在")
                    else:
                        print(f"❌ 删除 {table}.{constraint_name} 失败: {e}")
        
        # 添加正确的外键
        for table, constraints in foreign_key_fixes.items():
            for constraint_name, column, ref_table in constraints:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} FOREIGN KEY ({column}) REFERENCES {ref_table}")
                    print(f"✅ 添加 {table}.{constraint_name}")
                except Exception as e:
                    print(f"⚠️ 添加 {table}.{constraint_name} 失败: {e}")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("✅ 所有外键约束已修复")
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_all_foreign_keys()