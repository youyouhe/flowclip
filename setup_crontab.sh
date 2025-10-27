#!/bin/bash

# 设置清理超期视频的定时任务
# 每2小时执行一次清理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_SCRIPT="$SCRIPT_DIR/cleanup_expired_videos.py"
LOG_FILE="$SCRIPT_DIR/cleanup_videos.log"

# 确保脚本存在且有执行权限
if [ ! -f "$CLEANUP_SCRIPT" ]; then
    echo "错误: 清理脚本不存在: $CLEANUP_SCRIPT"
    exit 1
fi

if [ ! -x "$CLEANUP_SCRIPT" ]; then
    echo "错误: 清理脚本没有执行权限: $CLEANUP_SCRIPT"
    chmod +x "$CLEANUP_SCRIPT"
fi

# 创建crontab任务
# 每2小时的第0分钟执行一次（例如: 00:00, 02:00, 04:00, ...）
CRON_ENTRY="0 */2 * * * cd $SCRIPT_DIR && /usr/bin/python3 $CLEANUP_SCRIPT >> $LOG_FILE 2>&1"

echo "设置crontab任务..."
echo "任务内容: $CRON_ENTRY"

# 检查是否已存在相同的任务
if crontab -l 2>/dev/null | grep -F "cleanup_expired_videos.py" > /dev/null; then
    echo "发现已存在的清理任务，正在移除..."
    # 移除旧的任务
    crontab -l 2>/dev/null | grep -v "cleanup_expired_videos.py" | crontab -
fi

# 添加新的任务
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✓ crontab任务设置成功！"
echo ""
echo "任务详情:"
echo "  - 执行频率: 每2小时"
echo "  - 脚本路径: $CLEANUP_SCRIPT"
echo "  - 日志文件: $LOG_FILE"
echo "  - 下次执行: $(date -d "+2 hours" '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "查看当前crontab任务: crontab -l"
echo "查看日志: tail -f $LOG_FILE"
echo "移除任务: crontab -e (删除相关行)"

# 测试脚本是否能正常运行
echo ""
echo "是否要测试脚本运行？(y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo "正在测试脚本（试运行模式）..."
    cd "$SCRIPT_DIR" || exit 1
    python3 "$CLEANUP_SCRIPT" --dry-run
    echo "测试完成！"
fi