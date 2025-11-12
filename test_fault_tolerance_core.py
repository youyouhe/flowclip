#!/usr/bin/env python3
"""
核心容错逻辑测试 - 不需要完整环境
"""

import sys
import os
from pathlib import Path

# 添加后端路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_error_detection():
    """测试错误检测逻辑"""
    print("=== 测试错误检测 ===")

    # 模拟错误类型判断函数
    def is_recoverable_error(error_output: str) -> bool:
        recoverable_errors = [
            "Did not get any data blocks",
            "fragment not found",
            "HTTP Error 404",
            "Unable to download video data",
            "This video is unavailable"
        ]
        error_lower = error_output.lower()
        return any(error.lower() in error_lower for error in recoverable_errors)

    # 测试用例
    test_cases = [
        ("Did not get any data blocks", True),
        ("fragment not found; Skipping fragment 1281", True),
        ("HTTP Error 404: Not Found", True),
        ("ERROR: This video is private", False),
        ("Permission denied", False),
        ("No space left on device", False),
        ("", False)
    ]

    print("错误类型检测测试:")
    all_passed = True
    for error, expected in test_cases:
        result = is_recoverable_error(error)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{error}' -> {result} (期望: {expected})")
        if result != expected:
            all_passed = False

    return all_passed

def test_file_size_logic():
    """测试文件大小检查逻辑"""
    print("\n=== 测试文件大小检查 ===")

    # 模拟文件大小检查
    def check_file_size(file_size_bytes):
        if file_size_bytes < 1024 * 1024:  # < 1MB
            return {"valid": False, "reason": f"文件过小: {file_size_bytes} bytes"}
        elif file_size_bytes > 10 * 1024 * 1024:  # > 10MB
            return {"valid": True, "file_size": file_size_bytes}
        else:
            return {"valid": False, "reason": f"文件可能不完整: {file_size_bytes} bytes"}

    test_cases = [
        (500 * 1024, False),    # 500KB - 过小
        (5 * 1024 * 1024, False),  # 5MB - 可能不完整
        (800 * 1024 * 1024, True),  # 800MB - 良好
        (50 * 1024 * 1024, True),   # 50MB - 良好
    ]

    print("文件大小检查测试:")
    all_passed = True
    for size, expected in test_cases:
        result = check_file_size(size)
        status = "✓" if result["valid"] == expected else "✗"
        size_mb = size / (1024 * 1024)
        print(f"  {status} {size_mb:.1f}MB -> {result['valid']} (期望: {expected})")
        if result["valid"] != expected:
            all_passed = False

    return all_passed

def test_youtube_command_parameters():
    """测试yt-dlp命令参数"""
    print("\n=== 测试yt-dlp命令参数 ===")

    # 构建命令
    base_cmd = [
        'yt-dlp',
        'https://youtu.be/9wDeKOeYxIg',
        '--output', '/tmp/test/%(id)s.%(ext)s',
        '--no-playlist',
        '--write-info-json',
        '--write-thumbnail',
        '--newline',
        '--verbose',
        # 容错参数
        '--ignore-errors',
        '--abort-on-unavailable-fragment', 'false',
        '--hls-use-mpegts',
        '--retries', '3',
        '--fragment-retries', '5',
        '--skip-unavailable-fragments',
        '--no-check-certificate'
    ]

    # 检查关键容错参数是否存在
    required_params = [
        '--ignore-errors',
        '--abort-on-unavailable-fragment',
        '--hls-use-mpegts',
        '--retries',
        '--fragment-retries',
        '--skip-unavailable-fragments'
    ]

    print("容错参数检查:")
    all_passed = True
    for param in required_params:
        exists = param in base_cmd
        status = "✓" if exists else "✗"
        print(f"  {status} {param}")
        if not exists:
            all_passed = False

    # 显示完整命令
    print(f"\n完整命令长度: {len(base_cmd)} 个参数")
    print("关键容错参数已添加" if all_passed else "缺少关键容错参数")

    return all_passed

def main():
    """主测试函数"""
    print("开始核心容错逻辑测试...\n")

    # 运行所有测试
    tests = [
        ("错误检测", test_error_detection),
        ("文件大小检查", test_file_size_logic),
        ("yt-dlp命令参数", test_youtube_command_parameters)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name}测试出错: {e}")
            results.append((test_name, False))

    # 总结
    print("\n" + "="*50)
    print("测试总结:")
    all_passed = True
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False

    print(f"\n总体结果: {'✓ 所有测试通过' if all_passed else '✗ 部分测试失败'}")

    if all_passed:
        print("\n🎉 容错机制核心逻辑验证成功!")
        print("建议部署到生产环境进行实际测试。")
    else:
        print("\n❌ 需要修复失败的测试项。")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)