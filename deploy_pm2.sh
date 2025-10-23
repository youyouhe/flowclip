#!/bin/bash

# EchoClip PM2 部署脚本
# 用于在服务器上使用 PM2 部署和更新应用

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 项目路径
PROJECT_DIR="/home/flowclip/EchoClip"
BACKUP_DIR="/home/flowclip/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# 检查是否以 flowclip 用户运行
if [ "$(whoami)" != "flowclip" ]; then
    log_error "请以 flowclip 用户运行此脚本"
    exit 1
fi

log_info "开始部署 EchoClip 应用 (PM2 模式)..."

# 创建必要的目录
mkdir -p $BACKUP_DIR
mkdir -p ~/.pm2/logs
mkdir -p /home/flowclip/minio-data

# 进入项目目录
cd $PROJECT_DIR

# 1. 停止现有服务
log_info "停止现有 PM2 服务..."
pm2 stop all || true
pm2 delete all || true

# 2. 备份当前代码
log_info "备份当前代码..."
tar -czf $BACKUP_DIR/backup_$TIMESTAMP.tar.gz --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='dist' .

# 3. 拉取最新代码
log_info "拉取最新代码..."
git fetch origin
git pull origin main

# 4. 检查并安装系统依赖
log_info "检查系统依赖..."

# 检查 Node.js
if ! command -v node &> /dev/null; then
    log_error "Node.js 未安装！"
    exit 1
fi

NODE_VERSION=$(node --version)
log_success "Node.js 版本: $NODE_VERSION"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    log_error "Python3 未安装！"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
log_success "Python 版本: $PYTHON_VERSION"

# 5. 设置后端环境
log_info "设置后端环境..."
cd backend

# 创建虚拟环境
if [ ! -d "venv" ]; then
    log_info "创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-audio.txt

# 检查必要的 Python 脚本
if [ ! -f "start_celery.py" ]; then
    log_error "start_celery.py 文件不存在！"
    exit 1
fi

if [ ! -f "callback_server.py" ]; then
    log_error "callback_server.py 文件不存在！"
    exit 1
fi

if [ ! -f "run_mcp_server_complete.py" ]; then
    log_error "run_mcp_server_complete.py 文件不存在！"
    exit 1
fi

log_success "后端环境设置完成"

# 6. 设置前端环境
log_info "设置前端环境..."
cd ../frontend

# 安装依赖
npm install --legacy-peer-deps

# 构建生产版本
log_info "构建前端生产版本..."
npm run build

# 检查构建结果
if [ ! -d "dist" ]; then
    log_error "前端构建失败，dist 目录不存在！"
    exit 1
fi

log_success "前端环境设置完成"

# 7. 检查系统服务状态
log_info "检查系统服务状态..."

# 检查 MySQL
MYSQL_SERVICE="mysql"
if ! systemctl is-active --quiet $MYSQL_SERVICE; then
    MYSQL_SERVICE="mysqld"
    if ! systemctl is-active --quiet $MYSQL_SERVICE; then
        log_warn "MySQL 服务未运行，尝试启动..."
        sudo systemctl start $MYSQL_SERVICE || {
            log_error "MySQL 启动失败，请手动检查"
            exit 1
        }
    fi
fi
log_success "MySQL 服务运行正常"

# 检查 Redis
REDIS_SERVICE="redis"
if ! systemctl is-active --quiet $REDIS_SERVICE; then
    REDIS_SERVICE="redis-server"
    if ! systemctl is-active --quiet $REDIS_SERVICE; then
        log_warn "Redis 服务未运行，尝试启动..."
        sudo systemctl start $REDIS_SERVICE || {
            log_error "Redis 启动失败，请手动检查"
            exit 1
        }
    fi
fi
log_success "Redis 服务运行正常"

# 检查 MinIO
if ! pgrep -f "minio server" > /dev/null; then
    log_warn "MinIO 服务未运行，尝试启动..."
    nohup minio server /home/flowclip/minio-data --console-address ":9001" > /dev/null 2>&1 &
    sleep 3
    if pgrep -f "minio server" > /dev/null; then
        log_success "MinIO 服务启动成功"
    else
        log_error "MinIO 启动失败，请手动检查"
        exit 1
    fi
else
    log_success "MinIO 服务运行正常"
fi

# 8. 检查端口占用
log_info "检查端口占用..."

check_port() {
    local port=$1
    local service=$2
    if netstat -tuln | grep -q ":$port "; then
        log_warn "端口 $port ($service) 已被占用"
        return 1
    else
        log_success "端口 $port ($service) 可用"
        return 0
    fi
}

check_port 3307 "MySQL"
check_port 6379 "Redis"
check_port 9000 "MinIO API"
check_port 9001 "MinIO Console"
check_port 3000 "Frontend"
check_port 8001 "Backend API"
check_port 9090 "TUS Callback"
check_port 8002 "MCP Server"

# 9. 测试数据库连接
log_info "测试数据库连接..."
cd $PROJECT_DIR/backend
source venv/bin/activate

python3 -c "
import mysql.connector
try:
    conn = mysql.connector.connect(
        host='localhost',
        port=3307,
        user='youtube_user',
        password='youtube_password',
        database='youtube_slicer'
    )
    print('✓ 数据库连接成功')
    conn.close()
except Exception as e:
    print(f'✗ 数据库连接失败: {e}')
    exit(1)
" || {
    log_error "数据库连接测试失败！"
    exit 1
}

# 10. 运行数据库迁移
log_info "运行数据库迁移..."
cd $PROJECT_DIR/backend
source venv/bin/activate
alembic upgrade head || {
    log_warn "数据库迁移失败，继续部署..."
}

# 11. 初始化系统配置
log_info "初始化系统配置..."
if [ -f "init_system_config.py" ]; then
    python init_system_config.py || {
        log_warn "系统配置初始化失败，继续部署..."
    }
else
    log_warn "init_system_config.py 文件不存在，跳过系统配置初始化"
fi

# 12. 启动 PM2 服务
log_info "启动 PM2 服务..."
cd $PROJECT_DIR

# 首先验证 PM2 配置文件
if [ ! -f "ecosystem.config.js" ]; then
    log_error "ecosystem.config.js 文件不存在！"
    exit 1
fi

# 启动所有服务
pm2 start ecosystem.config.js --env production || {
    log_error "PM2 服务启动失败！"
    exit 1
}

# 13. 保存 PM2 配置
log_info "保存 PM2 配置..."
pm2 save

# 设置 PM2 开机启动
pm2 startup | grep -E '^sudo' | sh || true

# 14. 等待服务启动并进行健康检查
log_info "等待服务启动..."
sleep 10

# 健康检查函数
health_check() {
    local url=$1
    local service=$2
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$service 健康检查通过"
            return 0
        else
            log_info "$service 健康检查失败，重试 $attempt/$max_attempts..."
            sleep 2
            attempt=$((attempt + 1))
        fi
    done

    log_warn "$service 健康检查失败，请检查日志"
    return 1
}

# 执行健康检查
log_info "执行健康检查..."
health_check "http://localhost:8001/health" "Backend API"
health_check "http://localhost:3000" "Frontend"
health_check "http://localhost:9090/health" "TUS Callback Server"

# 15. 显示服务状态
log_info "显示服务状态..."
pm2 status

# 16. 显示部署信息
log_success "部署完成！"
echo ""
log_info "🌐 服务访问地址："
echo "  - 前端: http://107.173.223.214:3000"
echo "  - 后端API: http://107.173.223.214:8001"
echo "  - MinIO控制台: http://107.173.223.214:9001"
echo "  - TUS回调服务: http://107.173.223.214:9090"
echo "  - MCP服务: http://107.173.223.214:8002"
echo ""
log_info "📋 日志查看命令："
echo "  - 所有服务: pm2 logs"
echo "  - 特定服务: pm2 logs [service-name]"
echo "  - 实时监控: pm2 monit"
echo ""
log_info "🔧 常用管理命令："
echo "  - 重启服务: pm2 restart all"
echo "  - 停止服务: pm2 stop all"
echo "  - 重载配置: pm2 reload all"
echo "  - 查看状态: pm2 status"
echo ""
log_info "📁 重要文件位置："
echo "  - PM2 配置: $PROJECT_DIR/ecosystem.config.js"
echo "  - PM2 日志: ~/.pm2/logs/"
echo "  - 备份文件: $BACKUP_DIR/"
echo "  - MinIO 数据: /home/flowclip/minio-data"

# 17. 显示系统资源使用情况
log_info "系统资源使用情况："
echo "内存使用: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "磁盘使用: $(df -h $PROJECT_DIR | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"

log_success "EchoClip PM2 部署脚本执行完成！"