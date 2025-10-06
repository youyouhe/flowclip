#!/usr/bin/env python3
"""
测试YouTube .netrc认证功能
"""

import os
import sys
import yt_dlp
from pathlib import Path

def test_netrc_setup():
    """测试.netrc设置"""
    print("🔐 测试.netrc认证设置")
    print("="*50)

    # 检查.netrc文件
    netrc_file = Path.home() / '.netrc'

    if not netrc_file.exists():
        print("❌ .netrc文件不存在")
        return False

    # 检查权限
    file_stat = netrc_file.stat()
    mode = oct(file_stat.st_mode)[-3:]
    if mode != "600":
        print(f"❌ .netrc权限不正确: {mode} (应为600)")
        return False
    else:
        print(f"✅ .netrc权限正确: {mode}")

    # 检查内容
    with open(netrc_file, 'r') as f:
        content = f.read()

    if "machine youtube" in content:
        print("✅ 找到YouTube认证配置")

        # 检查是否是模板（还没有填入真实信息）
        if "<您的邮箱>" in content or "<您的密码>" in content:
            print("⚠️ .netrc文件还是模板，请填入真实的邮箱和密码")
            print("📝 编辑方法:")
            print(f"   nano {netrc_file}")
            print("   然后修改为类似: machine youtube login your_email@gmail.com password your_password")
            return False
        else:
            print("✅ .netrc配置已完善")
            return True
    else:
        print("❌ .netrc文件中没有找到YouTube认证配置")
        return False

def test_youtube_auth():
    """测试YouTube认证"""
    print("\n🧪 测试YouTube认证")
    print("="*50)

    try:
        # 配置yt-dlp使用.netrc
        ydl_opts = {
            'netrc': True,
            'quiet': True,
            'no_warnings': True,
        }

        # 测试URL（第一个YouTube视频）
        test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        print(f"📹 测试视频: {test_url}")
        print("🔄 正在尝试获取视频信息...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)

            if info and 'title' in info:
                print(f"✅ 认证成功！")
                print(f"   标题: {info.get('title')}")
                print(f"   时长: {info.get('duration')}秒")
                print(f"   上传者: {info.get('uploader')}")
                print(f"   观看次数: {info.get('view_count')}")
                return True
            else:
                print("❌ 获取视频信息失败")
                return False

    except Exception as e:
        error_msg = str(e)
        print(f"❌ 认证失败: {error_msg}")

        if "Sign in to confirm" in error_msg:
            print("💡 建议:")
            print("   1. 检查.netrc文件中的邮箱和密码是否正确")
            print("   2. 确保该账号可以正常登录YouTube")
            print("   3. 检查是否需要开启两步验证")

        elif "No such file" in error_msg or "Permission denied" in error_msg:
            print("💡 建议:")
            print("   1. 确保.netrc文件存在")
            print("   2. 检查文件权限是否为600")

        return False

def test_youtube_download():
    """测试视频下载（简单测试）"""
    print("\n📥 测试视频下载（元数据）")
    print("="*50)

    try:
        ydl_opts = {
            'netrc': True,
            'quiet': True,
            'no_warnings': True,
            'format': 'worst',  # 使用最低质量避免下载大文件
        }

        test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        print(f"📹 测试下载元数据: {test_url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)

            if info and 'formats' in info:
                formats = info.get('formats', [])
                print(f"✅ 成功获取 {len(formats)} 种格式")

                # 显示一些可用格式
                for i, fmt in enumerate(formats[:3]):  # 只显示前3个
                    print(f"   格式{i+1}: {fmt.get('format_note', 'unknown')} - {fmt.get('ext', 'unknown')}")

                return True
            else:
                print("❌ 获取格式信息失败")
                return False

    except Exception as e:
        print(f"❌ 下载测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 YouTube .netrc认证测试")
    print("="*60)

    # 1. 检查.netrc设置
    setup_ok = test_netrc_setup()

    if not setup_ok:
        print("\n❌ .netrc设置不完整，请先配置认证信息")
        print("\n📋 配置步骤:")
        print("1. 编辑 ~/.netrc 文件")
        print("2. 添加类似: machine youtube login your_email@gmail.com password your_password")
        print("3. 保存文件")
        print("4. 重新运行此测试")
        return False

    # 2. 测试认证
    auth_ok = test_youtube_auth()

    if not auth_ok:
        print("\n❌ YouTube认证失败")
        return False

    # 3. 测试下载
    download_ok = test_youtube_download()

    # 总结
    print("\n" + "="*60)
    print("📊 测试总结:")
    print(f"   .netrc设置: {'✅' if setup_ok else '❌'}")
    print(f"   YouTube认证: {'✅' if auth_ok else '❌'}")
    print(f"   下载测试: {'✅' if download_ok else '❌'}")

    if setup_ok and auth_ok and download_ok:
        print("\n🎉 所有测试通过！.netrc认证可以正常使用")
        print("\n💡 在代码中使用:")
        print("   ydl_opts = {'netrc': True}")
        print("   with yt_dlp.YoutubeDL(ydl_opts) as ydl:")
        print("       info = ydl.extract_info(url)")
        return True
    else:
        print("\n❌ 部分测试失败，请检查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)