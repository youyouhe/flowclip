#!/usr/bin/env python3
"""
检查音频处理依赖是否安装
"""

import sys
import subprocess

def check_ffmpeg():
    """检查ffmpeg是否安装"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ ffmpeg 已安装")
            return True
        else:
            print("✗ ffmpeg 未安装或不可用")
            return False
    except FileNotFoundError:
        print("✗ ffmpeg 未安装")
        return False

def check_pydub():
    """检查pydub是否安装"""
    try:
        from pydub import AudioSegment
        print("✓ pydub 已安装")
        return True
    except ImportError:
        print("✗ pydub 未安装")
        return False

def check_sklearn():
    """检查scikit-learn是否安装"""
    try:
        import sklearn
        print("✓ scikit-learn 已安装")
        return True
    except ImportError:
        print("✗ scikit-learn 未安装 (可选，用于音频分割的聚类功能)")
        return False

def check_numpy():
    """检查numpy是否安装"""
    try:
        import numpy as np
        print("✓ numpy 已安装")
        return True
    except ImportError:
        print("✗ numpy 未安装")
        return False

def check_matplotlib():
    """检查matplotlib是否安装"""
    try:
        import matplotlib
        print("✓ matplotlib 已安装 (用于调试模式)")
        return True
    except ImportError:
        print("✗ matplotlib 未安装 (可选，用于调试模式)")
        return False

def main():
    print("检查音频处理依赖...")
    print("=" * 40)
    
    dependencies = [
        ("ffmpeg", check_ffmpeg),
        ("pydub", check_pydub),
        ("numpy", check_numpy),
        ("scikit-learn", check_sklearn),
        ("matplotlib", check_matplotlib),
    ]
    
    missing = []
    
    for name, check_func in dependencies:
        print(f"\n检查 {name}...")
        if not check_func():
            if name != "scikit-learn" and name != "matplotlib":  # 可选依赖
                missing.append(name)
    
    print("\n" + "=" * 40)
    if missing:
        print("缺失的必要依赖:")
        for dep in missing:
            print(f"  - {dep}")
        print("\n安装命令:")
        if "pydub" in missing:
            print("  pip install pydub")
        if "numpy" in missing:
            print("  pip install numpy")
        if "scikit-learn" in missing:
            print("  pip install scikit-learn")
        if "matplotlib" in missing:
            print("  pip install matplotlib")
        if "ffmpeg" in missing:
            print("  # Ubuntu/Debian:")
            print("  sudo apt-get install ffmpeg")
            print("  # macOS:")
            print("  brew install ffmpeg")
            print("  # Windows:")
            print("  下载并安装 https://ffmpeg.org/download.html")
    else:
        print("✓ 所有必要依赖都已安装")
    
    return len(missing) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)