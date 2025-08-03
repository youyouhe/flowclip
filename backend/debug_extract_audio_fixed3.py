#!/usr/bin/env python3
"""
调试音频提取功能，检查Celery与Redis连接问题
修复版本3：直接测试Redis连接并诊断问题
"""

import os
import sys
import time
import asyncio
import socket
from pathlib import Path
from dotenv import load_dotenv

# 添加当前目录到路径
sys.path.append(str(Path('.').absolute()))

# 加载环境变量
load_dotenv()

# 打印当前环境信息
print("===== 环境信息 =====")
print(f"当前工作目录: {os.getcwd()}")
print(f"REDIS_URL: {os.getenv('REDIS_URL')}")
print(f"Python路径: {sys.path}")

def test_redis_direct():
    """直接测试Redis连接，不使用Celery或Kombu"""
    print("\n===== 直接测试Redis连接 =====")
    
    # 从环境变量或配置获取Redis地址
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        from app.core.config import settings
        redis_url = settings.redis_url
    
    print(f"测试连接: {redis_url}")
    
    # 解析Redis URL
    if redis_url.startswith('redis://'):
        redis_url = redis_url[len('redis://'):]
    
    # 解析主机和端口
    host = redis_url.split(':')[0]
    port = 6379  # 默认端口
    
    if ':' in redis_url:
        try:
            port = int(redis_url.split(':')[1])
        except ValueError:
            pass
    
    print(f"解析后: 主机={host}, 端口={port}")
    
    # 测试TCP连接
    try:
        print(f"尝试TCP连接到 {host}:{port}...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        result = s.connect_ex((host, port))
        s.close()
        
        if result == 0:
            print("TCP连接成功！Redis端口可访问。")
        else:
            print(f"TCP连接失败！错误码: {result}")
            print("可能的原因:")
            print("1. Redis服务未运行")
            print("2. 防火墙阻止了连接")
            print("3. 主机/端口配置错误")
            print("\n尝试以下解决方案:")
            print("- 确认Redis Docker容器是否运行: docker ps | grep redis")
            print("- 检查Redis容器IP地址: docker inspect backend_redis_1 | grep IPAddress")
            print("- 尝试直接使用Redis容器IP")
    except Exception as e:
        print(f"连接测试出错: {e}")
    
    # 使用Redis库测试
    try:
        import redis
        print("\n使用Redis库测试连接...")
        r = redis.Redis(host=host, port=port, socket_connect_timeout=5)
        ping_result = r.ping()
        print(f"Redis PING测试: {ping_result}")
        print("Redis连接成功!")
        
        # 测试基本操作
        test_key = 'test_connection_key'
        test_value = 'connection_ok'
        r.set(test_key, test_value)
        read_value = r.get(test_key).decode('utf-8')
        print(f"写入'{test_value}', 读取'{read_value}'")
        
        # 清理
        r.delete(test_key)
        return True
    except ImportError:
        print("未安装Redis库。请安装: pip install redis")
        return False
    except Exception as e:
        print(f"Redis操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_celery_config():
    """测试Celery配置，查看实际应用的设置"""
    print("\n===== 测试Celery配置 =====")
    
    # 导入celery应用实例
    from app.core.celery import celery_app
    
    # 打印配置
    print("Celery配置:")
    print(f"应用名称: {celery_app.main}")
    print(f"Broker URL: {celery_app.conf.broker_url}")
    print(f"Backend URL: {celery_app.conf.result_backend}")
    print(f"Broker Transport: {celery_app.conf.broker_transport}")
    print(f"Broker Transport选项: {celery_app.conf.broker_transport_options}")
    print(f"Broker连接池: {celery_app.conf.broker_pool_limit}")
    
    # 检查worker设置
    print("\nWorker设置:")
    print(f"Worker并发数: {celery_app.conf.worker_concurrency}")
    print(f"Worker预取乘数: {celery_app.conf.worker_prefetch_multiplier}")

async def use_direct_approach():
    """通过直接方法提取音频，不使用Celery"""
    try:
        from app.services.audio_processor import audio_processor
        from app.core.config import settings
        
        print("\n===== 使用直接方法提取音频 =====")
        video_id = input("请输入视频ID: ")
        project_id = int(input("请输入项目ID: "))
        user_id = int(input("请输入用户ID: "))
        
        # 获取视频文件路径
        from app.core.database import AsyncSessionLocal
        from app.models.video import Video
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as db:
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                print(f"错误: 未找到ID为 {video_id} 的视频")
                return
            
            video_path = video.file_path
            print(f"找到视频: {video.title}, 路径: {video_path}")
            
            # 修复MinIO路径
            # 移除可能的bucket前缀
            bucket_prefix = f"{settings.minio_bucket_name}/"
            if video_path.startswith(bucket_prefix):
                object_name = video_path[len(bucket_prefix):]
            else:
                object_name = video_path
                
            print(f"处理后的对象名称: {object_name}")
        
        # 从此处直接执行音频提取逻辑，跳过Celery
        print("从MinIO下载视频文件...")
        from app.services.minio_client import minio_service
        import tempfile
        import requests
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_filename = f"{video_id}.mp4"
            video_file_path = temp_path / video_filename
            
            # 获取视频文件URL
            video_url = await minio_service.get_file_url(object_name, expiry=3600)
            
            if not video_url:
                print("错误: 无法获取视频文件URL")
                return
                
            print(f"获取到视频URL: {video_url}")
            
            # 下载视频文件
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(video_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"视频文件已下载到: {video_file_path}")
            
            # 提取音频
            print("正在提取音频...")
            result = await audio_processor.extract_audio_from_video(
                video_path=str(video_file_path),
                video_id=video_id,
                project_id=project_id,
                user_id=user_id
            )
            
            # 显示结果
            if result.get('success'):
                print("音频提取成功:")
                print(f"- 音频文件名: {result['audio_filename']}")
                print(f"- MinIO路径: {result['minio_path']}")
                print(f"- 对象名称: {result['object_name']}")
                print(f"- 音频时长: {result['duration']} 秒")
                print(f"- 文件大小: {result['file_size']} 字节")
                print(f"- 音频格式: {result['audio_format']}")
            else:
                print(f"音频提取失败: {result.get('error', '未知错误')}")
        
    except Exception as e:
        print(f"直接提取音频失败: {e}")
        import traceback
        traceback.print_exc()

async def fix_redis_connection_in_db():
    """尝试在数据库中修复Redis连接"""
    try:
        import json
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        print("\n===== 尝试修复数据库中的Redis配置 =====")
        redis_url = os.getenv('REDIS_URL')
        
        # 直接执行一个SQL查询来查看当前配置
        async with AsyncSessionLocal() as db:
            print("检查数据库配置表...")
            try:
                result = await db.execute(text("SELECT name, value FROM config WHERE name LIKE '%redis%'"))
                rows = result.all()
                if rows:
                    print("找到Redis相关配置:")
                    for row in rows:
                        print(f"{row[0]}: {row[1]}")
                else:
                    print("未找到Redis相关配置")
            except Exception as e:
                print(f"查询配置表失败: {e}")
        
    except Exception as e:
        print(f"修复Redis配置失败: {e}")

async def get_docker_redis_info():
    """获取Docker中Redis容器的信息"""
    import subprocess
    
    print("\n===== Docker Redis 容器信息 =====")
    try:
        # 检查Redis容器是否运行
        print("检查Redis容器状态...")
        cmd = ["docker", "ps", "-f", "name=redis", "--format", "{{.Names}} {{.Status}}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if result.stdout.strip():
                print(f"运行中的Redis容器: \n{result.stdout}")
            else:
                print("未找到运行中的Redis容器")
                
                # 检查所有容器
                print("\n检查所有Redis相关容器(包括已停止的)...")
                cmd = ["docker", "ps", "-a", "-f", "name=redis", "--format", "{{.Names}} {{.Status}}"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.stdout.strip():
                    print(f"Redis相关容器: \n{result.stdout}")
        
        # 获取Redis容器IP
        print("\n获取Redis容器IP地址...")
        cmd = ["docker", "ps", "-q", "-f", "name=redis"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            container_id = result.stdout.strip()
            cmd = ["docker", "inspect", "-f", "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_id]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print(f"Redis容器IP: {result.stdout.strip()}")
                print("建议更新.env文件中的REDIS_URL为:")
                print(f"REDIS_URL=redis://{result.stdout.strip()}:6379")
            else:
                print("无法获取Redis容器IP地址")
        
    except Exception as e:
        print(f"获取Docker信息失败: {e}")

async def main():
    """主函数"""
    print("===== Redis连接问题诊断工具 =====")
    print("1. 直接测试Redis连接")
    print("2. 检查Celery配置")
    print("3. 直接提取音频(绕过Celery)")
    print("4. 获取Docker中Redis信息")
    choice = input("请选择功能 (1/2/3/4): ")
    
    if choice == "1":
        test_redis_direct()
    elif choice == "2":
        await test_celery_config()
    elif choice == "3":
        await use_direct_approach()
    elif choice == "4":
        await get_docker_redis_info()
    else:
        print("无效的选择")

if __name__ == "__main__":
    asyncio.run(main())