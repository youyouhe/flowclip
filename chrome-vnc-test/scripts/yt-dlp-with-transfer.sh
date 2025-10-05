#!/bin/bash

# 配置
VIDEO_URL="$1"
LOCAL_IP="$2"  # 你的本地IP
LOCAL_USER="$3"  # 你的本地用户名
LOCAL_PATH="$4"  # 本地保存路径
SSH_PORT="$5"    # 本地SSH端口，默认22

# 设置默认值
SSH_PORT=${SSH_PORT:-22}
COOKIE_FILE="/headless/Downloads/cookie.txt"

echo "开始从Firefox导出cookie并下载视频..."
echo "视频URL: $VIDEO_URL"
echo "本地IP: $LOCAL_IP"
echo "本地路径: $LOCAL_PATH"

# 执行yt-dlp，从Firefox导出cookie并下载
echo "正在从Firefox导出cookie并分析视频..."
yt-dlp --cookies-from-browser firefox --cookies "$COOKIE_FILE" -F "$VIDEO_URL"

if [ $? -eq 0 ]; then
    echo "cookie文件已生成"

    # 检查cookie文件是否存在
    if [ -f "$COOKIE_FILE" ]; then
        echo "正在传输cookie文件到本地..."

        # 尝试传输cookie文件
        scp -P "$SSH_PORT" "$COOKIE_FILE" "$LOCAL_USER@$LOCAL_IP:$LOCAL_PATH/"

        if [ $? -eq 0 ]; then
            echo "✅ cookie.txt已成功传输到: $LOCAL_USER@$LOCAL_IP:$LOCAL_PATH/"
            echo "现在你可以在本地使用这个cookie文件下载视频了"
        else
            echo "❌ cookie文件传输失败"
            echo "请确保:"
            echo "1. 本地SSH服务已启动"
            echo "2. 防火墙允许端口$SSH_PORT"
            echo "3. 已配置SSH免密登录或准备好密码"
            echo "4. 可以手动从容器复制: $COOKIE_FILE"
        fi
    else
        echo "❌ cookie文件未生成，可能Firefox没有相关cookie"
    fi
else
    echo "❌ yt-dlp执行失败"
fi