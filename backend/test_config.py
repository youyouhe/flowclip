#!/usr/bin/env python3
"""
测试 config.py 配置加载
"""
import sys
import os

# 添加项目路径到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_loading():
    """测试配置加载"""
    try:
        # 导入配置
        from app.core.config import settings

        print("✅ 配置加载成功！")
        print(f"📊 数据库URL: {settings.database_url}")
        print(f"🔧 MySQL配置: {settings.mysql_host}:{settings.mysql_port}")
        print(f"🔴 Redis URL: {settings.redis_url}")
        print(f"💾 MinIO配置: {settings.minio_endpoint}")
        print(f"🌐 前端URL: {settings.frontend_url}")
        print(f"🔍 Debug模式: {settings.debug}")
        print(f"📁 TUS阈值: {settings.tus_file_size_threshold_mb}MB")

        # 检查关键配置是否存在
        if settings.database_url and settings.redis_url and settings.minio_endpoint:
            print("✅ 所有关键配置都已正确加载")
            return True
        else:
            print("❌ 部分关键配置缺失")
            return False

    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_config_loading()
    sys.exit(0 if success else 1)