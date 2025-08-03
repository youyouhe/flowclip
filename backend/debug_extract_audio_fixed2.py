#!/usr/bin/env python3
"""
调试音频提取功能，检查Celery与Redis连接问题
修复版本2：修复MinIO路径问题
"""

import os
import sys
import time
import asyncio
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

async def test_direct_extract():
    """不使用Celery，直接调用音频提取功能"""
    try:
        from app.services.audio_processor import audio_processor
        from app.core.config import settings
        
        print("\n===== 测试直接提取音频 =====")
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
        
        # 直接执行音频提取
        # 首先下载视频文件
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

async def test_celery_extract():
    """通过Celery调用音频提取任务"""
    try:
        from app.core.config import settings
        print("\n===== 测试通过Celery提取音频 =====")
        
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
        
        # 使用Celery任务
        from app.tasks.video_tasks import extract_audio
        
        print("发送Celery任务...")
        print(f"参数: video_id={video_id}, project_id={project_id}, user_id={user_id}, video_minio_path={object_name}")
        
        # 异步调用任务
        print("尝试异步方式调用任务...")
        try:
            task_result = extract_audio.delay(
                video_id=str(video_id),
                project_id=project_id,
                user_id=user_id,
                video_minio_path=object_name
            )
            print(f"任务ID: {task_result.id}")
            
            # 等待任务完成
            print("等待任务完成...")
            timeout = 60  # 60秒超时
            start_time = time.time()
            while not task_result.ready() and time.time() - start_time < timeout:
                print(".", end="", flush=True)
                await asyncio.sleep(1)
            
            print("\n")
            if task_result.ready():
                print(f"任务完成，结果: {task_result.result}")
            else:
                print("任务超时，尚未完成")
                
        except Exception as e:
            print(f"异步调用失败: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"Celery提取音频测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_celery_config():
    """测试Celery配置"""
    try:
        print("\n===== 测试Celery配置 =====")
        
        # 检查Redis连接
        import redis
        from app.core.celery import celery_app
        
        print("Celery配置:")
        print(f"Broker URL: {celery_app.conf.broker_url}")
        print(f"Backend URL: {celery_app.conf.result_backend}")
        
        redis_url = celery_app.conf.broker_url
        host = redis_url.split('//')[1].split(':')[0]
        port = int(redis_url.split(':')[-1])
        
        print(f"尝试连接Redis: {host}:{port}")
        r = redis.Redis(host=host, port=port, socket_connect_timeout=5)
        ping_result = r.ping()
        print(f"Redis连接成功! PING响应: {ping_result}")
        
    except Exception as e:
        print(f"Celery配置测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("===== 音频提取调试工具 =====")
    print("1. 直接提取音频（不使用Celery）")
    print("2. 通过Celery提取音频")
    print("3. 测试Celery配置")
    choice = input("请选择测试方式 (1/2/3): ")
    
    if choice == "1":
        await test_direct_extract()
    elif choice == "2":
        await test_celery_extract()
    elif choice == "3":
        await test_celery_config()
    else:
        print("无效的选择")

if __name__ == "__main__":
    asyncio.run(main())