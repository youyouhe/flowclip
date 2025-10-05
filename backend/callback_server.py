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
from typing import Dict, Any
from aiohttp import web
import redis

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

        # 初始化Redis连接
        self._init_redis()

        logger.info(f"独立回调服务器初始化完成:")
        logger.info(f"  端口: {self.callback_port}")
        logger.info(f"  主机: {self.callback_host}")
        logger.info(f"  Redis URL: {self.redis_url}")

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            self._redis_client.ping()
            logger.info(f"✅ Redis连接成功: {self.redis_url}")

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            raise RuntimeError(f"无法连接到Redis: {e}")

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