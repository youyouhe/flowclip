#!/bin/bash

# 简化版MySQL数据库清理脚本

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

# 配置
MYSQL_USER="youtube_user"
MYSQL_DATABASE="youtube_slicer"
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
CREDENTIALS_FILE="/home/flowclip/credentials.txt"

echo "========================================"
echo "    简化版 MySQL 数据库清理脚本"
echo "========================================"
echo

# 读取密码
if [[ -f "$CREDENTIALS_FILE" ]]; then
    MYSQL_PASSWORD=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)
    if [[ -n "$MYSQL_PASSWORD" ]]; then
        log_success "✓ 读取MySQL密码成功"
    else
        log_error "❌ 无法读取MySQL密码"
        exit 1
    fi
else
    log_error "❌ 凭证文件不存在: $CREDENTIALS_FILE"
    exit 1
fi

# 测试连接
if mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SELECT 1;" &>/dev/null; then
    log_success "✓ 数据库连接成功"
else
    log_error "❌ 数据库连接失败"
    exit 1
fi

# 获取表列表
log_info "获取数据库表列表..."
tables=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = '$MYSQL_DATABASE'
    ORDER BY table_name;
" 2>/dev/null)

if [[ -n "$tables" ]]; then
    table_count=$(echo "$tables" | wc -l)
    log_success "✓ 发现 $table_count 个表"

    echo
    log_info "将要清理的表:"
    echo "$tables" | while read -r table; do
        if [[ -n "$table" ]]; then
            echo "  • $table"
        fi
    done
    echo
else
    log_warning "数据库为空或无法访问表"
    exit 0
fi

# 确认清理
echo -n "确认要清理所有表数据吗？这将永久删除所有数据！[y/N]: "
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
    log_info "操作已取消"
    exit 0
fi

# 执行清理
log_info "开始清理数据库表..."

# 使用here-doc一次性执行所有命令
mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" << EOF
SET FOREIGN_KEY_CHECKS = 0;

-- 清空所有表
$(echo "$tables" | while read -r table; do
    if [[ -n "$table" ]]; then
        echo "TRUNCATE TABLE IF EXISTS \`$table\`;"
    fi
done)

SET FOREIGN_KEY_CHECKS = 1;

-- 显示清理结果
SELECT '所有表清理完成！' as status;
EOF

if [[ $? -eq 0 ]]; then
    log_success "✓ 数据库清理完成"

    # 清理Bootstrap配置
    if [[ -f "backend/.bootstrap_config.json" ]]; then
        rm -f backend/.bootstrap_config.json
        log_success "✓ Bootstrap配置文件已删除"
    fi

    # 验证清理结果
    total_rows=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "
        SELECT SUM(table_rows) FROM information_schema.tables
        WHERE table_schema = '$MYSQL_DATABASE';
    " 2>/dev/null || echo "0")

    log_info "清理验证:"
    log_info "  表数量: $table_count"
    log_info "  总行数: $total_rows"

    if [[ "$total_rows" == "0" ]]; then
        log_success "✅ 所有表已成功清空"
    else
        log_warning "⚠️  部分表可能仍有数据"
    fi

    echo
    log_success "🎉 数据库清理完成！"
    echo
    log_info "现在可以运行以下命令重新初始化系统："
    log_info "  ./install_user.sh    # 重新配置环境"
    log_info "  ./start_services.sh  # 启动服务"
    echo
else
    log_error "❌ 数据库清理失败"
    exit 1
fi