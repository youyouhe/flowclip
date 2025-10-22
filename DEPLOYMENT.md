# Flowclip 多环境部署指南

## 概述

本文档说明如何在不同环境中部署和配置 Flowclip 系统。

## 环境变量配置

### 方法一：使用环境变量 (推荐)

在运行安装脚本前设置环境变量：

```bash
# 基础配置
export PROJECT_NAME="flowclip"          # 项目名称
export PROJECT_USER="your_username"      # 系统用户名
export PROJECT_DIR="/path/to/project"   # 项目目录路径

# 数据库配置
export CREDENTIALS_FILE="/path/to/credentials.txt"  # 凭据文件路径

# 运行安装脚本
./install_user.sh
```

## 主要配置项

### 1. 路径配置

| 变量 | 默认值 | 说明 |
|--------|----------|------|
| \`PROJECT_NAME\` | \`flowclip\` | 项目名称 |
| \`PROJECT_USER\` | \\\$(whoami) | 系统用户名 |
| \`PROJECT_DIR\` | \`/home/\\$PROJECT_USER/EchoClip\` | 项目根目录 |

### 2. 网络配置

| 变量 | 默认值 | 说明 |
|--------|----------|------|
| \`SERVER_IP\` | \`自动检测\` | 服务器IP地址 |
| \`BACKEND_PORT\` | \`8001\` | 后端API端口 |
| \`FRONTEND_PORT\` | \`3000\` | 前端服务端口 |

## 部署步骤

### 新环境部署

1. **准备环境**
\`\`\`bash
# 确保已安装系统依赖
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm redis-server mysql-server
\`\`\`

2. **配置环境变量**
\`\`\`bash
# 创建配置文件
cat > deployment.env << EOF
PROJECT_NAME=flowclip
PROJECT_USER=myuser
PROJECT_DIR=/home/myuser/EchoClip
SERVER_IP=192.168.1.100
