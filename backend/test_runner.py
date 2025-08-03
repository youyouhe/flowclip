#!/usr/bin/env python3
"""
测试运行器脚本
运行所有MinIO相关的测试
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_tests():
    """运行所有测试"""
    
    parser = argparse.ArgumentParser(description='运行MinIO集成测试')
    parser.add_argument('--integration', action='store_true', 
                       help='运行集成测试（需要MinIO服务）')
    parser.add_argument('--unit', action='store_true',
                       help='仅运行单元测试')
    parser.add_argument('--coverage', action='store_true',
                       help='生成测试覆盖率报告')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    # 设置测试环境
    os.environ['PYTHONPATH'] = str(Path(__file__).parent)
    
    # 测试命令
    cmd = [sys.executable, "-m", "pytest"]
    
    if args.verbose:
        cmd.append("-v")
    
    if args.unit:
        cmd.extend(["-m", "unit"])
    elif args.integration:
        cmd.extend(["-m", "integration"])
        os.environ['INTEGRATION_TESTS'] = "1"
    else:
        # 默认运行所有非集成测试
        cmd.extend(["-m", "not integration"])
    
    if args.coverage:
        cmd.extend([
            "--cov=app.services",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # 添加测试文件
    cmd.extend([
        "tests/test_minio_service.py",
        "tests/test_youtube_downloader_minio.py",
        "tests/test_video_api.py"
    ])
    
    print(f"运行测试命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n测试被中断")
        return 1
    except Exception as e:
        print(f"运行测试时出错: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)