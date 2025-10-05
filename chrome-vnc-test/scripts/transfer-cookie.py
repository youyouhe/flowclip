#!/usr/bin/env python3.9
"""
自动传输cookie文件到本地
"""
import os
import subprocess
import sys
import time

def transfer_cookie_file(local_ip, local_user, local_path, ssh_port=22):
    cookie_file = "/headless/Downloads/cookie.txt"

    if not os.path.exists(cookie_file):
        print(f"❌ cookie文件不存在: {cookie_file}")
        return False

    print(f"正在传输 {cookie_file} 到 {local_user}@{local_ip}:{local_path}")

    cmd = [
        "scp",
        "-P", str(ssh_port),
        cookie_file,
        f"{local_user}@{local_ip}:{local_path}/"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ cookie.txt传输成功!")
            print(f"已保存到: {local_user}@{local_ip}:{local_path}/cookie.txt")
            return True
        else:
            print(f"❌ 传输失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 传输异常: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python3.9 transfer_cookie.py <本地IP> <本地用户名> <本地路径> [SSH端口]")
        sys.exit(1)

    local_ip = sys.argv[1]
    local_user = sys.argv[2]
    local_path = sys.argv[3]
    ssh_port = int(sys.argv[4]) if len(sys.argv) > 4 else 22

    transfer_cookie_file(local_ip, local_user, local_path, ssh_port)