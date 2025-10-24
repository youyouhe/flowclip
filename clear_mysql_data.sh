#!/bin/bash

# EchoClip MySQL数据库清理脚本
# 用于清空所有表数据，提供干净的测试环境

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 项目配置
PROJECT_USER="${PROJECT_USER:-flowclip}"
MYSQL_USER="${MYSQL_USER:-youtube_user}"
MYSQL_DATABASE="${MYSQL_DATABASE:-youtube_slicer}"
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
CREDENTIALS_FILE="${CREDENTIALS_FILE:-/home/flowclip/credentials.txt}"

# 显示脚本信息
echo "========================================"
echo "    EchoClip MySQL 数据库清理脚本"
echo "========================================"
echo
log_info "数据库配置:"
log_info "  主机: $MYSQL_HOST:$MYSQL_PORT"
log_info "  用户: $MYSQL_USER"
log_info "  数据库: $MYSQL_DATABASE"
echo

# 凭据文件检查和密码读取
read_mysql_password() {
    # 从凭证文件读取密码
    if [[ -f "$CREDENTIALS_FILE" ]]; then
        local mysql_password=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)

        if [[ -n "$mysql_password" ]]; then
            echo "$mysql_password"
            return 0
        fi
    fi

    # 如果凭证文件读取失败，尝试从环境变量读取
    if [[ -n "${MYSQL_APP_PASSWORD:-}" ]]; then
        echo "$MYSQL_APP_PASSWORD"
        return 0
    fi

    # 手动输入密码
    read -s -p "MySQL密码: " mysql_password
    echo
    if [[ -n "$mysql_password" ]]; then
        echo "$mysql_password"
        return 0
    else
        return 1
    fi
}

# 数据库连接测试
test_mysql_connection() {
    local password="$1"

    log_info "测试数据库连接..."

    if mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -e "SELECT 1;" &>/dev/null; then
        log_success "✓ 数据库连接成功"
        return 0
    else
        log_error "❌ 数据库连接失败"
        return 1
    fi
}

# 获取数据库表列表
get_database_tables() {
    local password="$1"

    local tables=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = '$MYSQL_DATABASE'
        ORDER BY table_name;
    " 2>/dev/null)

    if [[ -n "$tables" ]]; then
        local table_count=$(echo "$tables" | wc -l)
        echo "$tables"
        return 0
    else
        return 1
    fi
}

# 创建备份
create_backup() {
    local password="$1"

    log_info "创建数据库备份..."

    local backup_file="backup_${MYSQL_DATABASE}_$(date +%Y%m%d_%H%M%S).sql"

    if mysqldump -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" > "$backup_file" 2>/dev/null; then
        local file_size=$(stat -c%s "$backup_file" 2>/dev/null || echo "unknown")
        log_success "✓ 备份创建成功: $backup_file ($file_size bytes)"
        echo "$backup_file"
        return 0
    else
        log_error "❌ 备份创建失败"
        return 1
    fi
}

# 清空数据库表
clear_database_tables() {
    local password="$1"
    local tables="$2"

    log_info "开始清空数据库表..."

    # 直接使用mysql命令清理，避免临时文件的复杂性
    log_info "执行清理命令..."

    # 生成并执行TRUNCATE命令（使用简单的命令行方式）
    local success=true

    # 首先禁用外键检查
    if ! mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -e "SET FOREIGN_KEY_CHECKS = 0;" 2>/dev/null; then
        log_error "❌ 无法禁用外键检查"
        return 1
    fi

    # 逐个清理表
    local cleaned_count=0
    local total_count=0

    while IFS= read -r table; do
        if [[ -n "$table" ]]; then
            total_count=$((total_count + 1))
            log_info "  清空表: $table"

            if mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -e "TRUNCATE TABLE \`$table\`;" 2>/dev/null; then
                cleaned_count=$((cleaned_count + 1))
            else
                log_warning "    ⚠️  表 $table 清空失败，尝试使用DELETE"
                if mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -e "DELETE FROM \`$table\`;" 2>/dev/null; then
                    log_info "    ✓ 表 $table 使用 DELETE 清空成功"
                    cleaned_count=$((cleaned_count + 1))
                else
                    log_error "    ❌ 表 $table 清空失败"
                    success=false
                fi
            fi
        fi
    done <<< "$tables"

    # 重新启用外键检查
    mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -e "SET FOREIGN_KEY_CHECKS = 1;" 2>/dev/null

    if [[ "$success" == true ]] && [[ "$cleaned_count" == "$total_count" ]]; then
        log_success "✓ 数据库清理完成 ($cleaned_count/$total_count 个表)"
        return 0
    else
        log_error "❌ 数据库清理部分失败 ($cleaned_count/$total_count 个表成功)"
        return 1
    fi
}

# 清理Bootstrap配置文件
clear_bootstrap_config() {
    log_info "清理Bootstrap配置文件..."

    local bootstrap_file="backend/.bootstrap_config.json"

    if [[ -f "$bootstrap_file" ]]; then
        rm -f "$bootstrap_file"
        log_success "✓ Bootstrap配置文件已删除"
    else
        log_info "  Bootstrap配置文件不存在，跳过"
    fi
}

# 显示清理结果
show_cleanup_result() {
    local password="$1"

    log_info "验证清理结果..."

    # 获取表数量
    local table_count=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = '$MYSQL_DATABASE';
    " 2>/dev/null)

    # 检查主要表的实际行数（更准确的方法）
    local main_tables_rows=0
    while read -r table; do
        if [[ -n "$table" ]]; then
            local count=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "SELECT COUNT(*) FROM \`$table\`;" 2>/dev/null || echo "0")
            main_tables_rows=$((main_tables_rows + count))
        fi
    done <<< "$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = '$MYSQL_DATABASE' AND table_name IN ('users', 'projects', 'system_configs', 'videos', 'transcripts');
    " 2>/dev/null)"

    log_success "✓ 数据库清理验证完成"
    log_info "  表数量: $table_count"
    log_info "  主要表实际行数: $main_tables_rows"

    if [[ "$main_tables_rows" == "0" ]]; then
        log_success "✅ 所有表已成功清空"
    else
        log_warning "⚠️  主要表中仍有 $main_tables_rows 行数据"
        log_info "显示详细行数:"

        # 显示每个主要表的具体行数
        while read -r table; do
            if [[ -n "$table" ]]; then
                local count=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "SELECT COUNT(*) FROM \`$table\`;" 2>/dev/null || echo "0")
                if [[ "$count" != "0" ]]; then
                    log_info "  $table: $count 行"
                fi
            fi
        done <<< "$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$password" "$MYSQL_DATABASE" -sN -e "
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = '$MYSQL_DATABASE';
        " 2>/dev/null)"
    fi
}

# 主函数
main() {
    local skip_backup=false
    local dry_run=false

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-backup)
                skip_backup=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --help|-h)
                cat << EOF
用法: $0 [选项]

选项:
    --skip-backup    跳过数据库备份
    --dry-run        仅显示将要清理的表，不执行实际操作
    --help, -h       显示此帮助信息

示例:
    $0                    # 完整清理（包含备份）
    $0 --skip-backup      # 清理但不备份
    $0 --dry-run          # 仅预览要清理的表

EOF
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done

    # 读取MySQL密码
    log_info "读取MySQL凭据..."
    local mysql_password
    mysql_password=$(read_mysql_password)
    if [[ $? -ne 0 ]]; then
        log_error "❌ 无法读取MySQL密码"
        exit 1
    fi

    if [[ -f "$CREDENTIALS_FILE" ]]; then
        log_success "✓ 从凭证文件读取MySQL密码成功"
    elif [[ -n "${MYSQL_APP_PASSWORD:-}" ]]; then
        log_success "✓ 从环境变量读取MySQL密码成功"
    else
        log_info "✓ 手动输入MySQL密码"
    fi

    # 测试数据库连接
    if ! test_mysql_connection "$mysql_password"; then
        exit 1
    fi

    # 获取数据库表列表
    log_info "获取数据库表列表..."
    local tables
    tables=$(get_database_tables "$mysql_password")
    if [[ $? -ne 0 ]]; then
        log_warning "数据库为空或无法访问表"
        exit 0
    fi

    local table_count=$(echo "$tables" | wc -l)
    log_success "✓ 发现 $table_count 个表"

    # 显示将要清理的表
    echo
    log_info "将要清理的表:"
    echo "$tables" | while read -r table; do
        if [[ -n "$table" ]]; then
            echo "  • $table"
        fi
    done
    echo

    # 干运行模式
    if [[ "$dry_run" == true ]]; then
        log_info "干运行模式：未执行实际清理操作"
        exit 0
    fi

    # 安全确认
    echo -n "确认要清理所有表数据吗？这将永久删除所有数据！[y/N]: "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "操作已取消"
        exit 0
    fi

    # 创建备份（除非跳过）
    local backup_file=""
    if [[ "$skip_backup" != true ]]; then
        backup_file=$(create_backup "$mysql_password")
        if [[ $? -ne 0 ]]; then
            log_warning "备份失败，但仍继续清理操作"
        fi
    else
        log_warning "跳过数据库备份"
    fi

    # 清理数据库表
    if clear_database_tables "$mysql_password" "$tables"; then
        # 清理Bootstrap配置
        clear_bootstrap_config

        # 显示清理结果
        show_cleanup_result "$mysql_password"

        # 显示备份文件信息
        if [[ -n "$backup_file" ]]; then
            log_info "备份文件: $backup_file"
        fi

        log_success "🎉 数据库清理完成！"
        echo
        log_info "现在可以运行以下命令重新初始化系统："
        log_info "  1. ./install_user.sh    # 重新配置环境"
        log_info "  2. ./start_services.sh  # 启动服务"
        echo
    else
        log_error "❌ 数据库清理失败"
        exit 1
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi