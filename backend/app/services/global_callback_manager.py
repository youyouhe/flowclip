"""
全局回调服务器管理器
统一管理TUS ASR回调服务器，支持固定端口和任务队列复用
"""

import asyncio
import threading
import time
import logging
import signal
import socket
import os
from typing import Dict, Optional, Any
from aiohttp import web
import json

logger = logging.getLogger(__name__)


class GlobalCallbackManager:
    """全局回调服务器管理器 - 单例模式"""

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

        # 任务管理
        self._task_registry: Dict[str, asyncio.Future] = {}  # {task_id: Future}
        self._task_lock = threading.RLock()  # 可重入锁
        self._process_id = None

        # 统计信息
        self._registered_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0

        logger.info("全局回调服务器管理器初始化完成")

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

    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "registered_tasks": self._registered_tasks,
            "completed_tasks": self._completed_tasks,
            "failed_tasks": self._failed_tasks,
            "pending_tasks": len(self._task_registry),
            "server_running": self._server_running,
            "port": self.callback_port,
            "server_pid": self._server_pid,
            "server_responding": self._is_server_responding() if self._server_running else False
        }

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
        """注册任务并返回Future对象"""
        with self._task_lock:
            if task_id in self._task_registry:
                logger.warning(f"任务 {task_id} 已存在，移除旧的Future")
                # 如果旧的Future还没完成，取消它
                old_future = self._task_registry[task_id]
                if not old_future.done():
                    old_future.cancel()

            # 创建新的Future - 使用当前事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 如果没有运行中的loop，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            future = loop.create_future()

            self._task_registry[task_id] = future
            self._registered_tasks += 1

            logger.info(f"任务 {task_id} 已注册，当前待处理任务数: {len(self._task_registry)}")
            return future

    def get_task(self, task_id: str) -> Optional[asyncio.Future]:
        """获取任务的Future对象"""
        with self._task_lock:
            return self._task_registry.get(task_id)

    def complete_task(self, task_id: str, result: Any):
        """完成任务并设置结果"""
        with self._task_lock:
            future = self._task_registry.get(task_id)
            if future and not future.done():
                # 获取或创建事件循环来设置结果
                try:
                    loop = future.get_loop()
                except RuntimeError:
                    # 如果Future没有关联的loop，创建新的
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # 在正确的loop中设置结果
                if loop.is_running():
                    loop.call_soon_threadsafe(future.set_result, result)
                else:
                    loop.run_until_complete(future.set_result(result))

                self._completed_tasks += 1
                logger.info(f"任务 {task_id} 已完成，结果已设置")
            else:
                logger.warning(f"任务 {task_id} 不存在或已完成")

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
                logger.warning(f"任务 {task_id} 不存在或已完成")

    def cleanup_task(self, task_id: str):
        """清理任务"""
        with self._task_lock:
            if task_id in self._task_registry:
                future = self._task_registry[task_id]
                if not future.done():
                    future.cancel()
                del self._task_registry[task_id]
                logger.info(f"任务 {task_id} 已从注册表中清理")

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
                logger.info("全局回调处理器被触发")
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

        # 取消所有待处理的任务
        with self._task_lock:
            for task_id, future in self._task_registry.items():
                if not future.done():
                    future.cancel()
            self._task_registry.clear()

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