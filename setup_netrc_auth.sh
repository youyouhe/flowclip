#!/bin/bash

echo "🚀 YouTube .netrc认证设置脚本"
echo "=================================="

# 检查并安装yt-dlp
echo "📦 检查yt-dlp..."
if ! python -c "import yt_dlp" 2>/dev/null; then
    echo "⚠️ yt-dlp未安装，正在安装..."
    pip install yt-dlp
else
    echo "✅ yt-dlp已安装"
fi

# 检查.netrc文件
echo ""
echo "🔐 检查.netrc文件..."
if [ ! -f ~/.netrc ]; then
    echo "❌ .netrc文件不存在，正在创建..."
    touch ~/.netrc
    chmod 600 ~/.netrc
    echo "✅ .netrc文件已创建"
else
    echo "✅ .netrc文件已存在"
fi

# 检查权限
permissions=$(stat -c "%a" ~/.netrc)
if [ "$permissions" != "600" ]; then
    echo "⚠️ 修正.netrc文件权限..."
    chmod 600 ~/.netrc
    echo "✅ 权限已修正为600"
else
    echo "✅ .netrc权限正确 (600)"
fi

# 显示.netrc文件内容
echo ""
echo "📝 当前.netrc文件内容:"
echo "--------------------------------"
cat ~/.netrc
echo "--------------------------------"

# 检查是否需要配置
if grep -q "machine youtube" ~/.netrc && ! grep -q "<您的邮箱>" ~/.netrc; then
    echo ""
    echo "✅ .netrc已配置完成"
    echo ""
    echo "🧪 运行测试..."
    python test_netrc_auth.py
else
    echo ""
    echo "⚠️ .netrc需要配置"
    echo ""
    echo "📋 配置步骤:"
    echo "1. 编辑.netrc文件:"
    echo "   nano ~/.netrc"
    echo ""
    echo "2. 添加YouTube认证信息:"
    echo "   machine youtube login your_email@gmail.com password your_password"
    echo ""
    echo "3. 保存文件 (Ctrl+O, Enter, Ctrl+X)"
    echo ""
    echo "4. 重新运行此脚本进行测试"
    echo ""
    echo "🔒 安全提醒:"
    echo "   - 使用您的真实Google账号密码"
    echo "   - 确保账号可以正常登录YouTube"
    echo "   - 如果开启了两步验证，可能需要应用专用密码"
fi