#!/bin/bash

# Flowclip 用户环境配置脚本
# 负责安装Python依赖、配置应用环境、启动服务等用户级操作

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目配置 - 支持环境变量自定义
PROJECT_NAME="${PROJECT_NAME:-flowclip}"
PROJECT_USER="${PROJECT_USER:-$(whoami)}"
PROJECT_DIR="${PROJECT_DIR:-/home/$PROJECT_USER/EchoClip}"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
CREDENTIALS_FILE="${CREDENTIALS_FILE:-/home/$PROJECT_USER/credentials.txt}"
REPO_URL="https://github.com/youyouhe/flowclip.git"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 克隆项目代码
clone_project() {
    log_info "克隆项目代码..."

    # 如果项目目录已存在且有内容，先备份
    if [[ -d "$PROJECT_DIR" ]] && [[ "$(ls -A "$PROJECT_DIR" 2>/dev/null)" ]]; then
        log_warning "项目目录已存在，创建备份..."
        local backup_dir="${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        mv "$PROJECT_DIR" "$backup_dir"
        log_info "原目录已备份到: $backup_dir"
    fi

    # 创建项目目录
    mkdir -p "$PROJECT_DIR"

    # 克隆项目
    cd "$(dirname "$PROJECT_DIR")"
    if git clone "$REPO_URL" EchoClip; then
        log_success "项目代码克隆成功"
    else
        log_error "项目代码克隆失败"
        exit 1
    fi

    # 设置权限
    chown -R "$(whoami):$(whoami)" "$PROJECT_DIR"
}

# 读取凭据文件
load_credentials() {
    log_info "读取系统凭据..."

    # 先尝试从用户目录读取 (install_root.sh 已复制到这里)
    if [[ -f "$CREDENTIALS_FILE" ]]; then
        log_info "从用户凭据文件读取: $CREDENTIALS_FILE"
    else
        log_warning "用户目录没有凭据文件，检查其他位置..."

        # 检查 install_root.sh 是否已复制凭据文件
        if [[ -f "/root/flowclip_credentials.txt" ]]; then
            log_info "发现 root 目录凭据文件，复制到用户目录..."
            if cp "/root/flowclip_credentials.txt" "$CREDENTIALS_FILE"; then
                log_success "凭据文件复制成功"
                chmod 600 "$CREDENTIALS_FILE"
            else
                log_error "凭据文件复制失败"
                exit 1
            fi
        else
            log_error "凭据文件不存在，请先运行 root 安装脚本"
            log_error "预期文件位置: /root/flowclip_credentials.txt"
            log_error "或使用完整安装脚本: sudo bash install_all.sh"
            exit 1
        fi
    fi

    # 读取凭据 - 使用标准化的KEY=VALUE格式
    if [[ -f "$CREDENTIALS_FILE" ]]; then
        log_info "解析凭据文件: $CREDENTIALS_FILE"

        # 显示凭据文件前几行用于调试
        log_info "凭据文件内容预览:"
        head -5 "$CREDENTIALS_FILE" | while IFS= read -r line; do
            log_info "  $line"
        done

        # 读取凭据 - 使用标准化的KEY=VALUE格式
        MYSQL_APP_PASSWORD=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
        MINIO_ACCESS_KEY=$(grep "^MINIO_ACCESS_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
        MINIO_SECRET_KEY=$(grep "^MINIO_SECRET_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
        APP_SECRET_KEY=$(grep "^SECRET_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)

        # 验证解析结果
        log_info "凭据解析结果:"
        log_info "  MySQL密码长度: ${#MYSQL_APP_PASSWORD}"
        log_info "  MinIO访问密钥长度: ${#MINIO_ACCESS_KEY}"
        log_info "  MinIO秘密密钥长度: ${#MINIO_SECRET_KEY}"
        log_info "  应用密钥长度: ${#APP_SECRET_KEY}"
    else
        log_error "凭据文件不存在: $CREDENTIALS_FILE"
        exit 1
    fi

    # 验证凭据是否读取成功
    if [[ -z "$MYSQL_APP_PASSWORD" ]] || [[ -z "$MINIO_ACCESS_KEY" ]] || [[ -z "$MINIO_SECRET_KEY" ]]; then
        log_error "凭据文件解析失败"
        log_error "请检查凭据文件格式: $CREDENTIALS_FILE"
        exit 1
    fi

    log_success "系统凭据读取完成"
}

# 检查项目目录
check_project_directory() {
    log_info "检查项目目录..."

    if [[ ! -d "$PROJECT_DIR" ]]; then
        log_error "项目目录不存在: $PROJECT_DIR"
        log_info "请确保项目代码已复制到正确位置"
        exit 1
    fi

    if [[ ! -d "$BACKEND_DIR" ]]; then
        log_error "后端目录不存在: $BACKEND_DIR"
        exit 1
    fi

    if [[ ! -d "$FRONTEND_DIR" ]]; then
        log_error "前端目录不存在: $FRONTEND_DIR"
        exit 1
    fi

    log_success "项目目录检查通过"
}

# 检查系统依赖
check_system_dependencies() {
    log_info "检查系统依赖..."

    local missing_deps=()

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    # 检查 pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("pip3")
    fi

    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        missing_deps+=("node")
    fi

    # 检查 npm
    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    # 检查 Redis
    if ! redis-cli ping &> /dev/null; then
        log_warning "Redis 服务未运行，请检查 Redis 配置"
    fi

    # 检查 MySQL
    if [[ -n "$MYSQL_APP_PASSWORD" ]]; then
        if ! mysql -uyoutube_user -p"$MYSQL_APP_PASSWORD" -e "SELECT 1;" &> /dev/null; then
            log_warning "MySQL 连接失败，请检查数据库配置"
        else
            log_success "MySQL 连接验证成功"
        fi
    else
        log_warning "MySQL 凭据未加载"
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "缺少系统依赖: ${missing_deps[*]}"
        log_info "请运行 root 安装脚本安装缺失的依赖"
        exit 1
    fi

    log_success "系统依赖检查通过"
}

# 配置 Python 虚拟环境
setup_python_env() {
    log_info "配置 Python 虚拟环境..."

    cd "$PROJECT_DIR"

    # 创建虚拟环境
    if [[ ! -d "venv" ]]; then
        log_info "创建 Python 虚拟环境..."
        python3 -m venv venv
    fi

    # 激活虚拟环境
    source venv/bin/activate

    # 升级 pip
    pip install --upgrade pip

    log_success "Python 虚拟环境配置完成"
}

# 安装后端依赖
install_backend_dependencies() {
    log_info "安装后端 Python 依赖..."

    cd "$BACKEND_DIR"

    # 激活虚拟环境
    source "$PROJECT_DIR/venv/bin/activate"

    # 安装基础依赖
    if [[ -f "requirements.txt" ]]; then
        log_info "安装 requirements.txt..."
        pip install -r requirements.txt
    fi

    # 安装音频处理依赖
    if [[ -f "requirements-audio.txt" ]]; then
        log_info "安装 requirements-audio.txt..."
        pip install -r requirements-audio.txt
    fi

    log_success "后端依赖安装完成"
}

# 创建环境配置文件
create_env_file() {
    log_info "创建应用环境配置文件..."

    local server_ip=$(hostname -I | awk '{print $1}')

    # 创建 .env 文件
    cat > "$PROJECT_DIR/.env" << EOF
# Server Configuration
PUBLIC_IP=$server_ip

# Frontend URL (where users access the application)
FRONTEND_URL=http://$server_ip:3000

# Backend API URL (used by frontend to call backend)
API_URL=http://$server_ip:8001

# Database Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:$MYSQL_APP_PASSWORD@localhost:3306/youtube_slicer?charset=utf8mb4

# Redis Configuration
REDIS_URL=redis://localhost:6379

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY
MINIO_SECRET_KEY=$MINIO_SECRET_KEY
MINIO_BUCKET_NAME=youtube-videos

# Security
SECRET_KEY=$APP_SECRET_KEY

# OpenAI API Key (for AI features)
OPENAI_API_KEY=your-openai-api-key

# Debug mode (set to false in production)
DEBUG=true
EOF

    log_success "环境配置文件创建完成"
}

# 更新环境配置文件
update_env_file() {
    log_info "更新应用环境配置文件..."

    # 检查.env文件是否存在
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        log_warning ".env文件不存在，将创建新文件"
        create_env_file
        return
    fi

    # 重新读取凭据（确保使用最新值）- 使用标准化的KEY=VALUE格式
    local mysql_password=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
    local minio_access_key=$(grep "^MINIO_ACCESS_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
    local minio_secret_key=$(grep "^MINIO_SECRET_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
    local app_secret_key=$(grep "^SECRET_KEY=" "$CREDENTIALS_FILE" | cut -d'=' -f2)
    local server_ip=$(hostname -I | awk '{print $1}')

    # 更新.env文件中的敏感配置
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=mysql+aiomysql://youtube_user:$mysql_password@localhost:3306/youtube_slicer?charset=utf8mb4|" "$PROJECT_DIR/.env"
    sed -i "s|MINIO_ACCESS_KEY=.*|MINIO_ACCESS_KEY=$minio_access_key|" "$PROJECT_DIR/.env"
    sed -i "s|MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=$minio_secret_key|" "$PROJECT_DIR/.env"
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$app_secret_key|" "$PROJECT_DIR/.env"
    sed -i "s|PUBLIC_IP=.*|PUBLIC_IP=$server_ip|" "$PROJECT_DIR/.env"
    sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=http://$server_ip:3000|" "$PROJECT_DIR/.env"
    sed -i "s|API_URL=.*|API_URL=http://$server_ip:8001|" "$PROJECT_DIR/.env"

    log_success "环境配置文件更新完成"

    # 验证解析结果
    log_info "验证凭据解析结果..."
    log_info "MySQL密码长度: ${#mysql_password}"
    log_info "MinIO访问密钥长度: ${#minio_access_key}"
    log_info "MinIO秘密密钥长度: ${#minio_secret_key}"
    log_info "应用密钥长度: ${#app_secret_key}"
}

# 配置数据库
setup_database() {
    log_info "配置数据库..."

    cd "$BACKEND_DIR"

    # 激活虚拟环境
    source "$PROJECT_DIR/venv/bin/activate"

    # 测试数据库连接
    log_info "测试数据库连接..."
    if python -c "
import pymysql
try:
    conn = pymysql.connect(
        host='localhost',
        user='youtube_user',
        password='$MYSQL_APP_PASSWORD',
        database='youtube_slicer',
        charset='utf8mb4'
    )
    print('✓ 数据库连接测试成功')
    conn.close()
except Exception as e:
    print(f'✗ 数据库连接测试失败: {e}')
    exit(1)
"; then
        log_success "数据库连接验证成功"
    else
        log_error "数据库连接验证失败"
        return 1
    fi

    # 创建测试用户（如果脚本存在）
    if [[ -f "create_test_user.py" ]]; then
        log_info "创建测试用户..."
        python create_test_user.py
    fi

    log_success "数据库配置完成"
    log_info "业务表将在应用启动时通过 create_tables() 自动创建"
}

# 安装前端依赖
install_frontend_dependencies() {
    log_info "安装前端 Node.js 依赖..."

    cd "$FRONTEND_DIR"

    # 安装依赖
    npm install --legacy-peer-deps

    log_success "前端依赖安装完成"
}

# 创建 PM2 配置文件
create_pm2_config() {
    log_info "创建 PM2 配置文件..."

    cd "$PROJECT_DIR"

    # 创建 PM2 配置文件
    # 检测服务器IP
    local server_ip=$(hostname -I | awk '{print $1}')

    cat > ecosystem.config.js << EOF
module.exports = {
  apps: [
    {
      name: 'backend-api',
      script: './backend/start_services.py',
      cwd: '$PROJECT_DIR',
      interpreter: '$PROJECT_DIR/venv/bin/python',
      interpreter_args: '-u',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        DATABASE_URL: 'mysql+aiomysql://youtube_user:$MYSQL_APP_PASSWORD@localhost:3306/youtube_slicer?charset=utf8mb4',
        REDIS_URL: 'redis://localhost:6379',
        MINIO_ENDPOINT: 'localhost:9000',
        MINIO_ACCESS_KEY: '$MINIO_ACCESS_KEY',
        MINIO_SECRET_KEY: '$MINIO_SECRET_KEY',
        MINIO_BUCKET_NAME: 'youtube-videos',
        SECRET_KEY: '$APP_SECRET_KEY',
        DEBUG: 'true'
      },
      log_file: '$PROJECT_DIR/logs/backend.log',
      out_file: '$PROJECT_DIR/logs/backend-out.log',
      error_file: '$PROJECT_DIR/logs/backend-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'celery-worker',
      script: './backend/start_celery.py',
      cwd: '$PROJECT_DIR',
      interpreter: '$PROJECT_DIR/venv/bin/python',
      interpreter_args: '-u',
      args: 'worker --loglevel=info --concurrency=4',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        DATABASE_URL: 'mysql+aiomysql://youtube_user:$MYSQL_APP_PASSWORD@localhost:3306/youtube_slicer?charset=utf8mb4',
        REDIS_URL: 'redis://localhost:6379',
        MINIO_ENDPOINT: 'localhost:9000',
        MINIO_ACCESS_KEY: '$MINIO_ACCESS_KEY',
        MINIO_SECRET_KEY: '$MINIO_SECRET_KEY',
        MINIO_BUCKET_NAME: 'youtube-videos',
        SECRET_KEY: '$APP_SECRET_KEY',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip/venv/lib/python3.10/site-packages'
      },
      log_file: '/home/flowclip/EchoClip/logs/celery-worker.log',
      out_file: '/home/flowclip/EchoClip/logs/celery-worker-out.log',
      error_file: '/home/flowclip/EchoClip/logs/celery-worker-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'celery-beat',
      script: './backend/start_celery.py',
      cwd: '$PROJECT_DIR',
      interpreter: '$PROJECT_DIR/venv/bin/python',
      interpreter_args: '-u',
      args: 'beat --loglevel=info',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        DATABASE_URL: 'mysql+aiomysql://youtube_user:$MYSQL_APP_PASSWORD@localhost:3306/youtube_slicer?charset=utf8mb4',
        REDIS_URL: 'redis://localhost:6379',
        MINIO_ENDPOINT: 'localhost:9000',
        MINIO_ACCESS_KEY: '$MINIO_ACCESS_KEY',
        MINIO_SECRET_KEY: '$MINIO_SECRET_KEY',
        MINIO_BUCKET_NAME: 'youtube-videos',
        SECRET_KEY: '$APP_SECRET_KEY',
        PYTHONPATH: '/home/flowclip/EchoClip/backend:/home/flowclip/EchoClip/venv/lib/python3.10/site-packages'
      },
      log_file: '/home/flowclip/EchoClip/logs/celery-beat.log',
      out_file: '/home/flowclip/EchoClip/logs/celery-beat-out.log',
      error_file: '/home/flowclip/EchoClip/logs/celery-beat-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'frontend-react',
      script: 'npm',
      cwd: '/home/flowclip/EchoClip/frontend',
      args: 'run dev',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'development',
        VITE_API_URL: '/api'
      },
      log_file: '/home/flowclip/EchoClip/logs/frontend.log',
      out_file: '/home/flowclip/EchoClip/logs/frontend-out.log',
      error_file: '/home/flowclip/EchoClip/logs/frontend-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
EOF

    # 创建日志目录
    mkdir -p logs

    log_success "PM2 配置文件创建完成"
}

# 创建服务启动脚本
create_service_scripts() {
    log_info "创建服务管理脚本..."

    # 创建启动脚本
    cat > "$PROJECT_DIR/start_services.sh" << 'EOF'
#!/bin/bash

# Flowclip 服务启动脚本

cd "$(dirname "$0")"

echo "启动 Flowclip 服务..."

# 激活虚拟环境
source venv/bin/activate

# 启动所有服务
pm2 start ecosystem.config.js

echo "服务启动完成！"
echo ""
echo "查看服务状态: pm2 status"
echo "查看日志: pm2 logs"
echo "停止服务: pm2 stop all"
echo "重启服务: pm2 restart all"
echo ""
echo "服务访问地址："
echo "  前端: http://localhost:3000"
echo "  后端API: http://localhost:8001"
echo "  API文档: http://localhost:8001/docs"
EOF

    # 创建停止脚本
    cat > "$PROJECT_DIR/stop_services.sh" << 'EOF'
#!/bin/bash

# Flowclip 服务停止脚本

cd "$(dirname "$0")"

echo "停止 Flowclip 服务..."

pm2 stop all
pm2 delete all

echo "服务已停止"
EOF

    # 创建重启脚本
    cat > "$PROJECT_DIR/restart_services.sh" << 'EOF'
#!/bin/bash

# Flowclip 服务重启脚本

cd "$(dirname "$0")"

echo "重启 Flowclip 服务..."

pm2 restart all

echo "服务重启完成"
EOF

    # 设置执行权限
    chmod +x "$PROJECT_DIR/start_services.sh"
    chmod +x "$PROJECT_DIR/stop_services.sh"
    chmod +x "$PROJECT_DIR/restart_services.sh"

    log_success "服务管理脚本创建完成"
}

# 创建启动服务脚本
create_backend_starter() {
    log_info "创建后端服务启动脚本..."

    cd "$BACKEND_DIR"

    # 创建统一的服务启动脚本
    cat > start_services.py << 'EOF'
#!/usr/bin/env python3
"""
Flowclip 后端服务启动脚本
启动所有必需的后端服务
"""

import asyncio
import subprocess
import signal
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True

    async def start_backend(self):
        """启动主后端服务"""
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8001"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_root / "backend",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        self.processes.append(("backend", process))
        return process

    async def start_callback_server(self):
        """启动TUS回调服务器"""
        cmd = [sys.executable, "callback_server.py"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_root / "backend",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        self.processes.append(("callback", process))
        return process

    async def start_mcp_server(self):
        """启动MCP服务器"""
        cmd = [sys.executable, "run_mcp_server_complete.py"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_root / "backend",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        self.processes.append(("mcp", process))
        return process

    async def monitor_processes(self):
        """监控进程状态"""
        while self.running:
            for name, process in self.processes:
                if process.returncode is not None:
                    print(f"服务 {name} 已退出，返回码: {process.returncode}")
                    # 可以在这里添加重启逻辑
                    self.running = False
                    break
            await asyncio.sleep(1)

    async def shutdown(self):
        """优雅关闭所有服务"""
        print("正在关闭服务...")
        self.running = False

        for name, process in self.processes:
            if process.returncode is None:
                print(f"关闭服务 {name}...")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    print(f"强制关闭服务 {name}...")
                    process.kill()
                    await process.wait()

        print("所有服务已关闭")

    async def run(self):
        """运行所有服务"""
        try:
            # 设置信号处理
            def signal_handler(signum, frame):
                print(f"收到信号 {signum}，准备关闭...")
                asyncio.create_task(self.shutdown())

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # 启动服务
            print("启动后端服务...")

            await self.start_backend()
            print("✓ 后端API服务已启动 (端口: 8001)")

            await self.start_callback_server()
            print("✓ TUS回调服务器已启动 (端口: 9090)")

            await self.start_mcp_server()
            print("✓ MCP服务器已启动 (端口: 8002)")

            print("\n所有服务启动完成！")
            print("访问地址:")
            print("  后端API: http://localhost:8001")
            print("  API文档: http://localhost:8001/docs")
            print("  TUS回调: http://localhost:9090")
            print("  MCP服务: http://localhost:8002")
            print("\n按 Ctrl+C 停止服务")

            # 监控进程
            await self.monitor_processes()

        except KeyboardInterrupt:
            print("\n收到中断信号")
        finally:
            await self.shutdown()

if __name__ == "__main__":
    # 设置环境变量
    os.environ.setdefault('PYTHONUNBUFFERED', '1')

    manager = ServiceManager()
    asyncio.run(manager.run())
EOF

    chmod +x "$BACKEND_DIR/start_services.py"

    log_success "后端服务启动脚本创建完成"
}

# 主函数
main() {
    echo "========================================"
    echo "    Flowclip 用户环境配置脚本"
    echo "========================================"
    echo

    # 克隆项目代码
    clone_project

    # 检查项目目录
    check_project_directory

    # 读取系统凭据
    load_credentials

    # 检查系统依赖
    check_system_dependencies

    # 配置 Python 环境
    setup_python_env

    # 安装后端依赖
    install_backend_dependencies

    # 创建/更新环境配置文件
    update_env_file

    # 配置数据库
    setup_database

    # 安装前端依赖
    install_frontend_dependencies

    # 创建 PM2 配置
    create_pm2_config

    # 创建服务脚本
    create_service_scripts

    # 创建后端启动脚本
    create_backend_starter

    echo
    echo "========================================"
    echo "       用户环境配置完成！"
    echo "========================================"
    echo
    echo "接下来可以使用以下命令管理服务："
    echo "  启动服务: ./start_services.sh"
    echo "  停止服务: ./stop_services.sh"
    echo "  重启服务: ./restart_services.sh"
    echo
    echo "或者手动启动："
    echo "  后端服务: cd backend && python start_services.py"
    echo "  前端服务: cd frontend && npm run dev"
    echo "  Celery Worker: cd backend && python start_celery.py worker"
    echo "  Celery Beat: cd backend && python start_celery.py beat"
    echo
    echo "服务访问地址："
    echo "  前端: http://localhost:3000"
    echo "  后端API: http://localhost:8001"
    echo "  API文档: http://localhost:8001/docs"
    echo
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi