#!/bin/bash

# Flowclip 系统初始化脚本 (root用户)
# 负责系统更新、软件安装、用户创建等需要root权限的操作
# 安装MySQL、Redis、MinIO等核心组件以替代Docker环境

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 系统配置
PROJECT_NAME="flowclip"
SERVICE_USER="flowclip"
PROJECT_DIR="/home/$SERVICE_USER/EchoClip"

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

# 检查系统环境
check_system_environment() {
    log_info "=== 系统环境检查 ==="

    # 显示系统信息
    log_info "系统信息:"
    echo "  操作系统: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2 2>/dev/null || echo '未知')"
    echo "  内核版本: $(uname -r)"
    echo "  CPU核心: $(nproc)"
    echo "  内存总量: $(free -h | awk 'NR==2{print $2}')"
    echo "  可用内存: $(free -h | awk 'NR==2{print $7}')"
    echo "  磁盘空间: $(df -h / | awk 'NR==2{print $4}') 可用"
    echo "  当前用户: $(whoami)"

    # 检查root权限
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo bash install_root.sh"
        exit 1
    fi
    log_success "root权限检查通过"

    # 检查网络连接
    log_info "检查网络连接..."
    if ping -c 1 google.com &> /dev/null; then
        log_success "网络连接正常"
    else
        log_warning "网络连接可能有问题，建议检查网络设置"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
    fi

    # 检查磁盘空间
    available_space=$(df / | awk 'NR==2 {print $4}')
    required_space=31457280  # 30GB in KB (约30GB)
    recommended_space=52428800  # 50GB in KB (推荐50GB)

    if [[ $available_space -lt $required_space ]]; then
        log_error "磁盘空间不足，需要至少30GB可用空间，当前可用: $(df -h / | awk 'NR==2{print $4}')"
        exit 1
    elif [[ $available_space -lt $recommended_space ]]; then
        log_warning "磁盘空间较少，推荐至少50GB，当前可用: $(df -h / | awk 'NR==2{print $4}')"
        log_warning "空间可能影响大文件处理和长期运行"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
        log_success "磁盘空间检查通过 (可用: $(df -h / | awk 'NR==2{print $4}')"
    else
        log_success "磁盘空间检查通过 (可用: $(df -h / | awk 'NR==2{print $4}')"
    fi

    # 检查内存
    available_mem=$(free -m | awk 'NR==2{print $7}')
    if [[ $available_mem -lt 4096 ]]; then
        log_warning "可用内存不足4GB (当前: ${available_mem}MB)，可能影响安装和运行性能"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
    else
        log_success "内存检查通过 (可用: ${available_mem}MB)"
    fi

    # 检查必要端口是否被占用
    local ports_to_check=("3306" "6379" "9000" "9001")
    local occupied_ports=()

    for port in "${ports_to_check[@]}"; do
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            occupied_ports+=("$port")
        fi
    done

    if [[ ${#occupied_ports[@]} -gt 0 ]]; then
        log_warning "以下端口已被占用: ${occupied_ports[*]}"
        log_info "这些端口将被用于: MySQL(3306), Redis(6379), MinIO(9000,9001)"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
    else
        log_success "端口检查通过 - 所有必要端口可用"
    fi

    # 检查是否为虚拟环境或容器
    if [[ -f /.dockerenv ]]; then
        log_warning "检测到Docker容器环境，不建议在容器内安装系统级服务"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
    fi

    log_success "系统环境检查完成"
}

# 检查当前用户权限 (保持向后兼容)
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo bash install_root.sh"
        exit 1
    fi
    log_success "root权限检查通过"
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        log_error "无法检测操作系统版本"
        exit 1
    fi

    log_info "检测到操作系统: $OS $VER"
}

# 系统初始化和基础软件安装
init_system() {
    log_info "开始系统初始化..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # Ubuntu/Debian 系统初始化
        log_info "更新软件包列表..."
        apt update

        log_info "升级系统软件包..."
        apt upgrade -y

        log_info "安装基础工具..."
        apt install -y \
            curl \
            wget \
            git \
            unzip \
            tar \
            build-essential \
            software-properties-common \
            apt-transport-https \
            ca-certificates \
            gnupg \
            lsb-release \
            net-tools \
            lsof \
            htop \
            vim \
            nano \
            python3 \
            python3-pip \
            python3-venv \
            python3-dev

        log_success "Ubuntu/Debian 系统初始化完成"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        # CentOS/RHEL 系统初始化
        if command -v dnf &> /dev/null; then
            log_info "更新软件包列表..."
            dnf update -y

            log_info "升级系统软件包..."
            dnf upgrade -y

            log_info "安装基础工具..."
            dnf groupinstall -y "Development Tools"
            dnf install -y \
                curl \
                wget \
                git \
                unzip \
                tar \
                net-tools \
                lsof \
                htop \
                vim \
                nano \
                epel-release \
                python3 \
                python3-pip \
                python3-devel
        else
            log_info "更新软件包列表..."
            yum update -y

            log_info "升级系统软件包..."
            yum upgrade -y

            log_info "安装基础工具..."
            yum groupinstall -y "Development Tools"
            yum install -y \
                curl \
                wget \
                git \
                unzip \
                tar \
                net-tools \
                lsof \
                htop \
                vim \
                nano \
                epel-release \
                python3 \
                python3-pip \
                python3-devel
        fi

        log_success "CentOS/RHEL 系统初始化完成"
    fi
}

# 安装 Python 3.11
install_python311() {
    log_info "检查 Python 3.11 安装状态..."

    if command -v python3.11 &> /dev/null; then
        log_success "Python 3.11 已安装: $(python3.11 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
        return 0
    fi

    log_info "正在安装 Python 3.11..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # Ubuntu/Debian 安装 Python 3.11
        apt install -y software-properties-common

        # 添加 deadsnakes PPA
        if ! grep -q "deadsnakes" /etc/apt/sources.list.d/* 2>/dev/null; then
            add-apt-repository ppa:deadsnakes/ppa -y
        fi

        apt update

        # 安装 Python 3.11
        apt install -y \
            python3.11 \
            python3.11-venv \
            python3.11-dev \
            python3.11-distutils \
            python3-lib2to3

        # 为 Python 3.11 安装 pip
        log_info "为 Python 3.11 安装 pip..."
        python3.11 -m ensurepip --upgrade || {
            log_warning "ensurepip 失败，尝试使用 get-pip.py..."
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
        }

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        # CentOS/RHEL 安装 Python 3.11
        if command -v dnf &> /dev/null; then
            dnf install -y python3.11 python3.11-devel
        else
            yum install -y python3.11 python3.11-devel
        fi

        # 为 Python 3.11 安装 pip
        log_info "为 Python 3.11 安装 pip..."
        python3.11 -m ensurepip --upgrade || {
            log_warning "ensurepip 失败，尝试使用 get-pip.py..."
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
        }
    fi

    # 验证安装
    if command -v python3.11 &> /dev/null; then
        log_success "Python 3.11 安装成功: $(python3.11 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
    else
        log_warning "Python 3.11 安装失败，将使用系统默认Python"
    fi
}

# 安装 MySQL 8.0
install_mysql() {
    log_info "安装 MySQL 8.0..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # 更新包列表
        apt update

        # 安装 MySQL 8.0
        log_info "安装 MySQL 8.0 软件包..."
        apt install -y mysql-server-8.0

        # 启动并启用 MySQL 服务
        systemctl start mysql
        systemctl enable mysql

        # 等待MySQL完全启动
        log_info "等待MySQL服务完全启动..."
        sleep 10

        # 检查MySQL服务状态
        if ! systemctl is-active --quiet mysql; then
            log_error "MySQL服务启动失败"
            return 1
        fi

        # 重置MySQL root密码（处理已安装MySQL的情况）
        log_info "配置MySQL安全设置..."
        log_info "检测到可能存在的MySQL安装，尝试重置配置..."

        # 方法1: 使用debian-sys-maint用户（Ubuntu/Debian特有）
        local mysql_configured=false
        if [[ -f "/etc/mysql/debian.cnf" ]]; then
            log_info "尝试使用debian-sys-maint用户重置密码..."
            local debian_password=$(grep -m1 "password" /etc/mysql/debian.cnf | awk '{print $3}')

            if mysql -u debian-sys-maint -p"$debian_password" -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpassword'; FLUSH PRIVILEGES;" &>/dev/null; then
                log_success "通过debian-sys-maint用户成功重置root密码"
                mysql_configured=true
            fi
        fi

        # 方法2: 尝试无密码root连接
        if [[ "$mysql_configured" == false ]] && mysql -u root -e "SELECT 1;" &>/dev/null; then
            log_info "发现root无密码访问，进行配置..."
            mysql -u root -e "
                ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpassword';
                DELETE FROM mysql.user WHERE User='';
                DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
                DROP DATABASE IF EXISTS test;
                DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
                FLUSH PRIVILEGES;
            "
            mysql_configured=true
        fi

        # 方法3: 尝试使用socket连接
        if [[ "$mysql_configured" == false ]] && mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "SELECT 1;" &>/dev/null; then
            log_info "发现socket连接方式，进行配置..."
            mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "
                ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpassword';
                DELETE FROM mysql.user WHERE User='';
                DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
                DROP DATABASE IF EXISTS test;
                DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
                FLUSH PRIVILEGES;
            "
            mysql_configured=true
        fi

        # 方法4: 尝试常见默认密码
        if [[ "$mysql_configured" == false ]]; then
            local common_passwords=("root" "password" "mysql" "123456" "")
            for pwd in "${common_passwords[@]}"; do
                if mysql -u root -p"$pwd" -e "SELECT 1;" &>/dev/null; then
                    log_info "发现root密码 '$pwd'，重新配置..."
                    mysql -u root -p"$pwd" -e "
                        ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpassword';
                        DELETE FROM mysql.user WHERE User='';
                        DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
                        DROP DATABASE IF EXISTS test;
                        DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
                        FLUSH PRIVILEGES;
                    "
                    mysql_configured=true
                    break
                fi
            done
        fi

        # 方法5: 重置MySQL root密码（安全模式）
        if [[ "$mysql_configured" == false ]]; then
            log_info "尝试安全模式重置MySQL密码..."
            systemctl stop mysql

            # 启动MySQL安全模式
            mysqld_safe --skip-grant-tables --skip-networking &
            local mysql_pid=$!

            sleep 5

            # 重置密码
            mysql -u root -e "
                USE mysql;
                UPDATE user SET authentication_string=PASSWORD('rootpassword') WHERE User='root';
                UPDATE user SET plugin='mysql_native_password' WHERE User='root';
                FLUSH PRIVILEGES;
            " &>/dev/null && mysql_configured=true

            # 重启MySQL
            kill $mysql_pid 2>/dev/null || true
            sleep 2
            systemctl start mysql
            sleep 5
        fi

        # 验证配置是否成功
        if mysql -uroot -prootpassword -e "SELECT 1;" &>/dev/null; then
            log_success "MySQL安全配置完成"
        else
            log_error "MySQL配置验证失败，请手动配置"
            log_info "手动配置命令："
            log_info "1. sudo mysql"
            log_info "2. ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'rootpassword';"
            log_info "3. FLUSH PRIVILEGES;"
            log_info "4. EXIT;"
            read -p "配置完成后按回车继续..."
        fi

        # 创建应用数据库和用户
        log_info "创建应用数据库和用户..."
        if mysql -uroot -prootpassword -e "USE youtube_slicer; SELECT 1;" &>/dev/null; then
            log_success "应用数据库已存在"
        else
            mysql -uroot -prootpassword -e "
                CREATE DATABASE IF NOT EXISTS youtube_slicer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
                CREATE USER IF NOT EXISTS 'youtube_user'@'localhost' IDENTIFIED BY 'youtube_password';
                GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'localhost';
                FLUSH PRIVILEGES;
            " || {
                log_warning "数据库创建可能失败，但继续安装..."
            }
        fi

        # 验证应用数据库连接
        if mysql -uyoutube_user -pyoutube_password -e "USE youtube_slicer; SELECT 1;" &>/dev/null; then
            log_success "数据库和用户创建并验证成功"
        else
            log_warning "数据库连接验证失败，请稍后手动检查"
        fi

        log_success "MySQL 8.0 安装配置完成"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        # 添加 MySQL 8.0 仓库
        log_info "添加 MySQL 8.0 仓库..."
        yum install -y https://dev.mysql.com/get/mysql80-community-release-el7-3.noarch.rpm

        # 安装 MySQL 8.0
        yum install -y mysql-community-server

        # 启动并启用 MySQL 服务
        systemctl start mysqld
        systemctl enable mysqld

        # 获取临时密码
        temp_password=$(grep 'temporary password' /var/log/mysqld.log | awk '{print $NF}')

        # 安全配置
        log_info "执行 MySQL 安全配置..."
        mysql -uroot -p"$temp_password" -e "
            ALTER USER 'root'@'localhost' IDENTIFIED BY 'rootpassword';
            DELETE FROM mysql.user WHERE User='';
            DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
            DROP DATABASE IF EXISTS test;
            DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
            FLUSH PRIVILEGES;
        "

        # 创建应用数据库和用户
        mysql -uroot -prootpassword -e "
            CREATE DATABASE IF NOT EXISTS youtube_slicer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            CREATE USER IF NOT EXISTS 'youtube_user'@'localhost' IDENTIFIED BY 'youtube_password';
            GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'localhost';
            FLUSH PRIVILEGES;
        "

        log_success "MySQL 8.0 安装配置完成"
    fi
}

# 安装 Redis
install_redis() {
    log_info "安装 Redis..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt install -y redis-server

        # 配置 Redis
        sed -i 's/supervised no/supervised systemd/' /etc/redis/redis.conf
        sed -i 's/#maxmemory 1gb/maxmemory 1gb/' /etc/redis/redis.conf
        sed -i 's/#maxmemory-policy allkeys-lru/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf

        # 启动并启用 Redis
        systemctl restart redis.service
        systemctl enable redis

        log_success "Redis 安装配置完成"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        if command -v dnf &> /dev/null; then
            dnf install -y redis
        else
            yum install -y redis
        fi

        # 配置 Redis
        sed -i 's/supervised no/supervised systemd/' /etc/redis.conf
        sed -i 's/#maxmemory 1gb/maxmemory 1gb/' /etc/redis.conf
        sed -i 's/#maxmemory-policy allkeys-lru/maxmemory-policy allkeys-lru/' /etc/redis.conf

        # 启动并启用 Redis
        systemctl restart redis
        systemctl enable redis

        log_success "Redis 安装配置完成"
    fi
}

# 安装 MinIO
install_minio() {
    log_info "安装 MinIO..."

    # 创建 MinIO 用户和目录
    useradd -r -s /bin/false minio || true
    mkdir -p /opt/minio
    mkdir -p /opt/minio/data

    # 下载 MinIO
    cd /tmp
    wget https://dl.min.io/server/minio/release/linux-amd64/minio
    chmod +x minio
    mv minio /opt/minio/

    # 设置所有权
    chown -R minio:minio /opt/minio

    # 创建 MinIO 服务文件
    cat > /etc/systemd/system/minio.service << 'EOF'
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target
AssertFileIsExecutable=/opt/minio/minio

[Service]
WorkingDirectory=/opt/minio/

User=minio
Group=minio

ProtectProc=invisible

EnvironmentFile=-/etc/default/minio
ExecStartPre=/bin/bash -c "if [ -z \"${MINIO_VOLUMES}\" ]; then echo \"Variable MINIO_VOLUMES not set in /etc/default/minio\"; exit 1; fi"
ExecStart=/opt/minio/minio server $MINIO_VOLUMES $MINIO_OPTS

# Let systemd restart this service always
Restart=always

# Specifies the maximum file descriptor number that can be opened by this process
LimitNOFILE=65536

# Specifies the maximum number of threads this process can create
TasksMax=infinity

# Disable timeout logic and wait until process is stopped
TimeoutStopSec=infinity
SendSIGKILL=no

[Install]
WantedBy=multi-user.target
EOF

    # 创建 MinIO 环境配置文件
    cat > /etc/default/minio << 'EOF'
# MinIO local configuration file
# Volume to be used for MinIO server.
MINIO_VOLUMES="/opt/minio/data"

# User and group
MINIO_ROOT_USER=i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0=
MINIO_ROOT_PASSWORD=TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k=

# Use if you want to run MinIO on a custom port.
MINIO_OPTS="--console-address \":9001\""

# Set MinIO server options.
# For more information, see https://docs.min.io/docs/minio-server-configuration-guide.html
EOF

    # 启动并启用 MinIO
    systemctl daemon-reload
    systemctl enable minio.service
    systemctl start minio.service

    # 等待 MinIO 启动
    sleep 5

    # 验证 MinIO 是否启动成功
    if systemctl is-active --quiet minio.service; then
        log_success "MinIO 安装配置完成"
        log_info "MinIO Console: http://$(hostname -I | awk '{print $1}'):9001"
        log_info "MinIO API: http://$(hostname -I | awk '{print $1}'):9000"
    else
        log_error "MinIO 启动失败"
        return 1
    fi
}

# 安装 Node.js
install_nodejs() {
    log_info "安装 Node.js 18.x..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # 安装 NodeSource 仓库
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -

        # 安装 Node.js
        apt install -y nodejs

        log_success "Node.js 安装完成: $(node -v)"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        # 安装 NodeSource 仓库
        curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -

        # 安装 Node.js
        if command -v dnf &> /dev/null; then
            dnf install -y nodejs
        else
            yum install -y nodejs
        fi

        log_success "Node.js 安装完成: $(node -v)"
    fi

    # 安装 pm2 进程管理器
    npm install -g pm2
    log_success "PM2 进程管理器安装完成"
}

# 安装项目特定系统依赖
install_system_deps() {
    log_info "正在安装 Flowclip 项目依赖..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        log_info "安装视频处理和图像处理库..."
        apt install -y \
            ffmpeg \
            libsm6 \
            libxext6 \
            libxrender-dev \
            libgomp1 \
            libglib2.0-0 \
            libgl1-mesa-glx \
            libglib2.0-0 \
            libgtk-3-0 \
            libavcodec-dev \
            libavformat-dev \
            libswscale-dev

        log_success "Ubuntu/Debian 项目依赖安装完成"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        log_info "安装视频处理和图像处理库..."
        if command -v dnf &> /dev/null; then
            dnf install -y \
                ffmpeg \
                ffmpeg-devel \
                libSM \
                libXext \
                libXrender \
                gomp \
                glib2 \
                mesa-libGL \
                gtk3 \
                avcodec-devel \
                avformat-devel \
                swscale-devel
        else
            yum install -y \
                ffmpeg \
                ffmpeg-devel \
                libSM \
                libXext \
                libXrender \
                gomp \
                glib2 \
                mesa-libGL \
                gtk3 \
                avcodec-devel \
                avformat-devel \
                swscale-devel
        fi

        log_success "CentOS/RHEL 项目依赖安装完成"
    fi
}

# 创建 Flowclip 专用用户
create_flowclip_user() {
    local username="$SERVICE_USER"

    log_info "创建专用用户: $username"

    # 检查用户是否已存在
    if id "$username" &>/dev/null; then
        log_warning "用户 $username 已存在"
        return 0
    fi

    # 创建用户
    adduser --disabled-password --gecos "" "$username" || {
        log_error "用户创建失败"
        return 1
    }

    # 添加到管理员组
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        usermod -aG sudo "$username"
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        usermod -aG wheel "$username"
    fi

    # 设置 sudo 免密码
    echo "$username ALL=(ALL) NOPASSWD:ALL" | tee "/etc/sudoers.d/$username" >/dev/null

    log_success "用户 $username 创建完成"
}

# 设置用户环境
setup_user_environment() {
    local username="$SERVICE_USER"

    log_info "为专用用户设置环境..."

    # 如果项目目录已存在，先检查是否是我们的项目
    if [[ -d "$PROJECT_DIR" ]]; then
        log_info "项目目录已存在: $PROJECT_DIR"
    else
        # 创建项目目录
        mkdir -p "$PROJECT_DIR"
    fi

    # 设置目录权限
    chown -R "$username:$username" "$PROJECT_DIR"

    # 为专用用户配置 Python 环境
    if command -v python3.11 &> /dev/null; then
        log_info "为专用用户配置 Python 3.11 环境..."

        # 创建用户的 bash 配置文件，设置 Python 别名
        cat >> "/home/$username/.bashrc" << EOF

# Python 3.11 环境配置
if command -v python3.11 &> /dev/null; then
    alias python3='python3.11'
    alias pip3='pip3.11'
    export PATH="/usr/bin/python3.11:\$PATH"
fi

# Flowclip 环境变量
export DATABASE_URL="mysql+aiomysql://youtube_user:youtube_password@localhost:3306/youtube_slicer?charset=utf8mb4"
export REDIS_URL="redis://localhost:6379"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0="
export MINIO_SECRET_KEY="TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k="
export MINIO_BUCKET_NAME="youtube-videos"
export PUBLIC_IP="\$(hostname -I | awk '{print \$1}')"

# Node.js 环境
export NODE_PATH="/usr/lib/node_modules"
EOF
    fi

    # 创建 .env 文件模板
    cat > "$PROJECT_DIR/.env" << EOF
# Database Configuration
DATABASE_URL=mysql+aiomysql://youtube_user:youtube_password@localhost:3306/youtube_slicer?charset=utf8mb4

# Redis Configuration
REDIS_URL=redis://localhost:6379

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0=
MINIO_SECRET_KEY=TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k=
MINIO_BUCKET_NAME=youtube-videos

# Security
SECRET_KEY=your-secret-key-change-in-production

# Frontend Configuration
FRONTEND_URL=http://localhost:3000
BACKEND_PUBLIC_URL=http://127.0.0.1:8001

# Development
DEBUG=true

# TUS Configuration
TUS_API_URL=http://localhost:8000
TUS_UPLOAD_URL=http://localhost:1080
TUS_CALLBACK_PORT=9090
TUS_CALLBACK_HOST=localhost
TUS_FILE_SIZE_THRESHOLD_MB=10
TUS_ENABLE_ROUTING=true
TUS_MAX_RETRIES=3
TUS_TIMEOUT_SECONDS=1800

# Public IP
PUBLIC_IP=\$(hostname -I | awk '{print \$1}')
EOF

    chown "$username:$username" "$PROJECT_DIR/.env"

    log_success "用户环境设置完成"
    echo "$PROJECT_DIR"
}

# 创建系统服务配置
create_system_services() {
    log_info "创建系统服务配置..."

    # 创建媒体文件目录
    mkdir -p /opt/flowclip/media
    chown -R "$SERVICE_USER:$SERVICE_USER" /opt/flowclip

    # 创建 Flowclip 服务目录
    mkdir -p /etc/flowclip
}

# 显示安装完成信息
show_completion_info() {
    local project_dir="$1"

    echo
    echo "========================================"
    echo "       Flowclip 系统初始化完成！"
    echo "========================================"
    echo
    echo "已安装的组件："
    echo "  ✓ MySQL 8.0 (端口: 3306)"
    echo "  ✓ Redis (端口: 6379)"
    echo "  ✓ MinIO (API: 9000, Console: 9001)"
    echo "  ✓ Node.js 18.x + PM2"
    echo "  ✓ Python 3.11"
    echo "  ✓ FFmpeg + 视频处理库"
    echo
    echo "项目位置: $project_dir"
    echo "专用用户: $SERVICE_USER"
    echo
    echo "数据库信息："
    echo "  数据库: youtube_slicer"
    echo "  用户: youtube_user / youtube_password"
    echo
    echo "MinIO 访问信息："
    echo "  API: http://$(hostname -I | awk '{print $1}'):9000"
    echo "  Console: http://$(hostname -I | awk '{print $1}'):9001"
    echo "  用户: i4W5jAG1j9w2MheEQ7GmYEotBrkAaIPSmLRQa6Iruc0="
    echo "  密码: TcFA+qUwvCnikxANs7k/HX7oZz2zEjLo3RakL1kZt5k="
    echo
    echo "接下来请使用以下命令切换到专用用户："
    echo "  su - $SERVICE_USER"
    echo "  cd EchoClip"
    echo "  # 配置应用环境并启动服务"
    echo
    echo "注意：请确保将当前项目代码复制到 $project_dir"
    echo
}

# 主函数
main() {
    echo "========================================"
    echo "    Flowclip 系统初始化脚本 (root)"
    echo "========================================"
    echo
    echo "此脚本将安装以下组件："
    echo "  • MySQL 8.0 数据库"
    echo "  • Redis 缓存服务"
    echo "  • MinIO 对象存储"
    echo "  • Node.js 18.x 运行环境"
    echo "  • Python 3.11 开发环境"
    echo "  • FFmpeg 等媒体处理库"
    echo "  • 系统依赖和工具"
    echo

    # 执行系统环境检查
    check_system_environment

    # 检测操作系统
    detect_os

    log_info "=== 开始系统初始化 ==="

    # 系统初始化
    init_system

    # 安装 Python 3.11
    install_python311

    # 安装核心组件
    log_info "=== 安装核心组件 ==="
    install_mysql
    install_redis
    install_minio
    install_nodejs

    # 安装项目依赖
    install_system_deps

    # 创建系统服务配置
    create_system_services

    # 创建专用用户
    create_flowclip_user

    # 设置用户环境
    project_dir=$(setup_user_environment)

    # 显示完成信息
    show_completion_info "$project_dir"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi