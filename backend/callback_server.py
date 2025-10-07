#!/usr/bin/env python3
"""
独立TUS回调服务器
运行在独立容器中，专门处理TUS ASR的回调请求
"""

import asyncio
import os
import json
import time
import logging
import signal
import pickle
from typing import Dict, Any, Optional
from aiohttp import web
import redis
from datetime import datetime
import sys
from pathlib import Path

# 添加项目根目录到Python路径，以便导入项目模块
sys.path.append(str(Path(__file__).parent))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.models.processing_task import ProcessingTask, ProcessingStatus
    from app.models.video import Video
    from app.models.video_slice import VideoSlice, VideoSubSlice
    from app.core.constants import ProcessingTaskStatus, ProcessingStage
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"无法导入数据库模块: {e}")
    logger.warning("将仅使用Redis缓存模式，不更新数据库")
    # 设置为None，后续检查时跳过数据库操作
    create_engine = None
    sessionmaker = None
    Base = None
    ProcessingTask = None
    ProcessingStatus = None
    Video = None
    VideoSlice = None
    VideoSubSlice = None
    ProcessingTaskStatus = None
    ProcessingStage = None

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StandaloneCallbackServer:
    """独立回调服务器"""

    def __init__(self):
        self.callback_port = int(os.getenv('CALLBACK_PORT', '9090'))
        self.callback_host = os.getenv('CALLBACK_HOST', '0.0.0.0')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.redis_key_prefix = os.getenv('REDIS_KEY_PREFIX', 'tus_callback:')
        self.result_key_prefix = os.getenv('REDIS_RESULT_PREFIX', 'tus_result:')
        self.stats_key = os.getenv('REDIS_STATS_KEY', 'tus_callback_stats')

        self._server_running = False
        self._redis_client = None

        # 数据库相关
        self.db_engine = None
        self.db_session_factory = None

        # 初始化Redis连接和数据库连接
        self._init_redis()
        self._init_database()

        logger.info(f"独立回调服务器初始化完成:")
        logger.info(f"  端口: {self.callback_port}")
        logger.info(f"  主机: {self.callback_host}")
        logger.info(f"  Redis URL: {self.redis_url}")
        logger.info(f"  数据库支持: {'启用' if self.db_engine else '禁用'}")

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            # 尝试使用和主应用相同的Redis配置
            try:
                from app.core.config import settings
                actual_redis_url = settings.redis_url
                logger.info(f"使用主应用配置的Redis URL: {actual_redis_url}")
            except ImportError:
                actual_redis_url = self.redis_url
                logger.info(f"使用环境变量Redis URL: {actual_redis_url}")

            self._redis_client = redis.from_url(
                actual_redis_url,
                decode_responses=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            self._redis_client.ping()
            logger.info(f"✅ Redis连接成功: {actual_redis_url}")

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            raise RuntimeError(f"无法连接到Redis: {e}")

    def _init_database(self):
        """初始化数据库连接"""
        if not all([create_engine, sessionmaker, ProcessingTask, ProcessingStatus]):
            logger.warning("⚠️ 数据库模块导入失败，跳过数据库初始化")
            return

        try:
            # 尝试使用和主应用相同的数据库配置
            try:
                from app.core.config import settings
                database_url = settings.database_url
                logger.info(f"使用主应用配置的数据库URL")
            except ImportError:
                # 从环境变量获取数据库URL，默认使用MySQL配置
                database_url = os.getenv('DATABASE_URL',
                    'mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer?charset=utf8mb4')
                logger.info(f"使用环境变量数据库URL")

            # 使用同步引擎进行独立服务器的数据库操作
            # 按照正确的方式转换数据库URL（参考app/core/database.py）
            sync_database_url = database_url.replace("+aiomysql", "")
            sync_database_url = sync_database_url.replace("mysql://", "mysql+pymysql://")

            self.db_engine = create_engine(sync_database_url, echo=False)
            self.db_session_factory = sessionmaker(bind=self.db_engine)

            # 测试数据库连接
            from sqlalchemy import text
            test_session = self.db_session_factory()
            test_session.execute(text("SELECT 1"))
            test_session.close()

            # 安全地显示数据库连接信息
            try:
                db_info = sync_database_url.split('@')[-1] if '@' in sync_database_url else sync_database_url.split('://')[0] + '://***'
                logger.info(f"✅ 数据库连接成功: {db_info}")
            except Exception as display_error:
                logger.info(f"✅ 数据库连接成功")

        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            logger.warning("⚠️ 将仅使用Redis缓存模式，不更新数据库")
            self.db_engine = None
            self.db_session_factory = None

    def _get_task_key(self, task_id: str) -> str:
        """获取任务在Redis中的键名"""
        return f"{self.redis_key_prefix}{task_id}"

    def _get_result_key(self, task_id: str) -> str:
        """获取结果在Redis中的键名"""
        return f"{self.result_key_prefix}{task_id}"

    async def callback_handler(self, request):
        """处理TUS回调请求"""
        try:
            current_time = time.time()
            logger.info("🔔 收到TUS回调请求")
            logger.info(f"时间: {current_time}")
            logger.info(f"请求头: {dict(request.headers)}")

            payload = await request.json()
            logger.info(f"回调数据: {json.dumps(payload, indent=2)}")

            task_id = payload.get('task_id')
            if not task_id:
                logger.error("❌ 回调中缺少task_id")
                return web.Response(status=400, text='Missing task_id')

            logger.info(f"📝 处理任务ID: {task_id}")

            # 检查任务是否在Redis中注册
            task_key = self._get_task_key(task_id)
            task_exists = self._redis_client.exists(task_key)

            if not task_exists:
                logger.warning(f"⚠️ 任务 {task_id} 未在Redis中找到，可能已超时")
            else:
                logger.info(f"✅ 任务 {task_id} 在Redis中找到")

            # 处理任务结果
            if payload.get('status') == 'completed':
                logger.info(f"✅ 任务 {task_id} 完成，保存结果")
                self._complete_task(task_id, payload)
            else:
                error_msg = payload.get('error_message', '任务失败')
                logger.error(f"❌ 任务 {task_id} 失败: {error_msg}")
                self._fail_task(task_id, error_msg)

            # 更新统计
            self._increment_stats('received_callbacks')

            logger.info(f"✅ 任务 {task_id} 处理完成")
            return web.Response(text='OK')

        except Exception as e:
            logger.error(f"❌ 回调处理错误: {e}", exc_info=True)
            return web.Response(status=500, text=str(e))

    def _complete_task(self, task_id: str, result: Dict[str, Any]):
        """完成任务并设置结果"""
        try:
            current_time = time.time()

            # 保存结果到Redis
            result_data = {
                'task_id': task_id,
                'result': result,
                'completed_at': current_time,
                'status': 'completed'
            }

            result_key = self._get_result_key(task_id)
            self._redis_client.setex(
                result_key,
                300,  # 5分钟过期
                pickle.dumps(result_data)
            )

            logger.info(f"✅ 任务 {task_id} 结果已保存到Redis")

            # 从任务注册表中删除
            task_key = self._get_task_key(task_id)
            self._redis_client.delete(task_key)

            # 更新统计
            self._increment_stats('completed_tasks')

            # 更新数据库中的任务状态
            self._update_database_task_status(task_id, result)

        except Exception as e:
            logger.error(f"❌ 保存任务结果失败: {e}")

    def _fail_task(self, task_id: str, error_message: str):
        """标记任务失败"""
        try:
            current_time = time.time()

            # 保存失败结果
            result_data = {
                'task_id': task_id,
                'error_message': error_message,
                'completed_at': current_time,
                'status': 'failed'
            }

            result_key = self._get_result_key(task_id)
            self._redis_client.setex(
                result_key,
                300,  # 5分钟过期
                pickle.dumps(result_data)
            )

            # 从任务注册表中删除
            task_key = self._get_task_key(task_id)
            self._redis_client.delete(task_key)

            # 更新统计
            self._increment_stats('failed_tasks')

            logger.info(f"✅ 任务 {task_id} 失败状态已保存")

        except Exception as e:
            logger.error(f"❌ 保存失败状态失败: {e}")

    def _increment_stats(self, stat_name: str):
        """增加统计计数"""
        try:
            self._redis_client.hincrby(self.stats_key, stat_name, 1)
        except Exception as e:
            logger.error(f"❌ 更新统计失败: {e}")

    async def health_check(self, request):
        """健康检查端点"""
        try:
            # 检查Redis连接
            self._redis_client.ping()

            # 获取统计信息
            stats = self._get_stats()

            return web.json_response({
                'status': 'healthy',
                'timestamp': time.time(),
                'stats': stats
            })
        except Exception as e:
            return web.json_response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }, status=503)

    def _get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            stats_data = self._redis_client.hgetall(self.stats_key)
            stats = {}
            for key, value in stats_data.items():
                stats[key.decode('utf-8')] = int(value.decode('utf-8'))

            # 获取待处理任务数
            pending_keys = self._redis_client.keys(f"{self.redis_key_prefix}*")
            stats['pending_tasks'] = len(pending_keys)

            # 获取缓存结果数
            result_keys = self._redis_client.keys(f"{self.result_key_prefix}*")
            stats['cached_results'] = len(result_keys)

            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {'error': str(e)}

    async def create_app(self):
        """创建aiohttp应用"""
        app = web.Application()
        app.router.add_post('/callback', self.callback_handler)
        app.router.add_get('/health', self.health_check)
        app.router.add_get('/stats', lambda request: web.json_response(self._get_stats()))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.callback_host, self.callback_port)
        await site.start()

        logger.info(f"🚀 独立回调服务器启动成功!")
        logger.info(f"📡 回调URL: http://{self.callback_host}:{self.callback_port}/callback")
        logger.info(f"💚 健康检查URL: http://{self.callback_host}:{self.callback_port}/health")
        logger.info(f"📊 统计URL: http://{self.callback_host}:{self.callback_port}/stats")

        # 保持运行
        while self._server_running:
            await asyncio.sleep(1)

        logger.info("独立回调服务器正在关闭...")

    async def shutdown(self):
        """关闭服务器"""
        logger.info("正在关闭独立回调服务器...")
        self._server_running = False

    def _update_database_task_status(self, task_id: str, result: Dict[str, Any]):
        """更新数据库中的任务状态"""
        if not self.db_session_factory:
            logger.debug("数据库未连接，跳过数据库更新")
            return

        try:
            session = self.db_session_factory()
            logger.info(f"🔍 开始查找与TUS任务ID {task_id} 关联的ProcessingTask")

            # 首先尝试从Redis中获取Celery任务ID
            celery_task_id = self._get_celery_task_id_from_redis(task_id)
            logger.info(f"📋 从Redis获取到的Celery任务ID: {celery_task_id}")

            processing_task = None
            if celery_task_id:
                # 优先通过Celery任务ID查找
                processing_task = session.query(ProcessingTask).filter(
                    ProcessingTask.celery_task_id == celery_task_id
                ).first()
                logger.info(f"✅ 通过Celery任务ID找到关联任务: {celery_task_id} -> ProcessingTask.id={processing_task.id if processing_task else 'None'}")

            if not processing_task:
                # 回退到通过task_metadata查找
                logger.info(f"🔍 尝试通过task_metadata查找TUS任务ID {task_id}")
                processing_task = session.query(ProcessingTask).filter(
                    ProcessingTask.task_metadata.like(f'%{task_id}%')
                ).first()
                if processing_task:
                    logger.info(f"✅ 通过task_metadata找到关联任务: TUS任务ID {task_id} -> ProcessingTask.id={processing_task.id}")

            if not processing_task:
                # 最后尝试：查找最近的相关任务
                logger.info(f"🔍 尝试查找最近的相关ProcessingTask（过去1小时内）")
                from datetime import timedelta
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)

                processing_task = session.query(ProcessingTask).filter(
                    ProcessingTask.created_at >= one_hour_ago,
                    ProcessingTask.task_type.like('%tus%')
                ).order_by(ProcessingTask.created_at.desc()).first()

                if processing_task:
                    logger.info(f"✅ 通过时间窗口找到关联任务: TUS任务ID {task_id} -> ProcessingTask.id={processing_task.id}")

            if not processing_task:
                logger.error(f"❌ 未找到与TUS任务ID {task_id} 关联的ProcessingTask")
                # 列出所有最近的ProcessingTask用于调试
                from datetime import timedelta
                recent_tasks = session.query(ProcessingTask).filter(
                    ProcessingTask.created_at >= datetime.utcnow() - timedelta(hours=2)
                ).all()
                logger.info(f"📋 最近2小时内的ProcessingTask数量: {len(recent_tasks)}")
                for task in recent_tasks[:5]:  # 只显示前5个
                    logger.info(f"  - Task.id={task.id}, celery_task_id={task.celery_task_id}, task_type={task.task_type}")

                session.close()
                return

            logger.info(f"✅ 找到关联任务: ProcessingTask.id={processing_task.id}, celery_task_id={processing_task.celery_task_id}")

            # 更新ProcessingTask状态
            processing_task.status = ProcessingTaskStatus.SUCCESS
            processing_task.progress = 100.0
            processing_task.completed_at = datetime.utcnow()
            processing_task.output_data = {
                'strategy': 'tus',
                'task_id': task_id,
                'srt_url': result.get('srt_url'),
                'filename': result.get('filename'),
                'status': result.get('status'),
                'completed_at': time.time(),
                **result
            }
            processing_task.message = f"TUS ASR处理完成 (任务ID: {task_id})"

            # 根据任务类型更新相关表
            self._update_related_records(session, processing_task, result)

            session.commit()
            logger.info(f"✅ 数据库任务状态已更新: task_id={task_id}, processing_task_id={processing_task.id}")

            session.close()

        except Exception as e:
            logger.error(f"❌ 更新数据库任务状态失败: {e}", exc_info=True)
            try:
                session.rollback()
                session.close()
            except:
                pass

    def _update_related_records(self, session, processing_task: ProcessingTask, result: Dict[str, Any]):
        """更新相关记录（Video、VideoSlice等）"""
        try:
            srt_url = result.get('srt_url')
            if not srt_url:
                logger.warning("⚠️ 回调结果中没有srt_url")
                return

            # 从processing_task的input_data中获取任务信息
            input_data = processing_task.input_data or {}
            video_id = input_data.get('video_id')
            slice_id = input_data.get('slice_id')
            sub_slice_id = input_data.get('sub_slice_id')

            # 下载SRT内容并保存到MinIO
            minio_srt_url = None
            try:
                minio_srt_url = self._download_and_store_srt(session, srt_url, video_id, slice_id, sub_slice_id)
                if minio_srt_url:
                    logger.info(f"✅ SRT文件已保存到MinIO: {minio_srt_url}")
                else:
                    logger.warning("⚠️ SRT文件保存到MinIO失败，将使用原始URL")
            except Exception as e:
                logger.error(f"❌ 下载和保存SRT到MinIO失败: {e}")
                logger.warning("⚠️ 继续使用原始TUS URL")

            # 使用MinIO URL（如果成功），否则使用原始TUS URL
            final_srt_url = minio_srt_url if minio_srt_url else srt_url

            if slice_id:
                # 更新VideoSlice记录
                video_slice = session.query(VideoSlice).filter(VideoSlice.id == slice_id).first()
                if video_slice:
                    video_slice.srt_url = final_srt_url
                    video_slice.srt_processing_status = "completed"
                    logger.info(f"✅ 已更新VideoSlice: id={slice_id}, srt_url={final_srt_url}")

            elif sub_slice_id:
                # 更新VideoSubSlice记录
                sub_slice = session.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                if sub_slice:
                    sub_slice.srt_url = final_srt_url
                    sub_slice.srt_processing_status = "completed"
                    logger.info(f"✅ 已更新VideoSubSlice: id={sub_slice_id}, srt_url={final_srt_url}")

            elif video_id:
                # 更新Video记录（原视频的SRT任务）
                video = session.query(Video).filter(Video.id == video_id).first()
                if video:
                    video.processing_progress = 100
                    video.processing_stage = ProcessingStage.GENERATE_SRT.value
                    video.processing_message = "字幕生成完成 (TUS模式)"
                    video.processing_completed_at = datetime.utcnow()
                    logger.info(f"✅ 已更新Video: id={video_id}")

                # 更新ProcessingStatus表
                processing_status = session.query(ProcessingStatus).filter(
                    ProcessingStatus.video_id == video_id
                ).first()
                if processing_status:
                    processing_status.overall_status = ProcessingTaskStatus.SUCCESS
                    processing_status.overall_progress = 100
                    processing_status.current_stage = ProcessingStage.COMPLETED.value
                    processing_status.generate_srt_status = ProcessingTaskStatus.SUCCESS
                    processing_status.generate_srt_progress = 100
                    logger.info(f"✅ 已更新ProcessingStatus: video_id={video_id}")

        except Exception as e:
            logger.error(f"❌ 更新相关记录失败: {e}", exc_info=True)

    def _get_celery_task_id_from_redis(self, task_id: str) -> Optional[str]:
        """从Redis中获取与TUS任务ID关联的Celery任务ID"""
        try:
            # 首先检查任务数据中是否包含Celery任务ID
            task_key = self._get_task_key(task_id)
            task_data = self._redis_client.get(task_key)
            if task_data:
                try:
                    data = pickle.loads(task_data)
                    celery_task_id = data.get('celery_task_id')
                    if celery_task_id:
                        logger.info(f"✅ 从任务数据中获取到Celery任务ID: {celery_task_id}")
                        return celery_task_id
                except Exception as e:
                    logger.debug(f"解析任务数据失败: {e}")

            # 如果任务数据中没有，尝试通过映射查找
            # 这种情况下需要遍历所有可能的映射
            logger.info(f"🔍 尝试通过映射查找TUS任务ID {task_id} 对应的Celery任务ID")

            # 检查所有可能的映射键（这种效率较低，但作为回退方案）
            for key_pattern in ["tus_celery_mapping:*"]:
                matching_keys = self._redis_client.keys(key_pattern)
                logger.info(f"🔍 找到 {len(matching_keys)} 个映射键")
                for key in matching_keys:
                    mapping_value = self._redis_client.get(key)
                    if mapping_value:
                        try:
                            decoded_value = mapping_value.decode('utf-8')
                            logger.debug(f"映射键 {key.decode('utf-8')} -> {decoded_value}")
                            if decoded_value == task_id:
                                celery_task_id = key.decode('utf-8').split(':', 1)[1]  # 提取Celery任务ID
                                logger.info(f"✅ 通过映射找到Celery任务ID: {celery_task_id}")
                                return celery_task_id
                        except Exception as decode_error:
                            logger.debug(f"解码映射值失败: {decode_error}")
                    else:
                        logger.debug(f"映射键 {key.decode('utf-8')} 没有值")

            logger.info(f"⚠️ 未找到TUS任务ID {task_id} 对应的Celery任务ID")
            return None

        except Exception as e:
            logger.error(f"❌ 从Redis获取Celery任务ID失败: {e}")
            return None

    def _download_and_store_srt(self, session, srt_url: str, video_id: int = None, slice_id: int = None, sub_slice_id: int = None) -> Optional[str]:
        """从TUS服务下载SRT内容并保存到MinIO"""
        try:
            from app.core.config import settings
            from app.models.video import Video
            from app.models.video_slice import VideoSlice, VideoSubSlice
            import requests

            # 构建TUS下载URL
            tus_api_url = getattr(settings, 'tus_api_url', 'http://localhost:8000')
            if srt_url.startswith('/'):
                download_url = f"{tus_api_url.rstrip('/')}{srt_url}"
            else:
                download_url = srt_url

            logger.info(f"🔄 开始从TUS服务下载SRT: {download_url}")

            # 设置请求头
            headers = {}
            if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
                headers['X-API-Key'] = settings.asr_api_key
            headers['ngrok-skip-browser-warning'] = 'true'

            # 下载SRT内容
            response = requests.get(download_url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ 下载SRT失败: HTTP {response.status_code}")
                return None

            srt_content = response.text
            logger.info(f"✅ SRT内容下载成功，大小: {len(srt_content)} 字符")

            # 确定MinIO存储路径和用户信息
            user_id = None
            project_id = None

            if slice_id:
                # 从VideoSlice获取用户和项目信息
                slice_record = session.query(VideoSlice).filter(VideoSlice.id == slice_id).first()
                if slice_record:
                    user_id, project_id = self._get_user_project_from_video(session, slice_record.video_id)
                    # 检查切片的sliced_file_path，提取slice_uuid用于路径关联
                    if slice_record.sliced_file_path:
                        # 从路径中提取slice_uuid: users/{user_id}/projects/{project_id}/slices/{slice_uuid}/{filename}
                        path_parts = slice_record.sliced_file_path.split('/')
                        if len(path_parts) >= 6 and path_parts[4] == 'slices':
                            slice_uuid = path_parts[5]
                            object_name = f"users/{user_id}/projects/{project_id}/slices/{slice_uuid}/subtitles.srt"
                            logger.info(f"✅ 使用切片UUID路径关联: slice_uuid={slice_uuid}")
                        else:
                            # 回退到简单命名
                            object_name = f"users/{user_id}/projects/{project_id}/subtitles/slice_{slice_id}.srt"
                            logger.warning(f"⚠️ 无法解析切片路径，使用简单命名")
                    else:
                        # 如果切片还没有文件路径，使用简单命名
                        object_name = f"users/{user_id}/projects/{project_id}/subtitles/slice_{slice_id}.srt"
                        logger.warning(f"⚠️ 切片没有文件路径，使用简单命名")
                else:
                    logger.error(f"❌ 未找到VideoSlice记录: id={slice_id}")
                    return None

            elif sub_slice_id:
                # 从VideoSubSlice获取用户和项目信息
                sub_slice = session.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                if sub_slice:
                    user_id, project_id = self._get_user_project_from_video(session, sub_slice.slice.video_id)
                    # 检查子切片的sliced_file_path，提取slice_uuid用于路径关联
                    if sub_slice.sliced_file_path:
                        # 从路径中提取slice_uuid: users/{user_id}/projects/{project_id}/slices/{slice_uuid}/{filename}
                        path_parts = sub_slice.sliced_file_path.split('/')
                        if len(path_parts) >= 6 and path_parts[4] == 'slices':
                            slice_uuid = path_parts[5]
                            object_name = f"users/{user_id}/projects/{project_id}/slices/{slice_uuid}/sub_slice_{sub_slice_id}.srt"
                            logger.info(f"✅ 使用切片UUID路径关联: slice_uuid={slice_uuid}")
                        else:
                            # 回退到简单命名
                            object_name = f"users/{user_id}/projects/{project_id}/subtitles/sub_slice_{sub_slice_id}.srt"
                            logger.warning(f"⚠️ 无法解析子切片路径，使用简单命名")
                    else:
                        # 如果子切片还没有文件路径，使用简单命名
                        object_name = f"users/{user_id}/projects/{project_id}/subtitles/sub_slice_{sub_slice_id}.srt"
                        logger.warning(f"⚠️ 子切片没有文件路径，使用简单命名")
                else:
                    logger.error(f"❌ 未找到VideoSubSlice记录: id={sub_slice_id}")
                    return None

            elif video_id:
                # 直接从Video获取用户和项目信息
                user_id, project_id = self._get_user_project_from_video(session, video_id)
                object_name = f"users/{user_id}/projects/{project_id}/subtitles/{video_id}.srt"

            else:
                logger.error("❌ 无法确定SRT存储路径：缺少video_id/slice_id/sub_slice_id")
                return None

            # 保存到MinIO
            from app.services.minio_client import minio_service
            import io

            srt_bytes = srt_content.encode('utf-8-sig')  # 添加BOM以支持UTF-8
            srt_stream = io.BytesIO(srt_bytes)

            minio_service.internal_client.put_object(
                bucket_name=settings.minio_bucket_name,
                object_name=object_name,
                data=srt_stream,
                length=len(srt_bytes),
                content_type='text/plain; charset=utf-8'
            )
            srt_stream.close()

            logger.info(f"✅ SRT文件已保存到MinIO: {object_name}")

            return object_name

        except Exception as e:
            logger.error(f"❌ 下载和保存SRT到MinIO失败: {e}", exc_info=True)
            return None

    def _get_user_project_from_video(self, session, video_id: int) -> tuple:
        """从video_id获取user_id和project_id"""
        try:
            from app.models.video import Video
            from app.models.project import Project

            # 需要join到Project表来获取user_id
            video = session.query(Video).join(Project).filter(Video.id == video_id).first()
            if video:
                return video.user_id, video.project_id
            else:
                logger.error(f"❌ 未找到Video记录: id={video_id}")
                return None, None
        except Exception as e:
            logger.error(f"❌ 获取用户项目信息失败: {e}")
            return None, None

    def run(self):
        """运行服务器"""
        self._server_running = True

        # 设置信号处理
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在关闭服务器...")
            self._server_running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # 创建事件循环并运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.create_app())
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"❌ 服务器运行错误: {e}", exc_info=True)
        finally:
            logger.info("独立回调服务器已关闭")

if __name__ == "__main__":
    server = StandaloneCallbackServer()
    server.run()