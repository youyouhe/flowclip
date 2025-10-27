#!/bin/bash
# 重启 Flowclip 服务
# 使用 PM2 管理所有服务

echo "重启 Flowclip 服务..."

# 检查 PM2 是否安装
if ! command -v pm2 &> /dev/null; then
    echo "PM2 未安装，请先安装 PM2"
    exit 1
fi

# 检查 ecosystem.config.js 是否存在
if [ ! -f "/home/flowclip/EchoClip/ecosystem.config.js" ]; then
    echo "ecosystem.config.js 文件不存在"
    exit 1
fi

# 使用 PM2 重启所有服务
echo "使用 PM2 重启所有 Flowclip 服务..."
pm2 restart /home/flowclip/EchoClip/ecosystem.config.js

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 显示服务状态
echo "服务状态："
pm2 status

echo ""
echo "服务重启完成！"
echo ""
echo "服务详情："
echo "- flowclip-backend:     后端 API 服务 (端口 8001)"
echo "- flowclip-callback:    TUS 回调服务器 (端口 9090)"
echo "- flowclip-celery-worker: Celery 异步任务处理器"
echo "- flowclip-celery-beat:  Celery 定时任务调度器"
echo "- flowclip-frontend:    前端静态文件服务器 (端口 3000)"
echo "- flowclip-mcp-server:  MCP 服务器 (端口 8002)"
echo ""
echo "日志命令："
echo "- pm2 logs flowclip-backend     # 查看后端日志"
echo "- pm2 logs flowclip-callback    # 查看回调服务日志"
echo "- pm2 logs flowclip-mcp-server  # 查看 MCP 服务日志"
echo "- pm2 logs all                  # 查看所有服务日志"
echo ""
echo "管理命令："
echo "- pm2 status                    # 查看服务状态"
echo "- pm2 restart flowclip-backend  # 重启特定服务"
echo "- pm2 stop flowclip-backend     # 停止特定服务"
echo "- pm2 monit                     # 监控服务性能"