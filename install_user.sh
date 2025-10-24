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

# 验证凭据格式
validate_credential() {
    local name="$1"
    local value="$2"
    local min_length="$3"

    if [[ -z "$value" ]]; then
        log_error "❌ $name 为空"
        return 1
    fi

    if [[ ${#value} -lt $min_length ]]; then
        log_error "❌ $name 长度不足 (${#value} < $min_length)"
        return 1
    fi

    log_success "✓ $name 验证通过 (长度: ${#value})"
    return 0
}

# 读取凭据文件
load_credentials() {
    log_info "读取系统凭据..."

    # 定义凭据文件的可能位置
    local credential_locations=(
        "$CREDENTIALS_FILE"
        "/root/flowclip_credentials.txt"
        "$PROJECT_DIR/credentials.txt"
        "/home/$(whoami)/credentials.txt"
    )

    local found_credential_file=""

    # 寻找凭据文件
    for cred_file in "${credential_locations[@]}"; do
        if [[ -f "$cred_file" ]] && [[ -r "$cred_file" ]]; then
            log_info "✓ 找到凭据文件: $cred_file"
            found_credential_file="$cred_file"
            break
        fi
    done

    # 如果没有找到凭据文件
    if [[ -z "$found_credential_file" ]]; then
        log_error "❌ 未找到凭据文件"
        log_error "请确保已运行 root 安装脚本生成凭据文件"
        log_error "预期文件位置："
        for cred_file in "${credential_locations[@]}"; do
            log_error "  • $cred_file"
        done
        exit 1
    fi

    # 如果找到的文件不是目标位置，尝试复制
    if [[ "$found_credential_file" != "$CREDENTIALS_FILE" ]]; then
        log_info "复制凭据文件到目标位置..."
        if cp "$found_credential_file" "$CREDENTIALS_FILE"; then
            log_success "✓ 凭据文件复制成功: $CREDENTIALS_FILE"
            chmod 600 "$CREDENTIALS_FILE"
            chown "$(whoami):$(whoami)" "$CREDENTIALS_FILE"
        else
            log_error "❌ 凭据文件复制失败"
            exit 1
        fi
    fi

    # 验证凭据文件权限
    local file_perms=$(stat -c "%a" "$CREDENTIALS_FILE" 2>/dev/null || echo "unknown")
    if [[ "$file_perms" != "600" ]]; then
        log_warning "凭据文件权限不安全 ($file_perms)，正在修复..."
        chmod 600 "$CREDENTIALS_FILE"
    fi

    # 解析凭据文件
    log_info "解析凭据文件: $CREDENTIALS_FILE"

    # 使用更安全的方式读取凭据，避免grep找不到时的错误
    local mysql_password=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)
    local minio_access_key=$(grep "^MINIO_ACCESS_KEY=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)
    local minio_secret_key=$(grep "^MINIO_SECRET_KEY=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)
    local app_secret_key=$(grep "^SECRET_KEY=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)

    # 验证每个凭据
    log_info "验证凭据完整性..."
    local validation_failed=false

    if ! validate_credential "MySQL应用密码" "$mysql_password" 8; then
        validation_failed=true
    fi

    if ! validate_credential "MinIO访问密钥" "$minio_access_key" 20; then
        validation_failed=true
    fi

    if ! validate_credential "MinIO秘密密钥" "$minio_secret_key" 30; then
        validation_failed=true
    fi

    if ! validate_credential "应用密钥" "$app_secret_key" 20; then
        validation_failed=true
    fi

    # 如果验证失败，退出
    if [[ "$validation_failed" == "true" ]]; then
        log_error "❌ 凭据验证失败，请检查凭据文件格式和内容"
        log_error "凭据文件: $CREDENTIALS_FILE"
        exit 1
    fi

    # 导出凭据到全局变量
    export MYSQL_APP_PASSWORD="$mysql_password"
    export MINIO_ACCESS_KEY="$minio_access_key"
    export MINIO_SECRET_KEY="$minio_secret_key"
    export APP_SECRET_KEY="$app_secret_key"

    # 显示凭据文件信息（不显示实际值）
    local file_size=$(stat -c %s "$CREDENTIALS_FILE" 2>/dev/null || echo "unknown")
    local file_time=$(stat -c %y "$CREDENTIALS_FILE" 2>/dev/null || echo "unknown")

    log_success "✅ 系统凭据读取完成"
    log_info "凭据文件信息:"
    log_info "  • 文件路径: $CREDENTIALS_FILE"
    log_info "  • 文件大小: $file_size 字节"
    log_info "  • 修改时间: $file_time"
    log_info "  • 文件权限: $(stat -c "%A" "$CREDENTIALS_FILE" 2>/dev/null || echo "unknown")"
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

# 转义特殊字符用于配置文件
escape_config_value() {
    local value="$1"
    # 转义可能引起问题的特殊字符
    echo "$value" | sed 's/[[\.*^$()+?{|]/\\&/g'
}

# 统一的环境配置文件设置函数
setup_env_file() {
    log_info "设置应用环境配置文件..."

    # 检查.env文件是否存在，如果存在则备份
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log_info "发现现有 .env 文件，创建备份..."
        cp "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    # 使用已导出的凭据变量（确保使用最新值）
    local mysql_password="$MYSQL_APP_PASSWORD"
    local minio_access_key="$MINIO_ACCESS_KEY"
    local minio_secret_key="$MINIO_SECRET_KEY"
    local app_secret_key="$APP_SECRET_KEY"
    local server_ip=$(hostname -I | awk '{print $1}')

    # 动态配置参数
    local mysql_host="${MYSQL_HOST:-localhost}"
    local mysql_port="${MYSQL_PORT:-3306}"
    local mysql_user="${MYSQL_USER:-youtube_user}"
    local mysql_database="${MYSQL_DATABASE:-youtube_slicer}"
    local redis_host="${REDIS_HOST:-localhost}"
    local redis_port="${REDIS_PORT:-6379}"
    local minio_host="${MINIO_HOST:-localhost}"
    local minio_port="${MINIO_PORT:-9000}"
    local minio_bucket="${MINIO_BUCKET_NAME:-youtube-videos}"
    local backend_port="${BACKEND_PORT:-8001}"
    local frontend_port="${FRONTEND_PORT:-3000}"
    local tus_api_port="${TUS_API_PORT:-8000}"
    local tus_upload_port="${TUS_UPLOAD_PORT:-1080}"
    local tus_callback_port="${TUS_CALLBACK_PORT:-9090}"
    local tus_callback_host="${TUS_CALLBACK_HOST:-localhost}"
    local tus_file_size_threshold="${TUS_FILE_SIZE_THRESHOLD_MB:-10}"
    local tus_max_retries="${TUS_MAX_RETRIES:-3}"
    local tus_timeout="${TUS_TIMEOUT_SECONDS:-1800}"
    local debug_mode="${DEBUG_MODE:-true}"
    local node_env="${NODE_ENV:-development}"

    # 验证凭据是否读取成功
    if [[ -z "$mysql_password" ]] || [[ -z "$minio_access_key" ]] || [[ -z "$minio_secret_key" ]] || [[ -z "$app_secret_key" ]]; then
        log_error "凭据解析失败，无法创建 .env 文件"
        return 1
    fi

    # 验证解析结果
    log_info "凭据解析结果:"
    log_info "  MySQL密码长度: ${#mysql_password}"
    log_info "  MinIO访问密钥长度: ${#minio_access_key}"
    log_info "  MinIO秘密密钥长度: ${#minio_secret_key}"
    log_info "  应用密钥长度: ${#app_secret_key}"

    log_info "动态配置参数:"
    log_info "  服务器IP: $server_ip"
    log_info "  MySQL: $mysql_user@$mysql_host:$mysql_port/$mysql_database"
    log_info "  Redis: $redis_host:$redis_port"
    log_info "  MinIO: $minio_host:$minio_port/$minio_bucket"
    log_info "  后端端口: $backend_port"
    log_info "  前端端口: $frontend_port"

    # 创建全新的 .env 文件
    cat > "$PROJECT_DIR/.env" << EOF
# Flowclip Application Configuration
# Generated on $(date)
# Server: $server_ip

# Server Configuration
PUBLIC_IP=$server_ip

# Frontend URL (where users access the application)
FRONTEND_URL=http://$server_ip:$frontend_port

# Backend API URL (used by frontend to call backend)
API_URL=http://$server_ip:$backend_port

# Database Configuration
MYSQL_HOST=$mysql_host
MYSQL_PORT=$mysql_port
MYSQL_USER=$mysql_user
MYSQL_DATABASE=$mysql_database
DATABASE_URL=mysql+aiomysql://$mysql_user:$mysql_password@$mysql_host:$mysql_port/$mysql_database?charset=utf8mb4

# Redis Configuration
REDIS_HOST=$redis_host
REDIS_PORT=$redis_port
REDIS_URL=redis://$redis_host:$redis_port

# MinIO Configuration
MINIO_HOST=$minio_host
MINIO_PORT=$minio_port
MINIO_ENDPOINT=$minio_host:$minio_port
MINIO_ACCESS_KEY=$minio_access_key
MINIO_SECRET_KEY=$minio_secret_key
MINIO_BUCKET_NAME=$minio_bucket

# Security
SECRET_KEY=$app_secret_key

# OpenAI API Key (for AI features) - Please set your own key
OPENAI_API_KEY=your-openai-api-key

# Debug mode (set to false in production)
DEBUG=$debug_mode

# Node.js Environment
NODE_ENV=$node_env

# TUS Configuration
TUS_API_URL=http://$server_ip:$tus_api_port
TUS_UPLOAD_URL=http://$server_ip:$tus_upload_port
TUS_CALLBACK_PORT=$tus_callback_port
TUS_CALLBACK_HOST=$tus_callback_host
TUS_FILE_SIZE_THRESHOLD_MB=$tus_file_size_threshold
TUS_ENABLE_ROUTING=true
TUS_MAX_RETRIES=$tus_max_retries
TUS_TIMEOUT_SECONDS=$tus_timeout

# Bootstrap Configuration Support
MYSQL_APP_PASSWORD=$mysql_password
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-}
DYNAMIC_MYSQL_PASSWORD=$mysql_password
DYNAMIC_MINIO_ACCESS_KEY=$minio_access_key
DYNAMIC_MINIO_SECRET_KEY=$minio_secret_key
DYNAMIC_SECRET_KEY=$app_secret_key
EOF

    # 设置文件权限
    chmod 600 "$PROJECT_DIR/.env"

    log_success "环境配置文件设置完成"
    log_info "文件位置: $PROJECT_DIR/.env"
    log_info "文件权限: 600 (仅用户可读写)"
    log_info "支持环境变量覆盖，可在运行时通过环境变量调整配置"
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

    # 验证凭据文件存在
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        log_error ".env 文件不存在，无法创建 PM2 配置"
        return 1
    fi

    # 创建必要的目录
    mkdir -p logs
    mkdir -p ~/.pm2/logs

    # 获取Python路径和虚拟环境路径
    local python_path=$(which python3)
    local venv_python="$PROJECT_DIR/venv/bin/python"
    if [[ -f "$venv_python" ]]; then
        python_path="$venv_python"
    fi

    # 获取当前用户的Python包路径
    local python_version=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' | head -n1)
    local site_packages_path="$PROJECT_DIR/venv/lib/python${python_version}/site-packages"

    # 生成动态的PM2配置文件
    cat > ecosystem.config.js << EOF
module.exports = {
  apps: [
    // Backend API
    {
      name: 'flowclip-backend',
      script: '$python_path',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level info',
      cwd: '$BACKEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '$BACKEND_DIR:$PROJECT_DIR',
        DEBUG: 'false'
      },
      error_file: '$HOME/.pm2/logs/backend-error.log',
      out_file: '$HOME/.pm2/logs/backend-out.log',
      log_file: '$HOME/.pm2/logs/backend-combined.log',
      time: true
    },

    // TUS Callback Server
    {
      name: 'flowclip-callback',
      script: '$python_path',
      args: 'callback_server.py',
      cwd: '$BACKEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '$BACKEND_DIR:$PROJECT_DIR',
        CALLBACK_HOST: '0.0.0.0',
        CALLBACK_PORT: '9090',
        REDIS_KEY_PREFIX: 'tus_callback',
        REDIS_RESULT_PREFIX: 'tus_result',
        REDIS_STATS_KEY: 'tus_callback_stats'
      },
      error_file: '$HOME/.pm2/logs/callback-error.log',
      out_file: '$HOME/.pm2/logs/callback-out.log',
      log_file: '$HOME/.pm2/logs/callback-combined.log',
      time: true
    },

    // Celery Worker
    {
      name: 'flowclip-celery-worker',
      script: '$python_path',
      args: 'start_celery.py worker --loglevel=info --concurrency=4',
      cwd: '$BACKEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '$BACKEND_DIR:$PROJECT_DIR',
        C_FORCE_ROOT: 'true'
      },
      error_file: '$HOME/.pm2/logs/celery-worker-error.log',
      out_file: '$HOME/.pm2/logs/celery-worker-out.log',
      log_file: '$HOME/.pm2/logs/celery-worker-combined.log',
      time: true,
      kill_timeout: 30000
    },

    // Celery Beat
    {
      name: 'flowclip-celery-beat',
      script: '$python_path',
      args: 'start_celery.py beat --loglevel=info',
      cwd: '$BACKEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '$BACKEND_DIR:$PROJECT_DIR',
        C_FORCE_ROOT: 'true'
      },
      error_file: '$HOME/.pm2/logs/celery-beat-error.log',
      out_file: '$HOME/.pm2/logs/celery-beat-out.log',
      log_file: '$HOME/.pm2/logs/celery-beat-combined.log',
      time: true,
      kill_timeout: 15000
    },

    // Frontend (Static Production Server)
    {
      name: 'flowclip-frontend',
      script: '/usr/bin/node',
      args: 'server.js',
      cwd: '$FRONTEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '256M',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PORT: '3000'
      },
      error_file: '$HOME/.pm2/logs/frontend-error.log',
      out_file: '$HOME/.pm2/logs/frontend-out.log',
      log_file: '$HOME/.pm2/logs/frontend-combined.log',
      time: true
    },

    // MCP Server
    {
      name: 'flowclip-mcp-server',
      script: '$python_path',
      args: 'run_mcp_server_complete.py',
      cwd: '$BACKEND_DIR',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '$PROJECT_DIR/.env',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '$BACKEND_DIR:$PROJECT_DIR',
        DEBUG: 'false'
      },
      error_file: '$HOME/.pm2/logs/mcp-server-error.log',
      out_file: '$HOME/.pm2/logs/mcp-server-out.log',
      log_file: '$HOME/.pm2/logs/mcp-server-combined.log',
      time: true
    }
  ]
};
EOF

    log_success "PM2 配置文件创建完成"
    log_info "配置文件位置: $PROJECT_DIR/ecosystem.config.js"
    log_info "所有服务统一使用 env_file: $PROJECT_DIR/.env"
    log_info "日志目录: $HOME/.pm2/logs/"
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

# 验证配置文件
verify_configurations() {
    log_info "验证生成的配置文件..."

    local validation_errors=()

    # 验证 .env 文件
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        log_info "验证 .env 文件..."

        # 检查关键配置项是否存在
        local required_vars=(
            "DATABASE_URL"
            "REDIS_URL"
            "MINIO_ENDPOINT"
            "MINIO_ACCESS_KEY"
            "MINIO_SECRET_KEY"
            "SECRET_KEY"
            "DYNAMIC_MYSQL_PASSWORD"
            "MYSQL_HOST"
            "MYSQL_PORT"
            "MYSQL_USER"
            "MYSQL_DATABASE"
        )

        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" "$PROJECT_DIR/.env"; then
                local value=$(grep "^$var=" "$PROJECT_DIR/.env" | cut -d'=' -f2)
                if [[ -z "$value" ]]; then
                    validation_errors+=(".env: $var 值为空")
                else
                    log_success "✓ .env: $var 配置正确"
                fi
            else
                validation_errors+=(".env: 缺少 $var 配置")
            fi
        done
    else
        validation_errors+=(".env 文件不存在")
    fi

    # 验证 PM2 配置文件
    if [[ -f "$PROJECT_DIR/ecosystem.config.js" ]]; then
        log_info "验证 ecosystem.config.js 文件..."

        # 检查是否所有应用都使用 env_file
        local app_names=("flowclip-backend" "flowclip-callback" "flowclip-celery-worker" "flowclip-celery-beat" "flowclip-frontend" "flowclip-mcp-server")

        for app in "${app_names[@]}"; do
            if grep -q "name.*'$app'" "$PROJECT_DIR/ecosystem.config.js"; then
                # 检查是否有 env_file 配置
                if grep -A 20 "name.*'$app'" "$PROJECT_DIR/ecosystem.config.js" | grep -q "env_file"; then
                    log_success "✓ PM2: $app 使用 env_file"
                else
                    validation_errors+=("PM2: $app 缺少 env_file 配置")
                fi

                # 检查PYTHONPATH配置是否正确
                if grep -A 20 "name.*'$app'" "$PROJECT_DIR/ecosystem.config.js" | grep -q "PYTHONPATH"; then
                    local pythonpath=$(grep -A 20 "name.*'$app'" "$PROJECT_DIR/ecosystem.config.js" | grep "PYTHONPATH" | cut -d"'" -f4)
                    if [[ "$pythonpath" == *"$PROJECT_DIR"* ]] || [[ "$pythonpath" == *"$BACKEND_DIR"* ]]; then
                        log_success "✓ PM2: $app PYTHONPATH 配置正确"
                    else
                        validation_errors+=("PM2: $app PYTHONPATH 配置可能不正确: $pythonpath")
                    fi
                fi
            else
                validation_errors+=("PM2: 缺少 $app 应用配置")
            fi
        done

        # 检查路径是否使用变量
        if grep -q "/home/flowclip/EchoClip" "$PROJECT_DIR/ecosystem.config.js"; then
            log_warning "PM2 配置中仍存在硬编码路径"
        else
            log_success "✓ PM2 配置使用动态路径"
        fi

    else
        validation_errors+=("ecosystem.config.js 文件不存在")
    fi

    # 验证日志目录
    if [[ ! -d "$HOME/.pm2/logs" ]]; then
        log_info "创建 PM2 日志目录..."
        mkdir -p "$HOME/.pm2/logs"
    fi
    log_success "✓ PM2 日志目录已创建: $HOME/.pm2/logs/"

    # 验证项目日志目录
    if [[ ! -d "$PROJECT_DIR/logs" ]]; then
        log_info "创建项目日志目录..."
        mkdir -p "$PROJECT_DIR/logs"
    fi
    log_success "✓ 项目日志目录已创建: $PROJECT_DIR/logs/"

    # 报告验证结果
    if [[ ${#validation_errors[@]} -eq 0 ]]; then
        log_success "✅ 所有配置验证通过！"
        return 0
    else
        log_error "❌ 发现 ${#validation_errors[@]} 个配置问题："
        for error in "${validation_errors[@]}"; do
            log_error "  • $error"
        done
        return 1
    fi
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

    # 创建 Celery 启动脚本
    log_info "创建 Celery 启动脚本..."
    cat > "$BACKEND_DIR/start_celery.py" << 'EOF'
#!/usr/bin/env python3
"""
Celery Worker 启动脚本
在启动 Celery Worker 之前从数据库加载系统配置
"""

import os
import sys
import logging
import signal
import threading
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量用于控制配置重载线程
reload_thread = None
reload_stop_event = threading.Event()

def load_system_configs(max_retries=10, retry_interval=3, silent=False):
    """从数据库加载系统配置，带重试机制"""
    for attempt in range(max_retries):
        try:
            # 显式加载环境变量 (使用项目根目录的.env)
            dotenv_path = project_root / '.env'
            from dotenv import load_dotenv
            load_dotenv(dotenv_path)

            # 导入必要的模块
            from app.core.database import get_sync_db
            from app.services.system_config_service import SystemConfigService
            from app.core.config import settings
            from app.services.minio_client import minio_service

            # 获取数据库会话并加载配置
            db = get_sync_db()
            SystemConfigService.update_settings_from_db_sync(db)
            db.close()

            # 重新加载MinIO客户端配置
            minio_service.reload_config()

            if not silent:
                logger.info("系统配置从数据库加载成功")
            return True
        except Exception as e:
            logger.warning(f"从数据库加载系统配置失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            import traceback
            logger.warning(f"详细错误信息: {traceback.format_exc()}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                logger.error(f"从数据库加载系统配置失败，已重试 {max_retries} 次")
                return False

def reload_configs_periodically(interval=60):
    """定期重新加载系统配置"""
    while not reload_stop_event.wait(interval):
        # 静默重新加载配置，只在出错时记录日志
        if not load_system_configs(silent=True):
            pass  # load_system_configs 内部已经记录了错误日志

def signal_handler(signum, frame):
    """信号处理函数，用于优雅关闭"""
    logger.info("收到信号，准备关闭...")
    reload_stop_event.set()
    if reload_thread and reload_thread.is_alive():
        reload_thread.join()
    sys.exit(0)

if __name__ == "__main__":
    # 设置信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 加载系统配置
    if not load_system_configs():
        logger.warning("系统配置加载失败，将继续使用环境变量配置")

    # 启动定期重载配置的线程
    reload_thread = threading.Thread(target=reload_configs_periodically, args=(60,), daemon=True)
    reload_thread.start()

    # 获取命令行参数
    if len(sys.argv) < 2:
        logger.error("请指定要启动的服务类型: worker 或 beat")
        sys.exit(1)

    service_type = sys.argv[1]

    if service_type == "worker":
        # 启动 Celery Worker
        import subprocess
        # 使用当前 Python 解释器下的 celery
        celery_path = os.path.join(os.path.dirname(sys.executable), "celery")
        cmd = [celery_path, "-A", "app.core.celery", "worker"] + sys.argv[2:]
        logger.info(f"启动 Celery Worker: {' '.join(cmd)}")
        subprocess.run(cmd)
    elif service_type == "beat":
        # 启动 Celery Beat
        import subprocess
        # 使用当前 Python 解释器下的 celery
        celery_path = os.path.join(os.path.dirname(sys.executable), "celery")
        cmd = [celery_path, "-A", "app.core.celery", "beat"] + sys.argv[2:]
        logger.info(f"启动 Celery Beat: {' '.join(cmd)}")
        subprocess.run(cmd)
    else:
        logger.error(f"不支持的服务类型: {service_type}，请使用 worker 或 beat")
        sys.exit(1)
EOF

    chmod +x "$BACKEND_DIR/start_celery.py"

    log_success "Celery 启动脚本创建完成"
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

    # 设置环境配置文件
    setup_env_file

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

  # 验证所有配置文件
    verify_configurations

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