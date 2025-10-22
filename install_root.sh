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

# 生成随机密码函数
generate_password() {
    local length=${1:-16}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# 生成动态密码
MYSQL_ROOT_PASSWORD=$(generate_password 20)
MYSQL_APP_PASSWORD=$(generate_password 20)
MINIO_ACCESS_KEY=$(generate_password 32)
MINIO_SECRET_KEY=$(generate_password 40)
APP_SECRET_KEY=$(generate_password 32)

# 保存密码到文件
PASSWORD_FILE="/root/flowclip_credentials.txt"
export PASSWORD_FILE  # 导出变量确保子进程可访问
save_credentials() {
    cat > "$PASSWORD_FILE" << EOF
========================================
    Flowclip 系统凭据信息
========================================
生成时间: $(date)
服务器IP: $(hostname -I | awk '{print $1}')

数据库凭据:
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_APP_PASSWORD=$MYSQL_APP_PASSWORD
MYSQL_DATABASE=youtube_slicer
MYSQL_USER=youtube_user

MinIO凭据:
MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY
MINIO_SECRET_KEY=$MINIO_SECRET_KEY
MINIO_BUCKET=youtube-videos

应用凭据:
SECRET_KEY=$APP_SECRET_KEY

========================================
重要提醒:
1. 请妥善保管此文件，建议删除或移至安全位置
2. 在生产环境中，请修改这些默认密码
3. 定期更换密码以确保系统安全
========================================
EOF
    chmod 600 "$PASSWORD_FILE"
}

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
    if [[ $available_mem -lt 1024 ]]; then
        log_error "可用内存不足1GB (当前: ${available_mem}MB)，无法正常安装和运行"
        exit 1
    elif [[ $available_mem -lt 2048 ]]; then
        log_warning "可用内存较少 (当前: ${available_mem}MB)，建议至少2GB以获得更好性能"
        log_info "当前配置可以运行，但处理大文件时可能较慢"
        read -p "是否继续安装? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "安装已取消"
            exit 0
        fi
        log_success "内存检查通过 (可用: ${available_mem}MB)"
    else
        log_success "内存检查通过 (可用: ${available_mem}MB)"
    fi

    # 检查必要端口是否被占用并自动处理
    local ports_to_check=("3306" "6379" "9000" "9001")
    local occupied_ports=()
    local services_to_stop=()

    for port in "${ports_to_check[@]}"; do
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            occupied_ports+=("$port")

            # 检测对应的服务
            case $port in
                3306)
                    if systemctl is-active --quiet mysql 2>/dev/null || systemctl is-active --quiet mysqld 2>/dev/null; then
                        services_to_stop+=("MySQL (端口: $port)")
                    fi
                    ;;
                6379)
                    if systemctl is-active --quiet redis 2>/dev/null || systemctl is-active --quiet redis-server 2>/dev/null; then
                        services_to_stop+=("Redis (端口: $port)")
                    fi
                    ;;
                9000|9001)
                    if systemctl is-active --quiet minio 2>/dev/null; then
                        services_to_stop+=("MinIO (端口: $port)")
                    fi
                    ;;
            esac
        fi
    done

    if [[ ${#occupied_ports[@]} -gt 0 ]]; then
        log_info "检测到以下端口已被占用: ${occupied_ports[*]}"

        if [[ ${#services_to_stop[@]} -gt 0 ]]; then
            log_info "将停止以下相关服务以确保正确安装:"
            for service in "${services_to_stop[@]}"; do
                log_info "  • $service"
            done

            log_info "正在停止现有服务..."

            # 停止MySQL服务
            if systemctl is-active --quiet mysql 2>/dev/null; then
                log_info "停止 MySQL 服务..."
                systemctl stop mysql
            elif systemctl is-active --quiet mysqld 2>/dev/null; then
                log_info "停止 MySQL 服务 (mysqld)..."
                systemctl stop mysqld
            fi

            # 停止Redis服务
            if systemctl is-active --quiet redis 2>/dev/null; then
                log_info "停止 Redis 服务..."
                systemctl stop redis
            elif systemctl is-active --quiet redis-server 2>/dev/null; then
                log_info "停止 Redis 服务 (redis-server)..."
                systemctl stop redis-server
            fi

            # 停止MinIO服务
            if systemctl is-active --quiet minio 2>/dev/null; then
                log_info "停止 MinIO 服务..."
                systemctl stop minio
            fi

            # 等待服务完全停止
            sleep 3

            # 重新检查端口
            local still_occupied=()
            for port in "${occupied_ports[@]}"; do
                if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                    still_occupied+=("$port")
                fi
            done

            if [[ ${#still_occupied[@]} -eq 0 ]]; then
                log_success "所有相关服务已停止，端口现在可用"
            else
                log_warning "以下端口仍被占用: ${still_occupied[*]}"
                log_info "可能有其他进程在使用这些端口，但继续安装"
            fi
        else
            log_warning "端口被占用但未检测到相关系统服务"
            log_info "可能有其他应用程序在使用这些端口"
            read -p "是否继续安装? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_info "安装已取消"
                exit 0
            fi
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

            if mysql -u debian-sys-maint -p"$debian_password" -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD'; FLUSH PRIVILEGES;" &>/dev/null; then
                log_success "通过debian-sys-maint用户成功重置root密码"
                mysql_configured=true
            fi
        fi

        # 方法2: 尝试无密码root连接
        if [[ "$mysql_configured" == false ]] && mysql -u root -e "SELECT 1;" &>/dev/null; then
            log_info "发现root无密码访问，进行配置..."
            mysql -u root -e "
                ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';
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
                ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';
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
                        ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';
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
                UPDATE user SET authentication_string=PASSWORD('$MYSQL_ROOT_PASSWORD') WHERE User='root';
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
        if mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1;" &>/dev/null; then
            log_success "MySQL安全配置完成"
        else
            log_error "MySQL配置验证失败，请手动配置"
            log_info "手动配置命令："
            log_info "1. sudo mysql"
            log_info "2. ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '$MYSQL_ROOT_PASSWORD';"
            log_info "3. FLUSH PRIVILEGES;"
            log_info "4. EXIT;"
            read -p "配置完成后按回车继续..."
        fi

        # 配置 MySQL 允许外部连接（支持 Docker 主机名）
        log_info "配置 MySQL 允许外部连接..."

        # 修改 MySQL 绑定地址，允许通过主机名连接
        if [[ -f "/etc/mysql/mysql.conf.d/mysqld.cnf" ]]; then
            # 备份原配置文件
            cp /etc/mysql/mysql.conf.d/mysqld.cnf /etc/mysql/mysql.conf.d/mysqld.cnf.backup.$(date +%Y%m%d_%H%M%S)

            # 修改绑定地址从 127.0.0.1 到 0.0.0.0
            sed -i 's/bind-address\t\t= 127.0.0.1/bind-address\t\t= 0.0.0.0/' /etc/mysql/mysql.conf.d/mysqld.cnf

            # 重启 MySQL 服务使配置生效
            systemctl restart mysql

            # 等待 MySQL 完全启动
            sleep 5

            # 验证配置是否生效
            if netstat -tuln | grep -q ":3306.*0.0.0.0"; then
                log_success "MySQL 已配置为接受外部连接"
            else
                log_warning "MySQL 外部连接配置可能需要手动验证"
            fi
        else
            log_warning "MySQL 配置文件未找到，跳过外部连接配置"
        fi

        # 创建应用数据库和用户
        log_info "创建应用数据库和用户..."

        # 先创建数据库
        mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS youtube_slicer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" || {
            log_error "数据库创建失败"
            return 1
        }

        # 删除可能存在的用户（确保使用新密码）
        mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP USER IF EXISTS 'youtube_user'@'localhost';" || {
            log_warning "删除现有用户失败，可能用户不存在"
        }
        mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP USER IF EXISTS 'youtube_user'@'%';" || {
            log_warning "删除现有通配符用户失败，可能用户不存在"
        }

        # 创建新用户并设置权限（支持 localhost 和外部连接）
        mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
            CREATE USER 'youtube_user'@'localhost' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
            CREATE USER 'youtube_user'@'%' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
            GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'localhost';
            GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'%';
            FLUSH PRIVILEGES;
        " || {
            log_error "应用用户创建失败"
            return 1
        }

        # 立即验证用户创建是否成功
        log_info "验证应用用户创建..."
        if mysql -uyoutube_user -p"$MYSQL_APP_PASSWORD" -e "USE youtube_slicer; SELECT 'User verification successful' as status;" &>/dev/null; then
            log_success "✓ 应用用户创建并验证成功"
        else
            log_error "❌ 应用用户创建失败，尝试手动修复..."

            # 尝试手动修复
            log_info "手动修复应用用户..."
            mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
                DROP USER IF EXISTS 'youtube_user'@'localhost';
                CREATE USER 'youtube_user'@'localhost' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
                GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'localhost';
                FLUSH PRIVILEGES;
            " || {
                log_error "手动修复失败，需要人工干预"
                log_info "请手动运行以下命令："
                log_info "mysql -uroot -p'$MYSQL_ROOT_PASSWORD' -e \""
                log_info "    DROP USER IF EXISTS 'youtube_user'@'localhost;"
                log_info "    CREATE USER 'youtube_user'@'localhost' IDENTIFIED BY '$MYSQL_APP_PASSWORD';"
                log_info "    GRANT ALL PRIVILEGES ON youtube_slicer.* TO 'youtube_user'@'localhost;"
                log_info "    FLUSH PRIVILEGES;\""
                return 1
            }

            # 再次验证
            if mysql -uyoutube_user -p"$MYSQL_APP_PASSWORD" -e "USE youtube_slicer; SELECT 'Manual fix successful' as status;" &>/dev/null; then
                log_success "✓ 手动修复成功，应用用户现在可用"
            else
                log_error "❌ 手动修复仍然失败"
                return 1
            fi
        fi

        log_success "应用数据库和用户创建完成"

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

        # 启动并启用 Redis (处理服务名差异)
        if systemctl restart redis-server.service; then
            log_info "Redis 服务启动成功 (redis-server)"
            systemctl enable redis-server.service
        elif systemctl restart redis.service; then
            log_info "Redis 服务启动成功 (redis)"
            systemctl enable redis.service
        else
            log_error "Redis 服务启动失败"
            return 1
        fi

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
    cat > /etc/default/minio << EOF
# MinIO local configuration file
# Volume to be used for MinIO server.
MINIO_VOLUMES="/opt/minio/data"

# User and group
MINIO_ROOT_USER=$MINIO_ACCESS_KEY
MINIO_ROOT_PASSWORD=$MINIO_SECRET_KEY

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
    log_info "安装 Node.js 22.x..."

    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        # 安装 NodeSource 仓库
        curl -fsSL https://deb.nodesource.com/setup_22.x | bash -

        # 安装 Node.js
        apt install -y nodejs

        log_success "Node.js 安装完成: $(node -v)"

    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        # 安装 NodeSource 仓库
        curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -

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

    # 配置 Docker 兼容的主机名映射
    log_info "配置 Docker 兼容的主机名映射..."

    # 备份原始 hosts 文件
    cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S)

    # 添加 Docker 服务的主机名映射
    local server_ip=$(hostname -I | awk '{print $1}')

    # 检查是否已存在映射，避免重复添加
    if ! grep -q "redis localhost" /etc/hosts; then
        echo "# Flowclip Docker 服务映射" >> /etc/hosts
        echo "$server_ip redis" >> /etc/hosts
        echo "$server_ip mysql" >> /etc/hosts
        echo "$server_ip minio" >> /etc/hosts
        log_success "Docker 主机名映射已添加到 /etc/hosts"
    else
        log_info "Docker 主机名映射已存在，跳过添加"
    fi

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

    # 复制凭据文件到用户目录（确保用户可以读取）
    if [[ -f "$PASSWORD_FILE" ]]; then
        log_info "=== 开始复制凭据文件 ==="

        # 显示源文件信息
        log_info "源文件信息:"
        log_info "  路径: $PASSWORD_FILE"
        log_info "  大小: $(stat -c %s "$PASSWORD_FILE" | numfmt --to=iec) 字节"
        log_info "  时间: $(stat -c %y "$PASSWORD_FILE")"
        log_info "  权限: $(stat -c %A "$PASSWORD_FILE")"
        log_info "  用户: $(stat -c %U "$PASSWORD_FILE"):$(stat -c %G "$PASSWORD_FILE")"

        # 检查源文件内容
        log_info "源文件内容预览:"
        log_info "  生成时间: $(grep "生成时间:" "$PASSWORD_FILE")"
        log_info "  SECRET_KEY前6位: $(grep "^SECRET_KEY=" "$PASSWORD_FILE" | cut -d'=' -f2 | cut -c1-6)..."

        # 复制到项目目录
        log_info "复制操作 1/2: 复制到项目目录..."
        log_info "  源文件: $PASSWORD_FILE"
        log_info "  目标文件: $PROJECT_DIR/credentials.txt"

        # 检查目标文件是否存在
        if [[ -f "$PROJECT_DIR/credentials.txt" ]]; then
            log_info "  目标文件已存在，将被覆盖"
            log_info "  原文件大小: $(stat -c %s "$PROJECT_DIR/credentials.txt" | numfmt --to=iec) 字节"
        else
            log_info "  目标文件不存在，将创建新文件"
        fi

        # 执行复制
        if cp -f "$PASSWORD_FILE" "$PROJECT_DIR/credentials.txt"; then
            log_success "  ✅ 复制命令执行成功"

            # 设置权限
            if chown "$username:$username" "$PROJECT_DIR/credentials.txt"; then
                log_success "  ✅ 权限设置成功: $username:$username"
            else
                log_error "  ❌ 权限设置失败"
            fi

            if chmod 600 "$PROJECT_DIR/credentials.txt"; then
                log_success "  ✅ 文件权限设置成功: 600"
            else
                log_error "  ❌ 文件权限设置失败"
            fi

            # 验证复制结果
            log_info "  验证复制结果:"
            log_info "  新文件大小: $(stat -c %s "$PROJECT_DIR/credentials.txt" | numfmt --to=iec) 字节"
            log_info "  新文件时间: $(stat -c %y "$PROJECT_DIR/credentials.txt")"
            log_info "  新文件权限: $(stat -c %A "$PROJECT_DIR/credentials.txt")"

        else
            log_error "  ❌ 复制命令执行失败"
        fi

        # 也复制到用户主目录（方便访问）
        log_info "复制操作 2/2: 复制到用户主目录..."
        log_info "  源文件: $PASSWORD_FILE"
        log_info "  目标文件: /home/$username/credentials.txt"

        # 检查目标文件是否存在
        if [[ -f "/home/$username/credentials.txt" ]]; then
            log_info "  目标文件已存在，将被覆盖"
            log_info "  原文件大小: $(stat -c %s "/home/$username/credentials.txt" | numfmt --to=iec) 字节"
        else
            log_info "  目标文件不存在，将创建新文件"
        fi

        # 执行复制
        if cp -f "$PASSWORD_FILE" "/home/$username/credentials.txt"; then
            log_success "  ✅ 复制命令执行成功"

            # 设置权限
            if chown "$username:$username" "/home/$username/credentials.txt"; then
                log_success "  ✅ 权限设置成功: $username:$username"
            else
                log_error "  ❌ 权限设置失败"
            fi

            if chmod 600 "/home/$username/credentials.txt"; then
                log_success "  ✅ 文件权限设置成功: 600"
            else
                log_error "  ❌ 文件权限设置失败"
            fi

            # 验证复制结果
            log_info "  验证复制结果:"
            log_info "  新文件大小: $(stat -c %s "/home/$username/credentials.txt" | numfmt --to=iec) 字节"
            log_info "  新文件时间: $(stat -c %y "/home/$username/credentials.txt")"
            log_info "  新文件权限: $(stat -c %A "/home/$username/credentials.txt")"

        else
            log_error "  ❌ 复制命令执行失败"
        fi

        # 最终验证
        log_info "=== 最终验证 ==="
        local source_secret=$(grep "^SECRET_KEY=" "$PASSWORD_FILE" | cut -d'=' -f2)
        local project_secret=$(grep "^SECRET_KEY=" "$PROJECT_DIR/credentials.txt" | cut -d'=' -f2)
        local home_secret=$(grep "^SECRET_KEY=" "/home/$username/credentials.txt" | cut -d'=' -f2)

        log_info "SECRET_KEY对比:"
        log_info "  源文件: ${source_secret:0:8}..."
        log_info "  项目目录: ${project_secret:0:8}..."
        log_info "  用户主目录: ${home_secret:0:8}..."

        if [[ "$source_secret" == "$project_secret" ]] && [[ "$source_secret" == "$home_secret" ]]; then
            log_success "🎉 所有凭据文件复制验证成功！"
        else
            log_error "❌ 凭据文件复制验证失败！"
            log_error "  源文件与项目目录文件不匹配: ${source_secret:0:8}... vs ${project_secret:0:8}..."
            log_error "  源文件与用户主目录文件不匹配: ${source_secret:0:8}... vs ${home_secret:0:8}..."
        fi

        log_success "=== 凭据文件复制操作完成 ==="
        log_info "📁 文件位置:"
        log_info "  • 源文件: $PASSWORD_FILE"
        log_info "  • 项目目录: $PROJECT_DIR/credentials.txt"
        log_info "  • 用户主目录: /home/$username/credentials.txt"
    else
        log_error "❌ 凭据文件不存在: $PASSWORD_FILE"
        log_info "请检查 save_credentials() 函数是否正确执行"
    fi

    log_success "用户环境设置完成"
    echo "$PROJECT_DIR"
}

# 创建系统服务配置
create_system_services() {
    log_info "创建系统服务配置..."

    # 确保用户存在
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_error "用户 $SERVICE_USER 不存在，无法设置目录权限"
        log_info "请确保用户创建步骤已完成"
        return 1
    fi

    # 创建媒体文件目录
    mkdir -p /opt/flowclip/media
    chown -R "$SERVICE_USER:$SERVICE_USER" /opt/flowclip

    # 创建 Flowclip 服务目录
    mkdir -p /etc/flowclip
    chown -R "$SERVICE_USER:$SERVICE_USER" /etc/flowclip

    log_success "系统服务配置创建完成"
}

# 使用MinIO客户端验证
verify_minio_with_mc() {
    local minio_endpoint="$1"
    local minio_access_key="$2"
    local minio_secret_key="$3"
    local failed_services=("$@")

    # 配置MinIO客户端
    log_info "配置MinIO客户端..."
    if mc alias set minio-verify "$minio_endpoint" "$minio_access_key" "$minio_secret_key" &>/dev/null; then
        log_success "✓ MinIO客户端配置成功"

        # 测试连接
        if mc ls minio-verify &>/dev/null; then
            log_success "✓ MinIO连接验证成功"

            # 检查或创建存储桶
            local bucket_name="youtube-videos"
            if mc ls minio-verify/"$bucket_name" &>/dev/null; then
                log_success "✓ MinIO存储桶已存在且可访问"
                test_minio_bucket_permissions_with_mc "$bucket_name" "$minio_endpoint" "$minio_access_key" "$minio_secret_key"
            else
                log_info "MinIO存储桶不存在，尝试创建..."
                if mc mb minio-verify/"$bucket_name" &>/dev/null; then
                    log_success "✓ MinIO存储桶创建成功"
                    test_minio_bucket_permissions_with_mc "$bucket_name" "$minio_endpoint" "$minio_access_key" "$minio_secret_key"
                else
                    log_error "✗ MinIO存储桶创建失败"
                    failed_services+=("MinIO存储桶创建")
                fi
            fi
        else
            log_error "✗ MinIO客户端连接失败"
            failed_services+=("MinIO连接")
        fi

        # 清理客户端配置
        mc alias remove minio-verify &>/dev/null || true
    else
        log_error "✗ MinIO客户端配置失败"
        failed_services+=("MinIO配置")
    fi

    return 0
}

# 使用MinIO客户端测试存储桶权限
test_minio_bucket_permissions_with_mc() {
    local bucket_name="$1"

    # 测试存储桶写权限
    log_info "测试MinIO存储桶权限..."
    local test_file="/tmp/minio-verify-$(date +%s).txt"
    echo "MinIO permission test - $(date)" > "$test_file"

    if mc cp "$test_file" "minio-verify/$bucket_name/minio-permission-test.txt" &>/dev/null; then
        log_success "✓ MinIO存储桶写权限验证成功"

        # 测试读权限
        if mc cat "minio-verify/$bucket_name/minio-permission-test.txt" &>/dev/null; then
            log_success "✓ MinIO存储桶读权限验证成功"
        else
            log_warning "⚠ MinIO存储桶读权限验证失败"
        fi

        # 测试删除权限
        if mc rm "minio-verify/$bucket_name/minio-permission-test.txt" &>/dev/null; then
            log_success "✓ MinIO存储桶删除权限验证成功"
        else
            log_warning "⚠ MinIO存储桶删除权限验证失败"
        fi

        log_success "✅ MinIO存储桶完全就绪，权限验证通过"
    else
        log_error "✗ MinIO存储桶写权限验证失败"
    fi

    # 清理临时文件
    rm -f "$test_file"
}

# 使用curl的备用验证方法
verify_minio_with_curl() {
    local minio_endpoint="$1"
    local failed_services=("$@")

    log_info "尝试curl备用方法（适用于旧版本MinIO）..."

    # 尝试简单的无认证操作
    local health_check=$(curl -s -w "%{http_code}" -o /dev/null "$minio_endpoint/minio/health/live")
    if [[ "$health_check" == "200" ]]; then
        log_success "✓ MinIO API健康检查通过"

        # 尝试简单的根路径请求（无认证）
        local root_test=$(curl -s -w "%{http_code}" -o /dev/null "$minio_endpoint/")
        if [[ "$root_test" == "403" ]] || [[ "$root_test" == "200" ]]; then
            log_success "✓ MinIO服务可访问（建议安装客户端进行完整测试）"

            log_info "安装MinIO客户端的建议："
            log_info "  wget https://dl.min.io/client/mc/release/linux-amd64/mc"
            log_info "  chmod +x mc"
            log_info "  sudo mv mc /usr/local/bin/"

            return 0
        else
            log_warning "⚠ MinIO根路径访问异常: HTTP $root_test"
            failed_services+=("MinIO访问")
        fi
    else
        log_error "✗ MinIO API健康检查失败: HTTP $health_check"
        failed_services+=("MinIO健康检查")
    fi

    return 0
}

# 验证所有服务
verify_all_services() {
    log_info "=== 开始服务验证 ==="
    local failed_services=()

    # 从凭据文件读取密码（确保使用正确的密码）
    local mysql_root_password mysql_app_password minio_access_key minio_secret_key

    # 使用绝对路径避免变量作用域问题
    local credentials_file="/root/flowclip_credentials.txt"

    if [[ -f "$credentials_file" ]]; then
        log_info "从凭据文件读取密码: $credentials_file"
        # 使用标准化的KEY=VALUE格式解析
        mysql_root_password=$(grep "^MYSQL_ROOT_PASSWORD=" "$credentials_file" | cut -d'=' -f2)
        mysql_app_password=$(grep "^MYSQL_APP_PASSWORD=" "$credentials_file" | cut -d'=' -f2)
        minio_access_key=$(grep "^MINIO_ACCESS_KEY=" "$credentials_file" | cut -d'=' -f2)
        minio_secret_key=$(grep "^MINIO_SECRET_KEY=" "$credentials_file" | cut -d'=' -f2)

        log_info "密码读取完成 - Root:${#mysql_root_password}, App:${#mysql_app_password}"
        log_info "验证解析结果: MinIO_KEY长度:${#minio_access_key}"
    else
        log_warning "凭据文件不存在: $credentials_file"
        log_info "尝试使用全局变量..."
        mysql_root_password="$MYSQL_ROOT_PASSWORD"
        mysql_app_password="$MYSQL_APP_PASSWORD"
        minio_access_key="$MINIO_ACCESS_KEY"
        minio_secret_key="$MINIO_SECRET_KEY"
    fi

    log_info "使用凭据进行验证..."

    # 验证MySQL服务
    log_info "验证MySQL服务..."
    if [[ -n "$mysql_root_password" ]]; then
        # 使用临时配置文件避免命令行显示密码
        echo "[client]" > /tmp/mysql_root_temp.cnf
        echo "user=root" >> /tmp/mysql_root_temp.cnf
        echo "password=$mysql_root_password" >> /tmp/mysql_root_temp.cnf
        chmod 600 /tmp/mysql_root_temp.cnf

        if mysql --defaults-extra-file=/tmp/mysql_root_temp.cnf -e "SELECT 1;" &>/dev/null; then
            log_success "✓ MySQL Root用户连接成功"
        else
            log_error "✗ MySQL Root用户连接失败"
            failed_services+=("MySQL Root")
        fi
        rm -f /tmp/mysql_root_temp.cnf
    else
        log_warning "⚠ MySQL Root密码为空，跳过验证"
    fi

    # 验证应用数据库
    if [[ -n "$mysql_app_password" ]]; then
        # 使用mysql_config_editor避免命令行显示密码
        echo "[client]" > /tmp/mysql_temp.cnf
        echo "user=youtube_user" >> /tmp/mysql_temp.cnf
        echo "password=$mysql_app_password" >> /tmp/mysql_temp.cnf
        chmod 600 /tmp/mysql_temp.cnf

        if mysql --defaults-extra-file=/tmp/mysql_temp.cnf -e "USE youtube_slicer; SELECT 'Database connection successful' as status;" &>/dev/null; then
            log_success "✓ MySQL应用数据库连接成功"
        else
            log_error "✗ MySQL应用数据库连接失败"
            log_info "调试信息: 使用密码长度 ${#mysql_app_password}"
            failed_services+=("MySQL应用数据库")
        fi
        rm -f /tmp/mysql_temp.cnf
    else
        log_warning "⚠ MySQL应用数据库密码为空，跳过验证"
        log_info "可以通过以下命令手动验证："
        log_info "mysql -uyoutube_user -p\$(grep '应用数据库密码:' $PASSWORD_FILE | awk '{print \$4}') youtube_slicer"
    fi

    # 验证Redis服务
    log_info "验证Redis服务..."
    if redis-cli ping &>/dev/null; then
        # 测试Redis基本操作
        if redis-cli set test_key "test_value" &>/dev/null && redis-cli get test_key &>/dev/null; then
            redis-cli del test_key &>/dev/null
            log_success "✓ Redis服务运行正常"
        else
            log_error "✗ Redis服务读写测试失败"
            failed_services+=("Redis读写")
        fi
    else
        log_error "✗ Redis服务连接失败"
        failed_services+=("Redis连接")
    fi

    # 验证MinIO服务
    log_info "验证MinIO服务..."
    local minio_endpoint="http://localhost:9000"

    # 检查MinIO API健康状态
    if curl -s -f "$minio_endpoint/minio/health/live" &>/dev/null; then
        log_success "✓ MinIO API服务运行正常"

        # 验证MinIO控制台
        if curl -s -f "http://localhost:9001" &>/dev/null; then
            log_success "✓ MinIO控制台可访问"
        else
            log_warning "⚠ MinIO控制台可能需要更多时间启动"
        fi

        # 测试MinIO认证和权限
        log_info "测试MinIO认证和存储桶权限..."

        # 检查是否安装了MinIO客户端
        if command -v mc &> /dev/null; then
            log_info "使用MinIO客户端进行验证..."
            verify_minio_with_mc "$minio_endpoint" "$minio_access_key" "$minio_secret_key" "${failed_services[@]}"
        else
            log_info "MinIO客户端未安装，尝试curl验证..."
            verify_minio_with_curl "$minio_endpoint" "${failed_services[@]}"
        fi
    else
        log_error "✗ MinIO API服务不可访问"
        failed_services+=("MinIO API")
    fi

    # 验证Node.js和PM2
    log_info "验证Node.js环境..."
    if command -v node &>/dev/null && node --version &>/dev/null; then
        local node_version=$(node --version)
        if [[ "$node_version" == v22* ]]; then
            log_success "✓ Node.js $node_version 版本正确"
        else
            log_warning "⚠ Node.js版本: $node_version (推荐v22.x)"
        fi
    else
        log_error "✗ Node.js未正确安装"
        failed_services+=("Node.js")
    fi

    if command -v pm2 &>/dev/null; then
        log_success "✓ PM2进程管理器安装成功"
    else
        log_error "✗ PM2未正确安装"
        failed_services+=("PM2")
    fi

    # 验证Python环境
    log_info "验证Python环境..."
    if command -v python3.11 &>/dev/null; then
        local python_version=$(python3.11 --version 2>&1)
        log_success "✓ Python $python_version 安装成功"
    else
        log_warning "⚠ Python 3.11 未找到，使用系统Python"
        if command -v python3 &>/dev/null; then
            log_info "✓ 系统Python $(python3 --version 2>&1) 可用"
        else
            log_error "✗ Python环境未正确配置"
            failed_services+=("Python")
        fi
    fi

    # 验证FFmpeg
    log_info "验证FFmpeg..."
    if command -v ffmpeg &>/dev/null; then
        local ffmpeg_version=$(ffmpeg -version 2>&1 | head -n1)
        log_success "✓ FFmpeg安装成功: $ffmpeg_version"
    else
        log_error "✗ FFmpeg未正确安装"
        failed_services+=("FFmpeg")
    fi

    # 验证用户和目录权限
    log_info "验证用户和目录权限..."
    if id "$SERVICE_USER" &>/dev/null; then
        log_success "✓ 专用用户 $SERVICE_USER 创建成功"

        if [[ -d "/opt/flowclip" ]] && [[ "$(stat -c %U /opt/flowclip)" == "$SERVICE_USER" ]]; then
            log_success "✓ 系统目录权限配置正确"
        else
            log_warning "⚠ 系统目录权限可能需要检查"
        fi

        if [[ -d "$PROJECT_DIR" ]]; then
            log_success "✓ 项目目录创建成功: $PROJECT_DIR"
        else
            log_error "✗ 项目目录创建失败"
            failed_services+=("项目目录")
        fi
    else
        log_error "✗ 专用用户 $SERVICE_USER 创建失败"
        failed_services+=("专用用户")
    fi

    # 验证端口占用
    log_info "验证端口状态..."
    local required_ports=("3306" "6379" "9000" "9001")
    local port_services=("MySQL" "Redis" "MinIO-API" "MinIO-Console")

    for i in "${!required_ports[@]}"; do
        local port="${required_ports[$i]}"
        local service="${port_services[$i]}"

        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            log_success "✓ $service 端口 $port 正在监听"
        else
            log_warning "⚠ $service 端口 $port 未监听 (可能还在启动)"
        fi
    done

# 生成验证报告
    echo
    echo "========================================"
    echo "         服务验证报告"
    echo "========================================"

    if [[ ${#failed_services[@]} -eq 0 ]]; then
        echo "🎉 所有服务验证通过！系统已准备就绪。"
        log_success "系统验证: 100% 通过"
    else
        echo "⚠️  发现以下问题需要关注:"
        for service in "${failed_services[@]}"; do
            echo "   • $service"
        done
        echo
        echo "💡 建议操作:"
        echo "   1. 检查对应服务的日志文件"
        echo "   2. 确认服务状态: systemctl status <service>"
        echo "   3. 查看凭据文件: $PASSWORD_FILE"
        echo "   4. 重启有问题的服务"
        echo
        log_warning "系统验证: 发现 ${#failed_services[@]} 个问题"
    fi

    echo
    echo "📋 快速诊断命令:"
    echo "   MySQL状态: systemctl status mysql"
    echo "   Redis状态: systemctl status redis-server"
    echo "   MinIO状态: systemctl status minio"
    echo "   查看日志: journalctl -u <service> -f"
    echo "   端口检查: netstat -tuln | grep -E '3306|6379|9000|9001'"
    echo "========================================"
    echo
}

# 显示安装完成信息
show_completion_info() {
    local project_dir="$1"

    # 凭据文件已在脚本开始时生成，无需重复生成
    log_info "使用已生成的凭据文件: $PASSWORD_FILE"

    # 执行完整的服务验证
    verify_all_services

    echo
    echo "========================================"
    echo "       Flowclip 系统初始化完成！"
    echo "========================================"
    echo
    echo "已安装的组件："
    echo "  ✓ MySQL 8.0 (端口: 3306)"
    echo "  ✓ Redis (端口: 6379)"
    echo "  ✓ MinIO (API: 9000, Console: 9001)"
    echo "  ✓ Node.js 22.x + PM2"
    echo "  ✓ Python 3.11"
    echo "  ✓ FFmpeg + 视频处理库"
    echo
    echo "项目位置: $project_dir"
    echo "专用用户: $SERVICE_USER"
    echo
    echo "🔐 安全凭据已生成并保存到: $PASSWORD_FILE"
    echo "   包含所有数据库、MinIO和应用密钥"
    echo "   文件权限: 600 (仅root可读写)"
    echo
    echo "MinIO 访问信息："
    echo "  API: http://$(hostname -I | awk '{print $1}'):9000"
    echo "  Console: http://$(hostname -I | awk '{print $1}'):9001"
    echo "  用户: $MINIO_ACCESS_KEY"
    echo "  密码: $MINIO_SECRET_KEY"
    echo
    echo "接下来请使用以下命令切换到专用用户："
    echo "  su - $SERVICE_USER"
    echo "  cd EchoClip"
    echo "  # 配置应用环境并启动服务"
    echo
    echo "⚠️  安全提醒："
    echo "  1. 请妥善保管凭据文件 $PASSWORD_FILE"
    echo "  2. 建议将凭据文件备份到安全位置"
    echo "  3. 生产环境请修改默认密码"
    echo "  4. 删除不需要的凭据文件"
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

    # 创建专用用户
    create_flowclip_user

    # 创建系统服务配置
    create_system_services

    # 生成并保存凭据文件（确保在用户环境设置之前）
    log_info "生成系统凭据..."
    save_credentials

    # 设置用户环境
    project_dir=$(setup_user_environment)

    # 显示完成信息
    show_completion_info "$project_dir"
}

# 脚本入口
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]] || [[ -z "${BASH_SOURCE[0]:-}" ]]; then
    main "$@"
fi