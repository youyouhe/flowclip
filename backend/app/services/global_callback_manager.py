"""
全局回调服务器管理器
统一管理TUS ASR回调服务器，支持固定端口和任务队列复用
使用Redis作为共享任务状态管理器，解决多进程环境下的任务同步问题
"""

import asyncio
import threading
import time
import logging
import signal
import socket
import os
import pickle
from typing import Dict, Optional, Any
from aiohttp import web
import json

logger = logging.getLogger(__name__)


class GlobalCallbackManager:
    """全局回调服务器管理器 - 单例模式，使用Redis共享任务状态"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # 回调服务器配置
        self.callback_port = 9090  # 固定端口
        self.callback_host = "0.0.0.0"
        self._server_running = False
        self._server_thread = None
        self._server_startup_lock = threading.Lock()  # 服务器启动互斥锁
        self._server_pid = None  # 记录启动服务器的进程ID

        # Redis配置
        self._redis_client = None
        self._redis_key_prefix = "tus_callback:"
        self._result_key_prefix = "tus_result:"
        self._stats_key = "tus_callback_stats"

        # 本地Future存储（仅用于当前进程的任务）
        self._local_futures: Dict[str, asyncio.Future] = {}
        self._future_lock = threading.RLock()

        # Fallback模式存储（当Redis不可用时）
        self._fallback_registry: Dict[str, Any] = {}
        self._fallback_results: Dict[str, Any] = {}
        self._fallback_expiry: Dict[str, float] = {}
        self._fallback_lock = threading.RLock()

        # Redis模式标志
        self._redis_available = False

        # 初始化Redis连接
        self._init_redis()

        if self._redis_client:
            logger.info("全局回调服务器管理器初始化完成（Redis模式）")
        else:
            logger.warning("全局回调服务器管理器初始化完成（Fallback模式）")

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            import redis
            from app.core.celery import celery_app

            # 首先尝试使用Celery的broker URL（最可靠的配置）
            broker_url = celery_app.conf.broker_url
            if broker_url:
                # 将celery broker URL转换为redis URL
                if broker_url.startswith('redis://'):
                    redis_url = broker_url
                else:
                    redis_url = f"redis://{broker_url.split('@')[-1]}"
            else:
                # 回退到配置文件中的设置
                from app.core.config import settings
                redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379/0')

            logger.info(f"🔗 尝试连接Redis: {redis_url}")

            # 创建Redis客户端，使用与Celery相同的配置
            self._redis_client = redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            self._redis_client.ping()
            logger.info(f"✅ Redis连接成功: {redis_url}")

            # 验证Redis功能
            test_key = f"{self._redis_key_prefix}test"
            self._redis_client.setex(test_key, 10, "test")
            test_result = self._redis_client.get(test_key)
            if test_result:
                logger.info("✅ Redis读写测试通过")
            else:
                logger.warning("⚠️ Redis读写测试失败")
                self._redis_client.delete(test_key)

        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            # 不要抛出异常，而是设置一个fallback模式
            logger.warning("⚠️ 将使用fallback模式，任务状态将存储在内存中")
            self._redis_client = None
            self._redis_available = False

        # 设置Redis可用性标志
        self._redis_available = self._redis_client is not None

    def _get_task_key(self, task_id: str) -> str:
        """获取任务在Redis中的键名"""
        return f"{self._redis_key_prefix}{task_id}"

    def _get_result_key(self, task_id: str) -> str:
        """获取结果在Redis中的键名"""
        return f"{self._result_key_prefix}{task_id}"

    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((self.callback_host, port))
                return result != 0  # 连接失败表示端口可用
        except Exception as e:
            logger.warning(f"端口检查异常: {e}")
            return False

    def _is_server_responding(self) -> bool:
        """检查服务器是否响应"""
        try:
            import requests
            url = f"http://localhost:{self.callback_port}/health"
            response = requests.get(url, timeout=2)
            return response.status_code == 200
        except Exception:
            # 如果health端点不存在，尝试基本连接
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((self.callback_host, self.callback_port))
                    return result == 0  # 连接成功表示服务器在运行
            except Exception:
                return False

    def _cleanup_expired_cache(self):
        """清理过期的缓存结果"""
        current_time = time.time()
        expired_tasks = []

        for task_id, expiry_time in self._cache_expiry.items():
            if current_time >= expiry_time:
                expired_tasks.append(task_id)

        for task_id in expired_tasks:
            del self._result_cache[task_id]
            del self._cache_expiry[task_id]
            logger.debug(f"清理过期缓存任务: {task_id}")

        if expired_tasks:
            logger.info(f"已清理 {len(expired_tasks)} 个过期缓存任务")

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息（支持Redis和fallback模式）"""
        stats = {
            "server_running": self._server_running,
            "port": self.callback_port,
            "server_pid": self._server_pid,
            "server_responding": self._is_server_responding() if self._server_running else False,
            "current_process_id": os.getpid(),
            "redis_available": self._redis_available,
            "local_pending_tasks": len(self._local_futures)
        }

        if self._redis_available:
            # Redis模式 - 获取全局统计
            try:
                stats_data = self._redis_client.hgetall(self._stats_key)
                for key, value in stats_data.items():
                    if key in ['registered_tasks', 'completed_tasks', 'failed_tasks']:
                        stats[key.decode('utf-8')] = int(value.decode('utf-8'))

                # 获取当前待处理任务数
                pending_keys = self._redis_client.keys(f"{self._redis_key_prefix}*")
                stats['pending_tasks'] = len(pending_keys)

                # 获取缓存结果数
                result_keys = self._redis_client.keys(f"{self._result_key_prefix}*")
                stats['cached_results'] = len(result_keys)

                # 填充默认值
                stats.setdefault('registered_tasks', 0)
                stats.setdefault('completed_tasks', 0)
                stats.setdefault('failed_tasks', 0)

            except Exception as e:
                logger.error(f"获取Redis统计信息失败: {e}")
                stats['redis_error'] = str(e)
                stats['registered_tasks'] = 0
                stats['completed_tasks'] = 0
                stats['failed_tasks'] = 0
                stats['pending_tasks'] = 0
                stats['cached_results'] = 0
        else:
            # Fallback模式 - 使用本地统计
            with self._fallback_lock:
                stats['registered_tasks'] = len(self._fallback_registry)
                stats['pending_tasks'] = len(self._fallback_registry)
                stats['cached_results'] = len(self._fallback_results)
                stats['completed_tasks'] = 0
                stats['failed_tasks'] = 0

        return stats

    def ensure_server_running(self):
        """确保回调服务器正在运行"""
        # 使用互斥锁确保同时只有一个线程能启动服务器
        with self._server_startup_lock:
            current_pid = os.getpid()

            # 如果服务器正在运行且线程活跃，检查是否是当前进程启动的
            if self._server_running and self._server_thread and self._server_thread.is_alive():
                if self._server_pid == current_pid:
                    logger.info("全局回调服务器已在运行（当前进程启动）")
                    return
                else:
                    # 服务器是其他进程启动的，检查是否还能用
                    if self._is_server_responding():
                        logger.info(f"全局回调服务器已在运行（进程 {self._server_pid} 启动），复用现有服务器")
                        return
                    else:
                        logger.warning(f"进程 {self._server_pid} 启动的服务器无响应，重新启动")
                        self._server_running = False
                        self._server_thread = None

            # 如果服务器线程存在但不活跃，重置状态
            if self._server_thread and not self._server_thread.is_alive():
                logger.warning("检测到全局回调服务器线程已退出，重置状态")
                self._server_running = False
                self._server_thread = None
                self._server_pid = None

            # 检查端口是否被占用
            if not self._is_port_available(self.callback_port):
                if self._is_server_responding():
                    logger.info("端口被占用但服务器响应正常，复用现有服务器")
                    self._server_running = True
                    return
                else:
                    logger.error(f"端口 {self.callback_port} 被占用但服务器无响应，无法启动回调服务器")
                    raise RuntimeError(f"回调服务器端口 {self.callback_port} 被占用且无响应")

            # 启动服务器
            self._start_callback_server()

    def register_task(self, task_id: str) -> asyncio.Future:
        """注册任务并返回Future对象（支持Redis和fallback模式）"""
        with self._future_lock:
            # 检查本地是否已有Future
            if task_id in self._local_futures:
                old_future = self._local_futures[task_id]
                if not old_future.done():
                    old_future.cancel()
                del self._local_futures[task_id]

            if self._redis_available:
                # Redis模式
                try:
                    task_data = {
                        'task_id': task_id,
                        'status': 'pending',
                        'created_at': time.time(),
                        'process_id': os.getpid()
                    }

                    task_key = self._get_task_key(task_id)
                    self._redis_client.setex(
                        task_key,
                        3600,
                        pickle.dumps(task_data)
                    )

                    self._increment_stat('registered_tasks')
                    logger.info(f"任务 {task_id} 已注册到Redis，进程ID: {os.getpid()}")

                except Exception as e:
                    logger.error(f"Redis任务注册失败: {e}")
                    # 回退到fallback模式
                    self._redis_available = False

            if not self._redis_available:
                # Fallback模式
                with self._fallback_lock:
                    self._fallback_registry[task_id] = {
                        'task_id': task_id,
                        'status': 'pending',
                        'created_at': time.time(),
                        'process_id': os.getpid()
                    }

            # 创建本地Future
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            future = loop.create_future()
            self._local_futures[task_id] = future

            mode = "Redis" if self._redis_available else "Fallback"
            logger.info(f"任务 {task_id} 本地Future已创建（{mode}模式），当前本地任务数: {len(self._local_futures)}")
            return future

    def get_task(self, task_id: str) -> Optional[asyncio.Future]:
        """获取任务的Future对象"""
        with self._future_lock:
            return self._local_futures.get(task_id)

    def _increment_stat(self, stat_name: str):
        """增加统计计数"""
        if self._redis_available:
            try:
                self._redis_client.hincrby(self._stats_key, stat_name, 1)
            except Exception as e:
                logger.error(f"更新Redis统计失败: {e}")
                # 回退到fallback模式
                self._redis_available = False

    def _check_task_exists_in_redis(self, task_id: str) -> bool:
        """检查任务是否在存储中存在"""
        if self._redis_available:
            try:
                task_key = self._get_task_key(task_id)
                return self._redis_client.exists(task_key) > 0
            except Exception as e:
                logger.error(f"检查Redis任务状态失败: {e}")
                return False
        else:
            # Fallback模式
            with self._fallback_lock:
                return task_id in self._fallback_registry

    def _check_result_exists_in_redis(self, task_id: str) -> bool:
        """检查结果是否在存储中存在"""
        if self._redis_available:
            try:
                result_key = self._get_result_key(task_id)
                return self._redis_client.exists(result_key) > 0
            except Exception as e:
                logger.error(f"检查Redis结果状态失败: {e}")
                return False
        else:
            # Fallback模式
            with self._fallback_lock:
                return task_id in self._fallback_results

    def complete_task(self, task_id: str, result: Any):
        """完成任务并设置结果（支持Redis和fallback模式）"""
        current_time = time.time()

        if self._redis_available:
            # Redis模式
            try:
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

                logger.info(f"✅ 任务 {task_id} 结果已存储到Redis")

                # 从Redis中移除任务状态
                task_key = self._get_task_key(task_id)
                self._redis_client.delete(task_key)

            except Exception as e:
                logger.error(f"Redis操作失败: {e}")
                # 回退到fallback模式
                self._redis_available = False

        if not self._redis_available:
            # Fallback模式
            with self._fallback_lock:
                self._fallback_results[task_id] = {
                    'result': result,
                    'completed_at': current_time,
                    'status': 'completed'
                }
                self._fallback_expiry[task_id] = current_time + 300  # 5分钟过期

                # 从fallback注册表中移除任务
                if task_id in self._fallback_registry:
                    del self._fallback_registry[task_id]

                logger.info(f"✅ 任务 {task_id} 结果已存储到Fallback缓存")

        # 2. 尝试在本地Future中设置结果
        with self._future_lock:
            local_future = self._local_futures.get(task_id)

            if local_future and not local_future.done():
                try:
                    loop = local_future.get_loop()
                    if loop.is_running():
                        loop.call_soon_threadsafe(local_future.set_result, result)
                    else:
                        loop.run_until_complete(local_future.set_result(result))

                    if self._redis_available:
                        self._increment_stat('completed_tasks')

                    mode = "Redis" if self._redis_available else "Fallback"
                    logger.info(f"✅ 任务 {task_id} 本地Future已完成（{mode}模式），结果已设置")

                except Exception as e:
                    logger.error(f"设置本地Future结果失败: {e}")
            else:
                mode = "Redis" if self._redis_available else "Fallback"
                logger.info(f"✅ 任务 {task_id} 回调已接收，结果已存储到{mode}缓存（5分钟有效期）")

    def fail_task(self, task_id: str, error: Exception):
        """标记任务失败"""
        with self._task_lock:
            future = self._task_registry.get(task_id)
            if future and not future.done():
                try:
                    loop = future.get_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    loop.call_soon_threadsafe(future.set_exception, error)
                else:
                    loop.run_until_complete(future.set_exception(error))

                self._failed_tasks += 1
                logger.info(f"任务 {task_id} 已标记为失败: {error}")
            else:
                # 任务可能已超时清理，缓存错误结果供后续获取
                error_result = {
                    'task_id': task_id,
                    'status': 'failed',
                    'error_message': str(error),
                    'error_type': type(error).__name__
                }
                self._result_cache[task_id] = error_result
                self._cache_expiry[task_id] = time.time() + 300  # 5分钟缓存
                logger.warning(f"任务 {task_id} 不存在或已完成，错误结果已缓存（5分钟有效期）")

    def get_cached_result(self, task_id: str) -> Optional[Any]:
        """获取缓存的结果（支持Redis和fallback模式）"""
        # 首先尝试从Redis获取
        if self._redis_available:
            try:
                result_key = self._get_result_key(task_id)
                result_data = self._redis_client.get(result_key)

                if result_data:
                    data = pickle.loads(result_data)
                    logger.info(f"✅ 从Redis缓存获取任务 {task_id} 的结果")
                    return data.get('result')

            except Exception as e:
                logger.error(f"获取Redis缓存结果失败: {e}")
                # 不要回退到fallback模式，继续检查本地缓存

        # 从fallback缓存获取
        with self._fallback_lock:
            if task_id in self._fallback_results:
                # 检查是否过期
                expiry_time = self._fallback_expiry.get(task_id, 0)
                if current_time < expiry_time:
                    result_data = self._fallback_results[task_id]
                    logger.info(f"✅ 从Fallback缓存获取任务 {task_id} 的结果")
                    return result_data.get('result')
                else:
                    # 清理过期的fallback缓存
                    del self._fallback_results[task_id]
                    del self._fallback_expiry[task_id]
                    logger.info(f"任务 {task_id} 的Fallback缓存结果已过期，已清理")

        return None

    
    def _start_callback_server(self):
        """启动全局回调服务器"""
        if self._server_running:
            return

        # 再次检查端口可用性（双重检查）
        if not self._is_port_available(self.callback_port):
            if self._is_server_responding():
                logger.info("服务器已在运行，无需启动")
                self._server_running = True
                return
            else:
                logger.error(f"端口 {self.callback_port} 被占用，无法启动服务器")
                return

        self._server_running = True
        self._process_id = None
        self._server_pid = os.getpid()  # 记录启动服务器的进程ID

        logger.info(f"启动全局回调服务器，端口: {self.callback_port}，进程ID: {self._server_pid}")
        self._server_thread = threading.Thread(
            target=self._run_callback_server,
            name="GlobalCallbackServer",
            daemon=True
        )
        self._server_thread.start()

        # 等待服务器启动并验证
        time.sleep(1.0)

        # 验证服务器是否真正启动
        if self._is_server_responding():
            logger.info(f"✅ 全局回调服务器启动成功，线程ID: {self._server_thread.ident}")
        else:
            logger.error("❌ 全局回调服务器启动失败，无法响应连接")
            self._server_running = False
            self._server_thread = None
            self._server_pid = None

    def _run_callback_server(self):
        """运行全局回调服务器"""
        self._process_id = None

        async def callback_handler(request):
            try:
                current_time = time.time()
                logger.info("全局回调处理器被触发")
                logger.info(f"回调到达时间: {current_time}")
                logger.info(f"请求方法: {request.method}")
                logger.info(f"请求头: {dict(request.headers)}")
                logger.info(f"请求远程地址: {request.remote}")

                payload = await request.json()
                logger.info(f"收到回调: {json.dumps(payload, indent=2)}")

                task_id = payload.get('task_id')
                if not task_id:
                    logger.error("回调中缺少task_id")
                    return web.Response(status=400, text='Missing task_id')

                logger.info(f"处理任务ID: {task_id}")

                # 调试：检查任务状态（Redis模式）
                is_registered = self._check_task_exists_in_redis(task_id)
                in_cache = self._check_result_exists_in_redis(task_id)

                # 检查本地Future
                with self._future_lock:
                    local_future = self._local_futures.get(task_id)
                    local_status = "本地存在" if local_future else "本地不存在"
                    if local_future:
                        local_status += f" (done: {local_future.done()})"

                redis_status = "Redis存在" if is_registered else "Redis不存在"
                cache_status = "结果缓存存在" if in_cache else "结果缓存不存在"

                logger.info(f"任务状态检查 - Redis: {redis_status}, {cache_status}, {local_status}")

                # 处理任务结果
                if payload.get('status') == 'completed':
                    logger.info(f"任务 {task_id} 完成，设置结果")
                    # 确保srt_url是完整URL
                    srt_url = payload.get('srt_url')
                    if srt_url and not srt_url.startswith('http'):
                        # 需要从当前客户端实例获取api_url，这里先保持原样
                        logger.info(f"保持原始srt_url: {srt_url}")
                    self.complete_task(task_id, payload)
                else:
                    error_msg = payload.get('error_message', '任务失败')
                    logger.info(f"任务 {task_id} 失败: {error_msg}")
                    self.fail_task(task_id, RuntimeError(error_msg))

                logger.info("返回OK响应")
                return web.Response(text='OK')

            except Exception as e:
                logger.error(f"回调处理错误: {e}", exc_info=True)
                return web.Response(status=500, text=str(e))

        async def health_check(request):
            """健康检查端点"""
            return web.Response(text='OK', status=200)

        async def create_app():
            app = web.Application()
            app.router.add_post('/callback', callback_handler)
            app.router.add_get('/health', health_check)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.callback_host, self.callback_port)
            await site.start()

            logger.info(f"✅ 全局回调服务器启动于端口 {self.callback_port}")
            logger.info(f"回调URL: http://localhost:{self.callback_port}/callback")
            logger.info(f"健康检查URL: http://localhost:{self.callback_port}/health")

            # 保持运行
            while self._server_running:
                await asyncio.sleep(1)

            logger.info("全局回调服务器正在关闭...")

        try:
            # 创建新的事件循环用于回调服务器
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(create_app())
        except OSError as e:
            if "address already in use" in str(e).lower():
                logger.error(f"❌ 端口 {self.callback_port} 已被占用，全局回调服务器启动失败")
                # 检查是否有其他服务器在运行
                if self._is_server_responding():
                    logger.info("检测到其他服务器在运行，将尝试使用现有服务器")
                    self._server_running = True  # 标记为可用，使用现有服务器
                else:
                    logger.error("端口被占用但没有响应的服务器，无法启动回调服务器")
                    self._server_running = False
            else:
                logger.error(f"❌ 全局回调服务器网络错误: {e}", exc_info=True)
                self._server_running = False
        except Exception as e:
            logger.error(f"❌ 全局回调服务器运行时错误: {e}", exc_info=True)
            self._server_running = False
        finally:
            logger.info("全局回调服务器线程结束")

    def shutdown(self):
        """关闭全局回调服务器"""
        logger.info("正在关闭全局回调服务器...")

        # 设置服务器停止标志
        self._server_running = False

        # 取消所有待处理的任务并清理缓存
        with self._task_lock:
            for task_id, future in self._task_registry.items():
                if not future.done():
                    future.cancel()
            self._task_registry.clear()

            # 清理所有缓存
            self._result_cache.clear()
            self._cache_expiry.clear()

        # 等待服务器线程结束
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5.0)
            if self._server_thread.is_alive():
                logger.warning("全局回调服务器线程未能正常关闭")

        # 清理状态
        self._server_thread = None
        self._server_pid = None
        self._process_id = None

        logger.info("全局回调服务器已关闭")


# 全局实例
global_callback_manager = GlobalCallbackManager()


# 信号处理
def _signal_handler(signum, frame):
    """处理关闭信号"""
    logger.info(f"收到信号 {signum}，关闭全局回调服务器...")
    global_callback_manager.shutdown()


# 注册信号处理器
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)