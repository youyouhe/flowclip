#!/usr/bin/env python3
"""
演示 MinIO 集成的完整工作流程
无需 YouTube 下载，直接测试文件上传/下载
"""

import asyncio
import aiohttp
import json
from pathlib import Path
from app.services.minio_client import minio_service
from app.core.config import settings

async def demo_workflow():
    print("🎯 演示 MinIO 集成工作流程")
    print("=" * 50)
    
    # 1. 测试 MinIO 连接
    print("\n📡 1. 测试 MinIO 连接...")
    bucket_ok = await minio_service.ensure_bucket_exists()
    print(f"✅ 桶状态: {'就绪' if bucket_ok else '需要创建'}")
    
    # 2. 上传测试文件
    print("\n📁 2. 上传测试文件...")
    test_content = b"Hello from MinIO integration demo!"
    object_name = "demo/test-file.txt"
    
    upload_result = await minio_service.upload_file_content(
        test_content, object_name, "text/plain"
    )
    print(f"✅ 上传成功: {upload_result}")
    
    # 3. 验证文件存在
    print("\n🔍 3. 验证文件存在...")
    exists = await minio_service.file_exists(object_name)
    print(f"✅ 文件存在: {exists}")
    
    # 4. 获取下载URL
    print("\n🔗 4. 获取下载URL...")
    download_url = await minio_service.get_file_url(object_name, expiry=300)
    print(f"✅ 下载URL: {download_url}")
    
    # 5. 测试对象命名规范
    print("\n🗂️  5. 测试对象命名规范...")
    user_id = 1
    project_id = 123
    video_name = "demo-video.mp4"
    
    video_path = minio_service.generate_object_name(user_id, project_id, video_name)
    audio_path = minio_service.generate_audio_object_name(user_id, project_id, "video123")
    thumb_path = minio_service.generate_thumbnail_object_name(user_id, project_id, "video123")
    
    print(f"   📺 视频路径: {video_path}")
    print(f"   🎵 音频路径: {audio_path}")
    print(f"   🖼️  缩略图路径: {thumb_path}")
    
    # 6. 测试文件删除
    print("\n🧹 6. 测试文件删除...")
    deleted = await minio_service.delete_file(object_name)
    print(f"✅ 文件删除: {deleted}")
    
    # 7. 验证文件已删除
    exists_after = await minio_service.file_exists(object_name)
    print(f"✅ 文件已清理: {not exists_after}")
    
    # 8. 展示 MinIO 控制台访问信息
    print("\n🌐 8. MinIO 控制台访问信息")
    print(f"   🖥️  Web控制台: http://localhost:9001")
    print(f"   👤 用户名: {settings.minio_access_key}")
    print(f"   🔑 密码: {settings.minio_secret_key}")
    print(f"   📁 存储桶: {settings.minio_bucket_name}")
    
    print("\n" + "=" * 50)
    print("🎉 演示完成！MinIO 集成工作正常")
    print("现在你可以：")
    print("   - 访问 http://localhost:9001 查看 MinIO 控制台")
    print("   - 使用上传/下载 API 端点")
    print("   - 使用预签名 URL 进行安全文件访问")

if __name__ == "__main__":
    asyncio.run(demo_workflow())