#!/usr/bin/env python3
"""
MinIO授权问题修复验证脚本
用于测试MinIO客户端配置和URL生成
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.minio_client import minio_service
from app.core.config import settings

async def test_minio_configuration():
    """测试MinIO配置和授权问题"""
    print("🔧 MinIO授权问题修复验证")
    print("=" * 50)
    
    # 测试连接
    print("📡 测试MinIO连接...")
    try:
        test_result = await minio_service.test_connection()
        print(f"✅ 连接状态: {test_result}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False
    
    # 测试桶创建
    print("\n📁 测试桶操作...")
    try:
        bucket_result = await minio_service.ensure_bucket_exists()
        print(f"✅ 桶创建结果: {bucket_result}")
    except Exception as e:
        print(f"❌ 桶操作失败: {e}")
        return False
    
    # 测试文件上传和URL生成
    print("\n🔄 测试文件上传和URL生成...")
    try:
        test_content = b"Hello MinIO - Authorization Test"
        test_object = "test/authorization_test.txt"
        
        # 上传测试文件
        upload_result = await minio_service.upload_file_content(
            test_content, test_object, "text/plain"
        )
        print(f"✅ 文件上传成功: {upload_result}")
        
        # 测试URL生成
        url = await minio_service.get_file_url(test_object, 3600)
        print(f"✅ 预签名URL生成成功: {url}")
        
        if url:
            # 测试URL访问
            import requests
            response = requests.get(url)
            print(f"✅ URL访问测试: 状态码 {response.status_code}")
            if response.status_code == 200:
                print(f"✅ URL内容验证: {response.text}")
            else:
                print(f"❌ URL访问失败: {response.text}")
        
        # 清理测试文件
        await minio_service.delete_file(test_object)
        print("✅ 测试文件已清理")
        
    except Exception as e:
        print(f"❌ 文件操作失败: {e}")
        return False
    
    print("\n🎉 所有测试通过！MinIO授权问题已修复")
    return True

async def main():
    """主函数"""
    print(f"MinIO端点: {settings.minio_endpoint}")
    print(f"MinIO桶名: {settings.minio_bucket_name}")
    print(f"MinIO安全模式: {settings.minio_secure}")
    print()
    
    try:
        success = await test_minio_configuration()
        if success:
            print("\n✅ MinIO配置验证完成，授权问题已解决")
        else:
            print("\n❌ MinIO配置验证失败")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())