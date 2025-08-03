#!/usr/bin/env python3
"""
测试 AsyncSessionLocal 修复的脚本
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_async_session_local_import():
    """测试 AsyncSessionLocal 导入"""
    try:
        from app.tasks.video_tasks import extract_audio, AsyncSessionLocal
        print("✓ AsyncSessionLocal 导入成功")
        print("✓ extract_audio 任务导入成功")
        return True
    except NameError as e:
        if "AsyncSessionLocal" in str(e):
            print(f"✗ AsyncSessionLocal 导入失败: {e}")
            return False
        else:
            raise
    except Exception as e:
        print(f"✗ 其他导入错误: {e}")
        return False

def test_celery_connection():
    """测试 Celery 连接"""
    try:
        from app.tasks.video_tasks import add
        result = add.delay(1, 2)
        print(f"✓ Celery 连接成功，任务ID: {result.id}")
        
        # 等待结果
        final_result = result.get(timeout=10)
        print(f"✓ 任务执行成功，结果: {final_result}")
        return True
    except Exception as e:
        print(f"✗ Celery 连接失败: {e}")
        return False

def test_extract_audio_task_import():
    """测试音频提取任务导入"""
    try:
        from app.tasks.video_tasks import extract_audio
        print("✓ extract_audio 任务函数导入成功")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(extract_audio)
        print(f"✓ 函数签名: {sig}")
        return True
    except Exception as e:
        print(f"✗ extract_audio 任务导入失败: {e}")
        return False

if __name__ == "__main__":
    print("=== AsyncSessionLocal 修复验证测试 ===\n")
    
    tests = [
        ("AsyncSessionLocal 导入测试", test_async_session_local_import),
        ("Celery 连接测试", test_celery_connection),
        ("音频提取任务导入测试", test_extract_audio_task_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"正在运行: {test_name}")
        if test_func():
            passed += 1
        print()
    
    print(f"=== 测试结果: {passed}/{total} 通过 ===")
    
    if passed == total:
        print("🎉 所有测试通过！AsyncSessionLocal 修复成功！")
        print("现在可以安全地运行音频提取任务了。")
    else:
        print("❌ 部分测试失败，请检查配置。")
        sys.exit(1)