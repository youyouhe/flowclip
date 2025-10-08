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
            # 只接受POST请求
            if request.method != 'POST':
                logger.warning(f"拒绝非POST请求: {request.method} from {request.remote}")
                return web.Response(status=405, text='Method Not Allowed')

            # 验证Content-Type
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                logger.warning(f"拒绝非JSON请求: Content-Type={content_type} from {request.remote}")
                return web.Response(status=400, text='Invalid Content-Type')

            # 检查User-Agent
            user_agent = request.headers.get('User-Agent', '')
            if 'Tus-ASR-Task-Manager' not in user_agent:
                logger.warning(f"拒绝可疑请求: User-Agent={user_agent}, Remote={request.remote}")
                return web.Response(status=403, text='Forbidden')

            current_time = time.time()
            logger.info("🔔 收到TUS回调请求")
            logger.info(f"时间: {current_time}")
            logger.info(f"请求头: {dict(request.headers)}")

            try:
                payload = await request.json()
            except Exception as json_error:
                logger.error(f"JSON解析失败: {json_error} from {request.remote}")
                return web.Response(status=400, text='Invalid JSON')

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
            elif payload.get('status') == 'failed':
                # 增强失败callback处理
                error_msg = payload.get('error_message', '任务失败')
                failed_at = payload.get('failed_at')
                filename = payload.get('filename', '')

                logger.error(f"❌ 任务 {task_id} 失败: {error_msg}")
                if filename:
                    logger.error(f"📁 失败文件: {filename}")
                if failed_at:
                    logger.error(f"⏰ 失败时间: {failed_at}")

                # 保存详细的失败信息
                self._fail_task(task_id, error_msg, payload)
            else:
                # 兼容其他失败状态
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

    def _fail_task(self, task_id: str, error_message: str, full_payload: Dict[str, Any] = None):
        """标记任务失败"""
        try:
            current_time = time.time()

            # 保存详细的失败结果
            result_data = {
                'task_id': task_id,
                'error_message': error_message,
                'completed_at': current_time,
                'status': 'failed'
            }

            # 如果有完整的payload，添加更多详细信息
            if full_payload:
                # 保留所有原始失败信息
                result_data.update(full_payload)

                # 记录详细失败信息到日志
                filename = full_payload.get('filename', '')
                failed_at = full_payload.get('failed_at', '')
                error_type = full_payload.get('error_type', '')

                if filename:
                    logger.info(f"📁 失败文件名: {filename}")
                if failed_at:
                    logger.info(f"⏰ TUS服务失败时间: {failed_at}")
                    result_data['tus_failed_at'] = failed_at
                if error_type:
                    logger.info(f"🔍 错误类型: {error_type}")
                    result_data['error_type'] = error_type

            # 添加callback服务器处理时间
            result_data['callback_processed_at'] = current_time
            result_data['callback_received'] = True

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

            logger.info(f"✅ 任务 {task_id} 失败状态已保存 (包含详细信息)")

            # 更新数据库中的任务状态
            self._update_database_task_status(task_id, result_data)

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
            logger.info(f"📋 ProcessingTask详细信息:")
            logger.info(f"  - task_type: {processing_task.task_type}")
            logger.info(f"  - task_name: {processing_task.task_name}")
            logger.info(f"  - video_id: {processing_task.video_id}")
            logger.info(f"  - input_data: {processing_task.input_data}")
            logger.info(f"  - task_metadata: {processing_task.task_metadata}")

            # 检查任务状态并分别处理成功和失败情况
            is_failed = result.get('status') == 'failed'

            if is_failed:
                # 处理失败状态
                error_message = result.get('error_message', 'TUS ASR处理失败')

                logger.error(f"❌ 处理任务失败: {task_id}")
                logger.error(f"💔 失败原因: {error_message}")

                # 更新ProcessingTask状态为失败
                processing_task.status = ProcessingTaskStatus.FAILED
                processing_task.progress = 0.0  # 失败时进度归零
                processing_task.completed_at = datetime.utcnow()
                processing_task.message = f"TUS ASR处理失败: {error_message} (任务ID: {task_id})"

                # 更新output_data，保留失败信息
                existing_output_data = processing_task.output_data or {}
                failure_updates = {
                    'callback_processed': True,
                    'callback_received_at': time.time(),
                    'tus_task_id': task_id,
                    'tus_result': result,  # 保存完整的失败回调结果
                    'error_details': {
                        'tus_error_message': error_message,
                        'tus_failed_at': result.get('failed_at'),
                        'tus_filename': result.get('filename'),
                        'tus_error_type': result.get('error_type'),
                        'callback_processed_at': time.time()
                    }
                }

                # 合并失败信息
                existing_output_data.update(failure_updates)
                processing_task.output_data = existing_output_data

                logger.info(f"✅ 失败状态已更新到数据库: task_id={task_id}, processing_task_id={processing_task.id}")

            else:
                # 处理成功状态（原有逻辑）
                # 下载SRT内容并保存到MinIO，同时获取SRT文本内容
                srt_content = None
                srt_url = result.get('srt_url')
                if srt_url:
                    try:
                        srt_content = self._download_srt_content_for_db(srt_url)
                        logger.info(f"✅ SRT内容下载成功，大小: {len(srt_content) if srt_content else 0} 字符")
                    except Exception as e:
                        logger.error(f"❌ 下载SRT内容失败: {e}")
                        srt_content = None

                # 更新ProcessingTask状态，包含SRT文本内容以保持前端兼容性
                processing_task.status = ProcessingTaskStatus.SUCCESS
                processing_task.progress = 100.0
                processing_task.completed_at = datetime.utcnow()

                # 重要：不要覆盖已存在的output_data，而是合并更新
                # Celery任务可能已经存储了重要信息（如srt_content）
                existing_output_data = processing_task.output_data or {}

                logger.info(f"📋 现有的output_data字段: {list(existing_output_data.keys())}")
                if existing_output_data.get('srt_content'):
                    logger.info(f"✅ 现有output_data已包含SRT内容，长度: {len(existing_output_data['srt_content'])} 字符")

                # 只更新必要的字段，保留Celery任务已存储的数据
                updates = {
                    'callback_processed': True,  # 标记callback已处理
                    'callback_received_at': time.time(),
                    'tus_task_id': task_id,
                    'tus_result': result  # 保存原始TUS回调结果
                }

                # 如果Celery任务没有存储SRT内容，而我们又下载到了，则添加
                if srt_content and not existing_output_data.get('srt_content'):
                    updates['srt_content'] = srt_content
                    logger.info(f"✅ 通过callback添加SRT内容，长度: {len(srt_content)} 字符")

                    # 计算字幕条数
                    try:
                        # 按字幕块分割并计算条数
                        blocks = srt_content.strip().split('\n\n')
                        subtitle_count = len([block for block in blocks if block.strip()])
                        updates['total_segments'] = subtitle_count
                        logger.info(f"✅ 计算字幕条数: {subtitle_count} 条")
                    except Exception as count_error:
                        logger.warning(f"⚠️ 计算字幕条数失败: {count_error}")
                        # 使用简单的换行符作为备选计算
                        updates['total_segments'] = srt_content.count('\n\n') + 1 if srt_content.strip() else 0
                        logger.info(f"✅ 使用备选方法计算字幕条数: {updates['total_segments']} 条")

                # 合并更新数据
                existing_output_data.update(updates)

                # 更新processing_task的output_data
                processing_task.output_data = existing_output_data
                logger.info(f"✅ 已合并更新output_data，总字段数: {len(processing_task.output_data)}")
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

    def _download_srt_content_for_db(self, srt_url: str) -> Optional[str]:
        """下载SRT内容用于存储到数据库"""
        try:
            from app.services.system_config_service import SystemConfigService
            from app.core.database import get_sync_db
            import requests

            # 从数据库动态加载TUS API配置
            try:
                with get_sync_db() as db:
                    db_configs = SystemConfigService.get_all_configs_sync(db)
                    tus_api_url = db_configs.get('tus_api_url', 'http://localhost:8000')
                    asr_api_key = db_configs.get('asr_api_key', None)
                    logger.info(f"✅ 从数据库加载TUS API URL: {tus_api_url}")
            except Exception as config_error:
                logger.warning(f"⚠️ 从数据库加载TUS API配置失败，使用默认值: {config_error}")
                tus_api_url = 'http://localhost:8000'
                asr_api_key = None

            # 构建TUS下载URL
            if srt_url.startswith('/'):
                download_url = f"{tus_api_url.rstrip('/')}{srt_url}"
            else:
                download_url = srt_url

            logger.info(f"🔄 开始下载SRT内容用于数据库存储: {download_url}")

            # 设置请求头
            headers = {}
            if asr_api_key:
                headers['X-API-Key'] = asr_api_key
                logger.info(f"✅ 使用ASR API Key进行授权")
            headers['ngrok-skip-browser-warning'] = 'true'

            # 下载SRT内容
            response = requests.get(download_url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ 下载SRT失败: HTTP {response.status_code}")
                return None

            srt_content = response.text
            logger.info(f"✅ 原始响应内容下载成功，大小: {len(srt_content)} 字符")

            # 检查响应是否是JSON格式（TUS API可能返回JSON包装的内容）
            try:
                import json
                json_response = json.loads(srt_content)
                if isinstance(json_response, dict) and 'data' in json_response:
                    # 如果是JSON格式且包含data字段，提取data字段作为SRT内容
                    srt_content = json_response['data']
                    logger.info(f"✅ 从JSON响应中提取SRT内容，大小: {len(srt_content)} 字符")
                    logger.info(f"📝 JSON响应格式: code={json_response.get('code')}, msg={json_response.get('msg')}")
                else:
                    logger.info(f"📝 响应不是预期的JSON格式，直接使用原始内容")
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接使用原始内容
                logger.info(f"📝 响应不是JSON格式，直接使用原始内容")
            except Exception as e:
                logger.warning(f"⚠️ 解析JSON响应失败，使用原始内容: {e}")

            logger.info(f"✅ 最终SRT内容大小: {len(srt_content)} 字符")
            return srt_content

        except Exception as e:
            logger.error(f"❌ 下载SRT内容失败: {e}", exc_info=True)
            return None

    def _update_related_records(self, session, processing_task: ProcessingTask, result: Dict[str, Any]):
        """更新相关记录（Video、VideoSlice等）"""
        try:
            srt_url = result.get('srt_url')
            if not srt_url:
                logger.warning("⚠️ 回调结果中没有srt_url")
                return

            # 从processing_task的input_data中获取任务信息
            input_data = processing_task.input_data or {}
            video_id = input_data.get('video_id') or processing_task.video_id  # 优先使用input_data中的，回退到ProcessingTask.video_id
            slice_id = input_data.get('slice_id')
            sub_slice_id = input_data.get('sub_slice_id')

            # 增加调试信息
            logger.info(f"📋 ProcessingTask.input_data: {input_data}")
            logger.info(f"📋 ProcessingTask.video_id: {processing_task.video_id}")
            logger.info(f"📋 提取的ID: video_id={video_id}, slice_id={slice_id}, sub_slice_id={sub_slice_id}")

            # 如果input_data中没有ID信息，尝试从其他地方获取
            if not any([slice_id, sub_slice_id]):  # 注意：我们主要需要的是slice_id或sub_slice_id，video_id已经有了
                logger.info(f"🔍 input_data中没有ID信息，尝试从其他地方获取")

                # 尝试从task_metadata中解析
                if processing_task.task_metadata:
                    import json
                    try:
                        metadata = json.loads(processing_task.task_metadata) if isinstance(processing_task.task_metadata, str) else processing_task.task_metadata
                        video_id = video_id or metadata.get('video_id')
                        slice_id = slice_id or metadata.get('slice_id')
                        sub_slice_id = sub_slice_id or metadata.get('sub_slice_id')
                        logger.info(f"📋 从task_metadata解析的ID: video_id={video_id}, slice_id={slice_id}, sub_slice_id={sub_slice_id}")
                    except Exception as parse_error:
                        logger.warning(f"⚠️ 解析task_metadata失败: {parse_error}")

                # 如果还是没有，尝试通过任务类型推断
                if not any([video_id, slice_id, sub_slice_id]):
                    task_type = processing_task.task_type or ''
                    logger.info(f"🔍 通过任务类型推断: {task_type}")

                    if 'video' in task_type.lower() and 'transcript' in task_type.lower():
                        # 视频转录任务，可能需要通过其他方式关联
                        logger.info(f"📋 这是视频转录任务，但缺少关联ID")

                    elif 'slice' in task_type.lower():
                        # 切片任务，可能需要查找最近的切片
                        logger.info(f"📋 这是切片处理任务")

            # 下载SRT内容并保存到MinIO
            minio_srt_url = None
            try:
                if video_id:  # 只要有video_id就可以保存到MinIO
                    minio_srt_url = self._download_and_store_srt(session, srt_url, video_id, slice_id, sub_slice_id)
                    if minio_srt_url:
                        logger.info(f"✅ SRT文件已保存到MinIO: {minio_srt_url}")
                    else:
                        logger.warning("⚠️ SRT文件保存到MinIO失败，将使用原始URL")
                else:
                    logger.warning(f"⚠️ 无法确定存储路径：video_id={video_id}, slice_id={slice_id}, sub_slice_id={sub_slice_id}")
                    logger.warning("⚠️ 将使用原始TUS URL作为SRT地址")
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

            elif video_id and not slice_id and not sub_slice_id:
                # 只有在既没有slice_id也没有sub_slice_id时，才更新原视频的记录
                # 这确保了只有原视频的SRT任务才会影响原视频状态
                logger.info(f"🎯 这是原视频的SRT任务，更新原视频记录: video_id={video_id}")

                video = session.query(Video).filter(Video.id == video_id).first()
                if video:
                    video.processing_progress = 100
                    video.processing_stage = ProcessingStage.GENERATE_SRT.value
                    video.processing_message = "字幕生成完成 (TUS模式)"
                    video.processing_completed_at = datetime.utcnow()
                    logger.info(f"✅ 已更新Video: id={video_id}")

                # 更新ProcessingStatus表 - 仅限原视频SRT任务
                processing_status = session.query(ProcessingStatus).filter(
                    ProcessingStatus.video_id == video_id
                ).first()
                if processing_status:
                    # 只更新SRT相关状态，不改变整体状态
                    # 防止切片任务影响原视频的整体状态
                    processing_status.generate_srt_status = ProcessingTaskStatus.SUCCESS
                    processing_status.generate_srt_progress = 100
                    logger.info(f"✅ 已更新原视频SRT状态(TUS): video_id={video_id}")

            elif video_id and (slice_id or sub_slice_id):
                # 这是切片或子切片的SRT任务，绝对不能更新原视频状态
                logger.warning(f"⚠️ 切片/子切片SRT任务完成，不更新原视频状态: video_id={video_id}, slice_id={slice_id}, sub_slice_id={sub_slice_id}")
                # 确保不会意外影响到原视频的状态记录
                try:
                    processing_status = session.query(ProcessingStatus).filter(
                        ProcessingStatus.video_id == video_id
                    ).first()
                    if processing_status:
                        # 检查并确保不会修改原视频的SRT状态
                        logger.info(f"🔍 检查原视频processing_status - 当前SRT状态: {processing_status.generate_srt_status}")
                        # 不做任何修改，只记录日志
                except Exception as check_error:
                    logger.error(f"检查原视频状态失败: {check_error}")

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
            from app.services.system_config_service import SystemConfigService
            from app.core.database import get_sync_db
            import requests

            # 从数据库动态加载TUS API配置
            try:
                with get_sync_db() as db:
                    db_configs = SystemConfigService.get_all_configs_sync(db)
                    tus_api_url = db_configs.get('tus_api_url', getattr(settings, 'tus_api_url', 'http://localhost:8000'))
                    asr_api_key = db_configs.get('asr_api_key', getattr(settings, 'asr_api_key', None))
                    logger.info(f"✅ 从数据库加载TUS API URL: {tus_api_url}")
                    logger.info(f"✅ 从数据库加载ASR API Key: {'已设置' if asr_api_key else '未设置'}")
            except Exception as config_error:
                logger.warning(f"⚠️ 从数据库加载TUS API配置失败，使用默认值: {config_error}")
                tus_api_url = getattr(settings, 'tus_api_url', 'http://localhost:8000')
                asr_api_key = getattr(settings, 'asr_api_key', None)
                logger.info(f"⚠️ 使用默认ASR API Key: {'已设置' if asr_api_key else '未设置'}")

            # 构建TUS下载URL
            if srt_url.startswith('/'):
                download_url = f"{tus_api_url.rstrip('/')}{srt_url}"
            else:
                download_url = srt_url

            logger.info(f"🔗 最终使用的TUS服务URL: {tus_api_url}")
            logger.info(f"🎯 完整下载URL: {download_url}")

            logger.info(f"🔄 开始从TUS服务下载SRT: {download_url}")

            # 设置请求头 - 修复授权问题
            headers = {}
            if asr_api_key:
                headers['X-API-Key'] = asr_api_key
                logger.info(f"✅ 使用ASR API Key进行授权")
            else:
                logger.warning(f"⚠️ 未设置ASR API Key，可能无法通过TUS API授权")
            headers['ngrok-skip-browser-warning'] = 'true'

            # 下载SRT内容
            response = requests.get(download_url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ 下载SRT失败: HTTP {response.status_code}")
                return None

            srt_content = response.text
            logger.info(f"✅ 原始响应内容下载成功，大小: {len(srt_content)} 字符")

            # 检查响应是否是JSON格式（TUS API可能返回JSON包装的内容）
            try:
                import json
                json_response = json.loads(srt_content)
                if isinstance(json_response, dict) and 'data' in json_response:
                    # 如果是JSON格式且包含data字段，提取data字段作为SRT内容
                    srt_content = json_response['data']
                    logger.info(f"✅ 从JSON响应中提取SRT内容，大小: {len(srt_content)} 字符")
                    logger.info(f"📝 JSON响应格式: code={json_response.get('code')}, msg={json_response.get('msg')}")
                else:
                    logger.info(f"📝 响应不是预期的JSON格式，直接使用原始内容")
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接使用原始内容
                logger.info(f"📝 响应不是JSON格式，直接使用原始内容")
            except Exception as e:
                logger.warning(f"⚠️ 解析JSON响应失败，使用原始内容: {e}")

            logger.info(f"✅ 最终SRT内容大小: {len(srt_content)} 字符")

            # 确定MinIO存储路径和用户信息
            user_id = None
            project_id = None

            if slice_id:
                # 从VideoSlice获取用户和项目信息
                slice_record = session.query(VideoSlice).filter(VideoSlice.id == slice_id).first()
                if slice_record:
                    user_id, project_id = self._get_user_project_from_video(session, slice_record.video_id)
                    # 统一使用标准的subtitles路径，避免路径不一致
                    # 需要获取video_id来生成正确的文件名
                    video_id = slice_record.video_id
                    object_name = f"users/{user_id}/projects/{project_id}/subtitles/{video_id}_slice_{slice_id}.srt"
                    logger.info(f"✅ 使用标准切片SRT路径: {object_name}")
                else:
                    logger.error(f"❌ 未找到VideoSlice记录: id={slice_id}")
                    return None

            elif sub_slice_id:
                # 从VideoSubSlice获取用户和项目信息
                sub_slice = session.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                if sub_slice:
                    user_id, project_id = self._get_user_project_from_video(session, sub_slice.parent_slice.video_id)
                    # 统一使用标准的subtitles路径，避免路径不一致
                    # 需要获取video_id来生成正确的文件名
                    video_id = sub_slice.parent_slice.video_id
                    object_name = f"users/{user_id}/projects/{project_id}/subtitles/{video_id}_subslice_{sub_slice_id}.srt"
                    logger.info(f"✅ 使用标准子切片SRT路径: {object_name}")
                else:
                    logger.error(f"❌ 未找到VideoSubSlice记录: id={sub_slice_id}")
                    return None

            elif video_id:
                # 直接从Video获取用户和项目信息
                user_id, project_id = self._get_user_project_from_video(session, video_id)
                object_name = f"users/{user_id}/projects/{project_id}/subtitles/{video_id}.srt"

            else:
                logger.warning("⚠️ 无法确定SRT存储路径：缺少video_id/slice_id/sub_slice_id")
                logger.info("📋 将跳过MinIO保存，使用原始TUS URL")
                return None

            # 保存到MinIO
            try:
                from app.services.minio_client import minio_service
                import io

                srt_bytes = srt_content.encode('utf-8-sig')  # 添加BOM以支持UTF-8
                srt_stream = io.BytesIO(srt_bytes)

                # 尝试直接使用MinIO客户端连接
                from minio import Minio
                from app.core.config import settings

                # 从数据库动态加载MinIO配置
                try:
                    with get_sync_db() as db:
                        db_configs = SystemConfigService.get_all_configs_sync(db)
                        minio_endpoint = db_configs.get('minio_endpoint', getattr(settings, 'minio_endpoint', 'minio:9000'))
                        minio_access_key = db_configs.get('minio_access_key', getattr(settings, 'minio_access_key', 'minioadmin'))
                        minio_secret_key = db_configs.get('minio_secret_key', getattr(settings, 'minio_secret_key', 'minioadmin'))
                        minio_bucket_name = db_configs.get('minio_bucket_name', getattr(settings, 'minio_bucket_name', 'youtube-videos'))
                        minio_secure = db_configs.get('minio_secure', getattr(settings, 'minio_secure', False))
                        if isinstance(minio_secure, str):
                            minio_secure = minio_secure.lower() in ('true', '1', 'yes')
                        logger.info(f"✅ 从数据库加载MinIO配置: {minio_endpoint}, secure={minio_secure}")
                except Exception as config_error:
                    logger.warning(f"⚠️ 从数据库加载MinIO配置失败，使用默认值: {config_error}")
                    minio_endpoint = getattr(settings, 'minio_endpoint', 'minio:9000')
                    minio_access_key = getattr(settings, 'minio_access_key', 'minioadmin')
                    minio_secret_key = getattr(settings, 'minio_secret_key', 'minioadmin')
                    minio_bucket_name = getattr(settings, 'minio_bucket_name', 'youtube-videos')
                    minio_secure = getattr(settings, 'minio_secure', False)

                # 创建MinIO客户端
                minio_client = Minio(
                    endpoint=minio_endpoint,
                    access_key=minio_access_key,
                    secret_key=minio_secret_key,
                    secure=minio_secure
                )

                # 确保bucket存在
                if not minio_client.bucket_exists(minio_bucket_name):
                    logger.info(f"📦 创建MinIO bucket: {minio_bucket_name}")
                    minio_client.make_bucket(minio_bucket_name)

                minio_client.put_object(
                    bucket_name=minio_bucket_name,
                    object_name=object_name,
                    data=srt_stream,
                    length=len(srt_bytes),
                    content_type='text/plain; charset=utf-8'
                )
                srt_stream.close()

                logger.info(f"✅ SRT文件已保存到MinIO: {object_name}")

                return object_name

            except Exception as minio_error:
                logger.error(f"❌ MinIO保存失败: {minio_error}")
                # 如果MinIO保存失败，返回None让系统使用原始URL
                return None

        except Exception as e:
            logger.error(f"❌ 下载和保存SRT到MinIO失败: {e}", exc_info=True)
            return None

    def _get_user_project_from_video(self, session, video_id: int) -> tuple:
        """从video_id获取user_id和project_id"""
        try:
            from app.models.video import Video
            from app.models.project import Project

            # 需要join到Project表来获取user_id
            # Video没有user_id字段，需要通过Project关联获取
            video = session.query(Video).join(Project).filter(Video.id == video_id).first()
            if video and video.project:
                return video.project.user_id, video.project_id
            else:
                logger.error(f"❌ 未找到Video记录或Project关联: id={video_id}")
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