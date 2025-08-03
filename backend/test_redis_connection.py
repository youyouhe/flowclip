#!/usr/bin/env python3
"""
测试Redis连接，检测并解决连接问题
"""

import sys
import os
import time
from pathlib import Path
import redis
from dotenv import load_dotenv

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

def test_redis_connection():
    """测试Redis连接并打印连接信息"""
    print("===== 测试Redis连接 =====")
    
    # 加载环境变量
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path)
    
    # 获取Redis URL
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    print(f"当前环境变量中的REDIS_URL: {redis_url}")
    
    # 解析Redis URL
    if redis_url.startswith('redis://'):
        redis_host = redis_url[len('redis://'):]
        if '@' in redis_host:
            auth, host_port = redis_host.split('@', 1)
        else:
            auth = None
            host_port = redis_host
            
        if ':' in host_port:
            host, port = host_port.split(':', 1)
            if '/' in port:
                port = port.split('/', 1)[0]
            try:
                port = int(port)
            except ValueError:
                port = 6379
        else:
            host = host_port
            port = 6379
    else:
        print(f"无法解析Redis URL: {redis_url}")
        host = 'localhost'
        port = 6379
    
    print(f"解析后的连接信息: 主机={host}, 端口={port}")
    
    # 尝试连接Redis
    try:
        print(f"尝试连接Redis: {host}:{port}...")
        r = redis.Redis(host=host, port=port, socket_connect_timeout=5)
        ping_result = r.ping()
        print(f"Redis连接成功! 响应: {ping_result}")
        
        # 测试基本操作
        test_key = 'test_connection_key'
        test_value = 'connection_ok'
        r.set(test_key, test_value)
        read_value = r.get(test_key)
        print(f"Redis读写测试: 写入'{test_value}', 读取'{read_value.decode('utf-8')}'")
        
        # 清理测试键
        r.delete(test_key)
        return True
    except redis.exceptions.ConnectionError as e:
        print(f"Redis连接错误: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False

def check_celery_config():
    """检查Celery配置文件"""
    print("\n===== 检查Celery配置 =====")
    
    celery_config_path = Path("./app/core/celery.py")
    if not celery_config_path.exists():
        print(f"错误: Celery配置文件不存在: {celery_config_path}")
        return
    
    with open(celery_config_path, "r") as f:
        content = f.read()
    
    print("当前Celery配置中的Redis连接方式:")
    if "broker=settings.redis_url" in content:
        print("- 使用settings.redis_url从配置模块获取Redis URL")
    elif "broker=redis_url" in content and "os.getenv('REDIS_URL'" in content:
        print("- 直接从环境变量获取Redis URL")
    else:
        print("- 未找到明确的Redis连接配置")
    
    print("\n如果想修复Celery配置，请运行:")
    print("python fix_celery_config.py")

def check_cors_config():
    """检查CORS配置"""
    print("\n===== 检查CORS配置 =====")
    
    main_path = Path("./app/main.py")
    if not main_path.exists():
        print(f"错误: FastAPI主文件不存在: {main_path}")
        return
    
    with open(main_path, "r") as f:
        content = f.read()
    
    if "CORSMiddleware" in content:
        print("CORS中间件已配置在主应用文件中")
    else:
        print("主应用文件中未找到CORS中间件配置")
        print("请运行以下命令添加CORS支持:")
        print("python fix_cors.py")

def print_running_instructions():
    """打印正确的运行说明"""
    print("\n===== 运行指导 =====")
    print("1. 启动FastAPI服务器:")
    print("   cd backend")
    print("   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload")
    print("")
    print("2. 启动Celery Worker:")
    print("   cd backend")
    print("   celery -A app.core.celery:celery_app worker --loglevel=info --pool=solo")
    print("   或")
    print("   celery -A app.core.celery worker --loglevel=info --concurrency=2")

if __name__ == "__main__":
    redis_ok = test_redis_connection()
    check_celery_config()
    check_cors_config()
    print_running_instructions()
    
    if not redis_ok:
        print("\n===== 注意 =====")
        print("Redis连接测试失败。请确保:")
        print("1. Redis服务已启动并运行")
        print("2. .env文件中的REDIS_URL设置正确")
        print("3. 如果使用Docker，确保容器正常运行:")
        print("   docker ps | grep redis")