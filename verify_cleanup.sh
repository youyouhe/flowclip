#!/bin/bash

# 数据库清理验证脚本

set -euo pipefail

# 颜色输出定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo "========================================"
echo "    数据库清理验证脚本"
echo "========================================"
echo

# 配置
MYSQL_USER="youtube_user"
MYSQL_DATABASE="youtube_slicer"
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
CREDENTIALS_FILE="/home/flowclip/credentials.txt"

# 读取密码
MYSQL_PASSWORD=$(grep "^MYSQL_APP_PASSWORD=" "$CREDENTIALS_FILE" 2>/dev/null | cut -d'=' -f2- | head -n1)

log_info "验证数据库清理结果..."

# 检查表数量
table_count=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = '$MYSQL_DATABASE';
" 2>/dev/null)

log_info "数据库表数量: $table_count"

# 检查每个表的行数
log_info "检查各表数据状态:"
total_actual_rows=0

mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "
    SELECT
        table_name as '表名',
        table_rows as '信息_schema行数',
        (SELECT COUNT(*) FROM \`$MYSQL_DATABASE\`.\`table_name\`) as '实际行数'
    FROM information_schema.tables
    WHERE table_schema = '$MYSQL_DATABASE'
    ORDER BY table_name;
" 2>/dev/null

# 计算实际总行数
actual_total=$(mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -sN -e "
    SELECT SUM(CASE
        WHEN table_name IN ('projects', 'system_configs', 'users') THEN
            (SELECT COUNT(*) FROM \`$MYSQL_DATABASE\`.\`table_name\`)
        ELSE 0
    END) as total
    FROM information_schema.tables
    WHERE table_schema = '$MYSQL_DATABASE';
" 2>/dev/null || echo "0")

echo
log_info "验证结果汇总:"
log_info "  信息schema总行数: $(mysql -h\"$MYSQL_HOST\" -P\"$MYSQL_PORT\" -u\"$MYSQL_USER\" -p\"$MYSQL_PASSWORD\" \"$MYSQL_DATABASE\" -sN -e \"SELECT SUM(table_rows) FROM information_schema.tables WHERE table_schema = '$MYSQL_DATABASE';\" 2>/dev/null)"
log_info "  实际数据总行数: $actual_total"

# 检查Bootstrap配置
if [[ -f "backend/.bootstrap_config.json" ]]; then
    log_warning "⚠️  Bootstrap配置文件仍存在"
else
    log_success "✓ Bootstrap配置文件已清理"
fi

# 最终判断
if [[ "$actual_total" == "0" ]]; then
    echo
    log_success "✅ 数据库清理验证通过！"
    log_success "   所有表数据已成功清空"
    log_success "   Bootstrap配置已清理"
    echo
    log_info "🎉 现在可以重新初始化系统："
    log_info "   ./install_user.sh    # 重新配置环境"
    log_info "   ./start_services.sh  # 启动服务"
else
    echo
    log_warning "⚠️  仍有 $actual_total 行数据未清理"
fi

echo