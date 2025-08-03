#!/bin/bash
# 音频处理依赖安装脚本

echo "安装音频处理依赖..."

# 检查操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux (Ubuntu/Debian)
    echo "检测到Linux系统，安装系统依赖..."
    sudo apt-get update
#    sudo apt-get install -y ffmpeg
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "检测到macOS系统，安装系统依赖..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "请先安装Homebrew: https://brew.sh"
        exit 1
    fi
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    echo "检测到Windows系统"
    echo "请手动安装ffmpeg: https://ffmpeg.org/download.html"
    echo "并将ffmpeg添加到系统PATH"
else
    echo "未知操作系统，请手动安装ffmpeg"
fi

# 安装Python依赖
echo "安装Python依赖..."
pip install pydub numpy scikit-learn matplotlib

echo "音频处理依赖安装完成！"
echo "现在可以运行音频分割任务了"
