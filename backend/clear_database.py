#!/usr/bin/env python3
"""
清空数据库脚本
用于清空 YouTube Slicer 数据库中的所有数据和 MinIO 存储文件
"""

import asyncio
import sys
import os
from minio import Minio
from minio.error import S3Error
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.database import Base

async def clear_minio():
    """清空 MinIO 存储桶中的所有文件"""
    
    print("\n正在连接 MinIO...")
    
    try:
        # 创建 MinIO 客户端
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            region="us-east-1"
        )
        
        bucket_name = settings.minio_bucket_name
        
        # 检查桶是否存在
        if not minio_client.bucket_exists(bucket_name):
            print(f"- MinIO 桶 '{bucket_name}' 不存在")
            return
        
        # 列出并删除所有对象
        objects = minio_client.list_objects(bucket_name, recursive=True)
        objects_to_delete = []
        
        for obj in objects:
            objects_to_delete.append(obj.object_name)
        
        if objects_to_delete:
            print(f"正在删除 {len(objects_to_delete)} 个 MinIO 文件...")
            
            # 逐个删除文件
            deleted_count = 0
            for obj_name in objects_to_delete:
                try:
                    minio_client.remove_object(bucket_name, obj_name)
                    deleted_count += 1
                    if deleted_count % 100 == 0:
                        print(f"✓ 已删除 {deleted_count}/{len(objects_to_delete)} 个文件")
                except Exception as e:
                    print(f"✗ 删除文件失败 {obj_name}: {e}")
            
            print(f"✓ MinIO 清空完成！共删除 {deleted_count} 个文件")
        else:
            print("- MinIO 桶中无文件")
            
    except Exception as e:
        print(f"✗ MinIO 操作失败: {str(e)}")
        raise

async def clear_database():
    """清空数据库中的所有数据"""
    
    print("=" * 60)
    print("YouTube Slicer 数据库和存储清空工具")
    print("=" * 60)
    
    # 确认操作 - 自动确认用于批量处理
    print("此操作将清空以下内容：")
    print("1. 数据库中的所有数据（用户、项目、视频、切片等）")
    print("2. MinIO 存储中的所有文件（视频、音频、字幕等）")
    print("3. 所有处理任务记录和日志")
    print("\n警告：此操作不可恢复！")
    print("自动确认处理...")
    
    confirm = 'YES'  # 自动确认
    
    # 自动清空 MinIO
    clear_minio_flag = True  # 自动清空 MinIO
    print("\n自动清空 MinIO 存储文件...")
    
    print("\n正在连接数据库...")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    try:
        async with engine.begin() as conn:
            print("正在清空数据表...")
            
            # 获取所有表名（按依赖关系排序，避免外键约束问题）
            tables_to_clear = [
                'processing_task_logs',     # 处理任务日志
                'video_sub_slices',        # 视频子切片
                'video_slices',            # 视频切片
                'llm_analyses',            # LLM分析
                'transcripts',             # 字幕
                'analysis_results',        # 分析结果
                'processing_tasks',        # 处理任务
                'processing_status',       # 处理状态
                'audio_tracks',            # 音频轨道
                'sub_slices',              # 子切片
                'slices',                  # 切片
                'videos',                  # 视频
                'projects',                # 项目
                'users',                   # 用户
            ]
            
            for table in tables_to_clear:
                try:
                    # 检查表是否存在
                    result = await conn.execute(
                        text(f"SHOW TABLES LIKE '{table}'")
                    )
                    table_exists = result.fetchone() is not None
                    
                    if table_exists:
                        # 清空表数据
                        await conn.execute(text(f"DELETE FROM {table}"))
                        print(f"✓ 已清空表: {table}")
                    else:
                        print(f"- 表不存在: {table}")
                        
                except Exception as e:
                    print(f"✗ 清空表 {table} 失败: {str(e)}")
            
            # 重置自增ID
            print("\n正在重置自增ID...")
            for table in tables_to_clear:
                try:
                    result = await conn.execute(
                        text(f"SHOW TABLES LIKE '{table}'")
                    )
                    table_exists = result.fetchone() is not None
                    
                    if table_exists:
                        await conn.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1"))
                        print(f"✓ 已重置表 {table} 的自增ID")
                        
                except Exception as e:
                    print(f"✗ 重置表 {table} 自增ID失败: {str(e)}")
            
            print("\n✓ 数据库清空完成！")
            
    except Exception as e:
        print(f"✗ 数据库操作失败: {str(e)}")
        raise
    finally:
        await engine.dispose()
    
    # 清空 MinIO
    if clear_minio_flag:
        await clear_minio()
    
    print("\n" + "=" * 60)
    print("清空操作完成！")
    print("=" * 60)
    
    print("\n建议后续操作：")
    print("1. 重新创建测试用户: python create_test_user.py")
    print("2. 运行数据库迁移: alembic upgrade head")
    print("3. 重启后端服务")
    print("4. 重启 Celery Worker")

if __name__ == "__main__":
    asyncio.run(clear_database())