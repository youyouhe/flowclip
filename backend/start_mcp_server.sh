#!/bin/bash
# 启动MCP服务器的脚本

echo "正在启动Flowclip MCP服务器..."

# 激活conda环境
source /home/cat/miniconda3/bin/activate youtube-slicer

# 进入backend目录并启动MCP服务器
cd /home/cat/EchoClip/backend
python run_mcp_server.py

echo "MCP服务器已启动，监听端口8002"