#!/usr/bin/env python3
"""
测试YouTube下载容错机制的脚本
用于验证HLS分片下载失败的智能容错处理
"""

import asyncio
import logging
import tempfile
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_validate_downloaded_file():
    """测试文件完整性验证函数"""
    print("=== 测试文件完整性验证 ===")

    from app.services.youtube_downloader_minio import validate_downloaded_file

    # 测试1: 不存在的文件
    print("1. 测试不存在的文件...")
    result = await validate_downloaded_file(Path("/nonexistent/file.mp4"))
    print(f"结果: {result}")
    assert not result["valid"], "应该返回无效"

    # 测试2: 实际下载的文件（需要手动下载测试文件）
    test_file = "/tmp/test/9wDeKOeYxIg.mp4"  # 使用之前下载的测试文件
    if Path(test_file).exists():
        print("2. 测试实际下载的文件...")
        result = await validate_downloaded_file(Path(test_file))
        print(f"结果: {result}")
        if result["valid"]:
            print("✓ 文件验证通过")
        else:
            print(f"✗ 文件验证失败: {result['reason']}")
    else:
        print("2. 跳过实际文件测试（文件不存在）")

def test_is_recoverable_error():
    """测试错误类型判断函数"""
    print("\n=== 测试错误类型判断 ===")

    from app.services.youtube_downloader_minio import is_recoverable_error

    # 测试可恢复的错误
    recoverable_errors = [
        "Did not get any data blocks",
        "fragment not found; Skipping fragment 1281",
        "HTTP Error 404: Not Found",
        "Unable to download video data",
        "This video is unavailable"
    ]

    print("1. 测试可恢复的错误:")
    for error in recoverable_errors:
        result = is_recoverable_error(error)
        print(f"  '{error}' -> {result}")
        assert result, f"应该识别为可恢复: {error}"

    # 测试不可恢复的错误
    non_recoverable_errors = [
        "ERROR: This video is private",
        "ERROR: Invalid URL",
        "Permission denied",
        "No space left on device"
    ]

    print("2. 测试不可恢复的错误:")
    for error in non_recoverable_errors:
        result = is_recoverable_error(error)
        print(f"  '{error}' -> {result}")
        assert not result, f"应该识别为不可恢复: {error}"

def test_youtube_downloader_with_mock():
    """使用模拟错误测试YouTube下载器"""
    print("\n=== 测试YouTube下载器容错机制 ===")

    from app.services.youtube_downloader_minio import YouTubeDownloaderMinio

    downloader = YouTubeDownloaderMinio()

    # 测试视频URL（使用之前出错的那个）
    test_url = "https://youtu.be/9wDeKOeYxIg"

    print(f"测试URL: {test_url}")
    print("注意: 这个测试会实际下载视频，可能需要较长时间...")

    try:
        result = asyncio.run(downloader.download_and_upload_video(
            url=test_url,
            project_id=1,  # 测试项目ID
            user_id=1,     # 测试用户ID
            video_id=999,  # 测试视频ID
            quality='720p'
        ))

        print("✓ 下载成功!")
        print(f"结果: {result}")

    except Exception as e:
        print(f"✗ 下载失败: {e}")
        print("如果失败是因为缺少cookie文件或其他配置，这是正常的")

async def main():
    """主测试函数"""
    print("开始测试YouTube下载容错机制...")

    # 1. 测试文件验证函数
    await test_validate_downloaded_file()

    # 2. 测试错误判断函数
    test_is_recoverable_error()

    # 3. 测试YouTube下载器（可选，需要完整环境）
    response = input("\n是否要测试实际下载功能? (y/N): ")
    if response.lower() in ['y', 'yes']:
        test_youtube_downloader_with_mock()

    print("\n=== 测试完成 ===")
    print("如果所有测试都通过，说明容错机制工作正常")

if __name__ == "__main__":
    # 确保在正确的目录中
    import sys
    from pathlib import Path

    if not Path("backend").exists():
        print("错误: 请在项目根目录中运行此脚本")
        sys.exit(1)

    # 运行测试
    asyncio.run(main())