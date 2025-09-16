#!/usr/bin/env python3
"""
测试URL编码修复的脚本
"""
import os
import sys

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.tasks.subtasks.capcut_task import _get_proxy_url

def test_url_encoding():
    """测试URL编码是否正确"""
    print("=== 测试URL编码修复 ===")

    # 测试包含中文的资源路径
    test_paths = [
        "default_resources/片尾_ea6e89f555de4094a18c381b5f506326.mp4",
        "default_resources/水波纹_1234567890abcdef.mp3",
        "videos/test_video.mp4"
    ]

    for path in test_paths:
        print(f"\n测试路径: {path}")
        try:
            url = _get_proxy_url(path)
            print(f"生成的URL: {url}")

            # 检查是否有双重编码的迹象
            if '%25' in url:
                print("❌ 发现双重编码问题!")
            else:
                print("✅ URL编码正常")

        except Exception as e:
            print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_url_encoding()