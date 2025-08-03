#!/usr/bin/env python3
"""
修复常见连接问题，包括Redis连接、CORS设置和Celery配置
"""

import sys
import os
import re
from pathlib import Path

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

def fix_redis_in_env():
    """确保Redis连接URL在.env中正确配置"""
    print("检查.env中的Redis配置...")
    
    env_path = Path("./.env")
    if not env_path.exists():
        print("错误: .env文件不存在，将创建新文件")
        with open(env_path, "w") as f:
            f.write("REDIS_URL=redis://localhost:6379\n")
        print("已创建.env文件并添加默认Redis URL")
        return
    
    with open(env_path, "r") as f:
        env_content = f.read()
    
    # 检查是否已包含REDIS_URL
    redis_url_match = re.search(r'REDIS_URL\s*=\s*(.*)', env_content)
    if redis_url_match:
        current_url = redis_url_match.group(1).strip()
        print(f"当前Redis URL: {current_url}")
        
        # 检查是否指向有效Redis服务
        if "localhost" in current_url:
            print("警告: Redis URL指向localhost，但Docker服务可能在不同的地址")
            print("建议检查Docker容器的IP并更新")
            print("可以使用以下命令查看Redis容器的IP:")
            print("docker inspect backend_redis_1 | grep IPAddress")
    else:
        # 添加Redis URL
        with open(env_path, "a") as f:
            f.write("\nREDIS_URL=redis://localhost:6379\n")
        print("已添加默认Redis URL到.env文件")
        print("请根据Docker容器的实际IP更新此值")

def fix_celery_initialization():
    """修复app/core/celery.py中的初始化问题"""
    print("\n检查Celery初始化配置...")
    
    celery_path = Path("./app/core/celery.py")
    if not celery_path.exists():
        print(f"错误: Celery配置文件不存在: {celery_path}")
        return
    
    with open(celery_path, "r") as f:
        content = f.read()
    
    # 创建备份
    backup_path = celery_path.with_suffix(".py.bak")
    if not backup_path.exists():
        with open(backup_path, "w") as f:
            f.write(content)
        print(f"已创建Celery配置备份: {backup_path}")
    
    # 确保直接从环境变量获取Redis URL
    updated_content = """from celery import Celery
import os
from dotenv import load_dotenv
from app.core.config import settings

# 显式加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path)

# 确保直接从环境变量获取Redis URL
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

celery_app = Celery(
    "youtube_slicer",
    broker=redis_url,
    backend=redis_url,
    include=["app.tasks.video_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    broker_transport_options={
        'visibility_timeout': 3600,  # 1小时
        'max_retries': 5,
    },
    broker_connection_retry=True,
    broker_connection_max_retries=10,
)

if __name__ == "__main__":
    celery_app.start()
"""
    
    with open(celery_path, "w") as f:
        f.write(updated_content)
    print("已更新Celery配置，直接从环境变量读取Redis URL")

def fix_cors_main_app():
    """确保CORS在main.py中正确配置"""
    print("\n检查main.py中的CORS配置...")
    
    main_path = Path("./app/main.py")
    if not main_path.exists():
        print(f"错误: FastAPI主文件不存在: {main_path}")
        return
    
    with open(main_path, "r") as f:
        content = f.read()
    
    # 检查CORS中间件
    if "CORSMiddleware" in content:
        print("CORS中间件已配置在main.py中")
        
        # 检查allow_origins配置
        if "allow_origins=[" in content:
            print("检查origins配置...")
            
            # 确保origins包括前端地址
            if '"*"' in content or "'*'" in content:
                print("当前配置允许所有源 (*)")
            else:
                print("注意: CORS配置限制了特定源，确保包含你的前端地址")
                print("例如: http://192.168.8.107:3000")
    else:
        print("未在main.py中找到CORS中间件配置")
        print("建议运行: python fix_cors.py")

def print_connection_info():
    """打印连接和故障排除信息"""
    print("\n===== 连接信息与故障排除 =====")
    print("1. Redis连接:")
    print("   - 检查Redis容器是否运行: docker ps | grep redis")
    print("   - 检查Redis连接: python test_redis_connection.py")
    print("   - 确保.env中的REDIS_URL指向正确的IP地址")
    
    print("\n2. Celery工作进程:")
    print("   - 在backend目录下运行: celery -A app.core.celery worker --loglevel=info")
    print("   - 如果有错误，尝试先停止现有进程: pkill -f 'celery -A'")
    
    print("\n3. CORS问题:")
    print("   - 确保前端请求使用的API URL与后端匹配")
    print("   - 检查前端环境变量中的API URL是否正确")
    print("   - 确保CORS中间件在FastAPI应用启动前配置")
    
    print("\n4. 启动FastAPI服务器:")
    print("   - uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")

if __name__ == "__main__":
    print("===== 开始修复连接问题 =====")
    fix_redis_in_env()
    fix_celery_initialization()
    fix_cors_main_app()
    print_connection_info()
    
    print("\n所有修复已完成。请重启服务以应用更改。")