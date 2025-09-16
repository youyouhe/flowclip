#!/usr/bin/env python3
"""
备份数据库脚本
用于在清空数据库前备份重要数据
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

async def backup_database():
    """备份数据库中的配置和重要数据"""
    
    print("=" * 60)
    print("Flowclip 数据库备份工具")
    print("=" * 60)
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "users": [],
        "projects": [],
        "config": {}
    }
    
    try:
        async with engine.begin() as conn:
            print("正在备份数据...")
            
            # 备份用户数据（不包含密码）
            result = await conn.execute(
                text("SELECT id, email, username, is_active, created_at FROM users")
            )
            for row in result.fetchall():
                backup_data["users"].append({
                    "id": row[0],
                    "email": row[1], 
                    "username": row[2],
                    "is_active": row[3],
                    "created_at": row[4].isoformat() if row[4] else None
                })
            
            # 备份项目数据
            result = await conn.execute(
                text("SELECT id, name, description, user_id, created_at FROM projects")
            )
            for row in result.fetchall():
                backup_data["projects"].append({
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "user_id": row[3],
                    "created_at": row[4].isoformat() if row[4] else None
                })
            
            # 保存备份文件
            backup_filename = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(os.path.dirname(__file__), backup_filename)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 备份完成！")
            print(f"  备份文件: {backup_path}")
            print(f"  用户数量: {len(backup_data['users'])}")
            print(f"  项目数量: {len(backup_data['projects'])}")
            
    except Exception as e:
        print(f"✗ 备份失败: {str(e)}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(backup_database())