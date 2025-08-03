#!/usr/bin/env python3
"""
创建测试用户
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/home/cat/github/slice-youtube/backend')

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy import select

async def create_test_user():
    """创建测试用户"""
    print("开始创建测试用户...")
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查用户是否已存在
            stmt = select(User).where(User.email == "admin@example.com")
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                print(f"测试用户已存在: {user.username} (ID: {user.id})")
                return
            
            # 创建新用户
            new_user = User(
                email="admin@example.com",
                username="admin",
                full_name="Admin User",
                hashed_password=get_password_hash("password123"),
                is_active=True,
                is_superuser=True
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            
            print(f"测试用户创建成功: {new_user.username} (ID: {new_user.id})")
            
        except Exception as e:
            print(f"创建测试用户失败: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_test_user())