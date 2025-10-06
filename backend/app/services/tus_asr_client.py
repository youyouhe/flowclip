"""
TUS ASR客户端集成类
封装TUS协议操作，适配现有的音频处理流程
"""

import os
import asyncio
import aiohttp
import json
import time
import threading
import logging
import signal
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from aiohttp import web

from app.core.config import settings
from app.services.global_callback_manager import global_callback_manager
from app.services.standalone_callback_client import standalone_callback_client

logger = logging.getLogger(__name__)


class TusASRClient:
    """TUS ASR客户端，为FlowClip系统提供TUS协议支持"""

    # 类级别属性初始化
    _callback_running = False
    _callback_server_thread = None

    # 是否使用独立回调服务器
    _use_standalone_callback = settings.tus_use_standalone_callback
    _use_global_callback = settings.tus_use_global_callback and not settings.tus_use_standalone_callback

    @classmethod
    def _process_signal_handler(cls, signum, frame):
        """处理进程级别的关闭信号"""
        logger.info(f"收到进程信号 {signum}，正在关闭回调服务器...")
        cls._callback_running = False

    @classmethod
    def _ensure_callback_server_running(cls):
        """确保进程级别的回调服务器正在运行"""
        if cls._callback_running and cls._callback_server_thread and cls._callback_server_thread.is_alive():
            logger.info("进程级别回调服务器已在运行")
            return

        # 如果服务器线程存在但不活跃，重置状态
        if cls._callback_server_thread and not cls._callback_server_thread.is_alive():
            logger.warning("检测到进程级别回调服务器线程已退出，重置状态")
            cls._callback_running = False
            cls._callback_server_thread = None

        # 如果需要重新启动服务器，由调用方处理
        # 这里只做检查，不启动服务器
        logger.info("进程级别回调服务器检查完成")

    def __init__(
        self,
        api_url: str = None,
        tus_url: str = None,
        callback_port: int = None,
        callback_host: str = None,
        max_retries: int = None,
        timeout_seconds: int = None
    ):
        """
        初始化TUS ASR客户端

        Args:
            api_url: ASR API服务器URL
            tus_url: TUS上传服务器URL
            callback_port: 回调监听端口
            callback_host: 回调主机IP
            max_retries: 最大重试次数
            timeout_seconds: 超时时间(秒)
        """
        from app.core.config import settings

        # 首先使用提供的参数或settings中的默认值
        self.api_url = (api_url or settings.tus_api_url).rstrip('/')
        self.tus_url = (tus_url or settings.tus_upload_url).rstrip('/')
        self.callback_host = callback_host or settings.tus_callback_host
        self.max_retries = max_retries or settings.tus_max_retries

        # 确保超时设置不超过安全限制
        configured_timeout = timeout_seconds or settings.tus_timeout_seconds
        self.timeout_seconds = min(configured_timeout, 1700)  # 限制在1700秒以内

        # 回调端口配置 - 支持固定端口模式
        if self._use_global_callback:
            # 使用全局回调服务器的固定端口
            self.callback_port = getattr(settings, 'tus_callback_port', 9090)
            logger.info(f"使用全局回调服务器模式，固定端口: {self.callback_port}")
        else:
            # 传统模式：自动为每个客户端分配不同的端口
            if callback_port:
                self.callback_port = callback_port
            else:
                self.callback_port = self._get_unique_callback_port()
            logger.info(f"使用传统动态端口模式，分配端口: {self.callback_port}")

        # 然后尝试从数据库动态更新配置（但不覆盖端口）
        self._load_config_from_database_without_port()

        # 内部状态管理
        if self._use_standalone_callback:
            # 独立回调服务器模式
            self.completed_tasks = {}  # 保留兼容性，但实际不使用
            self.callback_manager = standalone_callback_client
            self.process_id = os.getpid()  # 记录进程ID用于日志
            logger.info("使用独立回调服务器模式")
        elif self._use_global_callback:
            # 全局模式：使用全局管理器
            self.completed_tasks = {}  # 保留兼容性，但实际不使用
            self.callback_manager = global_callback_manager
            self.process_id = os.getpid()  # 记录进程ID用于日志

            # 确保全局回调服务器正在运行
            self.callback_manager.ensure_server_running()
            logger.info("全局回调服务器状态检查完成")
        else:
            # 传统模式：进程级别管理
            self.completed_tasks = {}
            self.process_id = os.getpid()  # 记录进程ID用于日志

            # 检查进程级别回调服务器是否已启动
            TusASRClient._ensure_callback_server_running()

        # 信号处理
        signal.signal(signal.SIGINT, TusASRClient._process_signal_handler)
        signal.signal(signal.SIGTERM, TusASRClient._process_signal_handler)

        logger.info(f"TUS ASR客户端初始化完成 (PID: {self.process_id}):")
        logger.info(f"  API URL: {self.api_url}")
        logger.info(f"  TUS URL: {self.tus_url}")
        logger.info(f"  回调端口: {self.callback_port}")
        logger.info(f"  回调主机: {self.callback_host}")

    def _load_config_from_database(self):
        """从数据库动态加载TUS配置"""
        try:
            import asyncio
            from app.core.database import get_sync_db
            from app.services.system_config_service import SystemConfigService

            # 使用同步数据库连接
            with get_sync_db() as db:
                # 从数据库获取所有配置
                db_configs = SystemConfigService.get_all_configs_sync(db)

                # 更新TUS配置
                for config_key, config_value in db_configs.items():
                    if config_key == 'tus_api_url':
                        self.api_url = config_value.rstrip('/')
                        logger.info(f"从数据库加载TUS API URL: {self.api_url}")
                    elif config_key == 'tus_upload_url':
                        self.tus_url = config_value.rstrip('/')
                        logger.info(f"从数据库加载TUS上传URL: {self.tus_url}")
                    elif config_key == 'tus_callback_port':
                        self.callback_port = int(config_value)
                        logger.info(f"从数据库加载TUS回调端口: {self.callback_port}")
                    elif config_key == 'tus_callback_host':
                        self.callback_host = config_value
                        logger.info(f"从数据库加载TUS回调主机: {self.callback_host}")
                    elif config_key == 'tus_max_retries':
                        self.max_retries = int(config_value)
                        logger.info(f"从数据库加载TUS最大重试次数: {self.max_retries}")
                    elif config_key == 'tus_timeout_seconds':
                        self.timeout_seconds = int(config_value)
                        logger.info(f"从数据库加载TUS超时时间: {self.timeout_seconds}")
                    elif config_key == 'tus_file_size_threshold_mb':
                        # 更新文件大小检测器的阈值
                        from app.services.file_size_detector import file_size_detector
                        threshold_mb = int(config_value)
                        file_size_detector.threshold_mb = threshold_mb
                        file_size_detector.threshold_bytes = threshold_mb * 1024 * 1024
                        logger.info(f"从数据库加载TUS文件大小阈值: {threshold_mb}MB")

        except Exception as e:
            logger.warning(f"从数据库加载TUS配置失败: {e}，使用默认配置")

    def _load_config_from_database_without_port(self):
        """从数据库动态加载TUS配置，但不覆盖端口设置"""
        try:
            import asyncio
            from app.core.database import get_sync_db
            from app.services.system_config_service import SystemConfigService

            # 使用同步数据库连接
            with get_sync_db() as db:
                # 从数据库获取所有配置
                db_configs = SystemConfigService.get_all_configs_sync(db)

                # 更新TUS配置（不包括端口）
                for config_key, config_value in db_configs.items():
                    if config_key == 'tus_api_url':
                        self.api_url = config_value.rstrip('/')
                        logger.info(f"从数据库加载TUS API URL: {self.api_url}")
                    elif config_key == 'tus_upload_url':
                        self.tus_url = config_value.rstrip('/')
                        logger.info(f"从数据库加载TUS上传URL: {self.tus_url}")
                    elif config_key == 'tus_callback_host':
                        self.callback_host = config_value
                        logger.info(f"从数据库加载TUS回调主机: {self.callback_host}")
                    elif config_key == 'tus_max_retries':
                        self.max_retries = int(config_value)
                        logger.info(f"从数据库加载TUS最大重试次数: {self.max_retries}")
                    elif config_key == 'tus_timeout_seconds':
                        self.timeout_seconds = int(config_value)
                        logger.info(f"从数据库加载TUS超时时间: {self.timeout_seconds}")
                    elif config_key == 'tus_file_size_threshold_mb':
                        # 更新文件大小检测器的阈值
                        from app.services.file_size_detector import file_size_detector
                        threshold_mb = int(config_value)
                        file_size_detector.threshold_mb = threshold_mb
                        file_size_detector.threshold_bytes = threshold_mb * 1024 * 1024
                        logger.info(f"从数据库加载TUS文件大小阈值: {threshold_mb}MB")

        except Exception as e:
            logger.warning(f"从数据库加载TUS配置失败: {e}，使用默认配置")


    def _is_port_available(self, port):
        """检查端口是否可用"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            # 如果连接成功，说明端口被占用
            return result != 0
        except Exception as e:
            logger.error(f"检查端口 {port} 可用性时出错: {e}")
            return False

    async def process_audio_file(
        self,
        audio_file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        处理音频文件的主要入口点

        Args:
            audio_file_path: 音频文件路径
            metadata: ASR处理元数据

        Returns:
            Dict: 处理结果，包含SRT内容和状态信息
        """
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_file_path}")

        if not audio_path.is_file():
            raise ValueError(f"路径不是文件: {audio_file_path}")

        logger.info(f"开始TUS ASR处理: {audio_file_path}")
        logger.info(f"文件大小: {audio_path.stat().st_size} bytes")

        try:
            if self._use_global_callback:
                # 全局模式：确保全局回调服务器正在运行
                logger.info("全局模式：确保全局回调服务器正在运行...")
                self.callback_manager.ensure_server_running()
                await asyncio.sleep(1.0)  # 等待全局回调服务器启动

                # 验证全局回调服务器是否启动
                logger.info("开始验证全局回调服务器启动状态...")
                port_ready = False
                for attempt in range(5):
                    try:
                        import socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1.0)  # 设置超时时间
                        result = sock.connect_ex(('127.0.0.1', self.callback_port))
                        sock.close()

                        if result == 0:
                            port_ready = True
                            logger.info(f"✅ 验证成功：全局回调服务器已在端口 {self.callback_port} 启动并接受连接")
                            break
                        else:
                            logger.warning(f"验证尝试 {attempt + 1}/5：全局回调服务器可能还未启动或未接受连接，端口 {self.callback_port}，等待重试...")
                            await asyncio.sleep(2.0)
                    except Exception as e:
                        logger.warning(f"验证尝试 {attempt + 1}/5 出错: {e}")
                        await asyncio.sleep(2.0)

                if not port_ready:
                    logger.error(f"❌ 全局回调服务器启动验证失败，端口 {self.callback_port} 无法连接")
                    raise RuntimeError(f"全局回调服务器启动失败，端口 {self.callback_port} 无法访问")

                # 检查全局回调服务器状态
                if self.callback_manager._server_running:
                    logger.info("全局回调服务器状态：正在运行")
                    logger.info(f"全局管理器统计: {self.callback_manager.stats}")
                else:
                    logger.error("全局回调服务器状态：已停止运行")
                    raise RuntimeError("全局回调服务器异常停止")

            else:
                # 传统模式：启动本地回调服务器
                logger.info("传统模式：开始启动本地回调服务器...")
                self._start_callback_server()
                await asyncio.sleep(2.0)  # 等待本地回调服务器启动（延长等待时间）

                # 验证本地回调服务器是否启动 - 多次尝试
                logger.info("开始验证本地回调服务器启动状态...")
                port_ready = False
                for attempt in range(5):
                    try:
                        import socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1.0)  # 设置超时时间
                        result = sock.connect_ex(('127.0.0.1', self.callback_port))
                        sock.close()

                        if result == 0:
                            port_ready = True
                            logger.info(f"✅ 验证成功：本地回调服务器已在端口 {self.callback_port} 启动并接受连接")
                            break
                        else:
                            logger.warning(f"验证尝试 {attempt + 1}/5：本地回调服务器可能还未启动或未接受连接，端口 {self.callback_port}，等待重试...")
                            await asyncio.sleep(2.0)
                    except Exception as e:
                        logger.warning(f"验证尝试 {attempt + 1}/5 出错: {e}")
                        await asyncio.sleep(2.0)

                if not port_ready:
                    logger.error(f"❌ 本地回调服务器启动验证失败，端口 {self.callback_port} 无法连接")
                    raise RuntimeError(f"本地回调服务器启动失败，端口 {self.callback_port} 无法访问")

                # 检查进程级别回调服务器线程是否仍在运行
                if self.__class__._callback_server_thread and self.__class__._callback_server_thread.is_alive():
                    logger.info("本地回调服务器线程状态：正在运行")
                else:
                    logger.error("本地回调服务器线程状态：已停止运行")
                    raise RuntimeError("本地回调服务器线程异常停止")

            # 执行TUS处理流程
            result = await self._execute_tus_pipeline(audio_file_path, metadata or {})
            return result

        except KeyboardInterrupt:
            logger.info("用户中断处理")
            raise
        except Exception as e:
            logger.error(f"TUS ASR处理失败: {e}", exc_info=True)
            # 提供更详细的错误信息
            error_info = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'file_path': audio_file_path,
                'timestamp': time.time()
            }
            logger.error(f"TUS ASR处理失败详情: {json.dumps(error_info, indent=2)}")
            # 清理当前任务
            if hasattr(self, 'current_task_id'):
                if self._use_global_callback:
                    # 全局模式：清理全局管理器中的任务
                    self.callback_manager.cleanup_task(self.current_task_id)
                else:
                    # 传统模式：清理本地任务
                    if self.current_task_id in self.completed_tasks:
                        del self.completed_tasks[self.current_task_id]
            raise RuntimeError(f"TUS ASR处理失败: {str(e)}") from e

    def _get_unique_callback_port(self) -> int:
        """获取唯一的回调端口，使用Docker映射的端口范围"""
        base_port = getattr(self, '__class__', TusASRClient)._base_port if hasattr(TusASRClient, '_base_port') else 9100
        process_id = os.getpid()

        # 在Docker映射的9000-9200范围内选择唯一端口
        port = base_port + (process_id % 101)  # 9100 + 0-100 = 9100-9200

        logger.info(f"为进程 {process_id} 分配唯一回调端口: {port} (Docker映射范围: 9100-9200)")
        return port

    def _get_available_port(self) -> int:
        """动态查找可用的回调端口"""
        base_port = 9100
        max_ports = 100  # 最多尝试100个端口

        for offset in range(max_ports):
            port = base_port + offset
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()

                if result != 0:  # 端口可用
                    logger.info(f"找到可用端口: {port}")
                    return port
                else:
                    logger.debug(f"端口 {port} 被占用，尝试下一个")
            except Exception as e:
                logger.debug(f"检查端口 {port} 时出错: {e}")
                continue

        # 如果都不可用，返回一个尽量唯一的端口
        import random
        fallback_port = 10000 + random.randint(0, 999)
        logger.warning(f"无法找到可用端口，使用随机端口: {fallback_port}")
        return fallback_port

    # 类变量
    _base_port = 9100

    async def _execute_tus_pipeline(
        self,
        audio_file_path: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行完整的TUS处理流水线"""
        audio_path = Path(audio_file_path)
        start_time = time.time()  # 记录开始时间用于统计

        try:
            # 检查回调管理器是否可用
            redis_available = True
            if self._use_standalone_callback:
                # 独立回调客户端：检查Redis客户端是否存在
                redis_available = self.callback_manager._redis_client is not None
            elif self._use_global_callback:
                # 全局回调管理器：检查Redis可用标志
                redis_available = self.callback_manager._redis_available

            if not redis_available:
                logger.warning("⚠️ 回调管理器Redis不可用，回退到标准ASR处理")
                return await self._fallback_to_standard_asr(audio_file_path, metadata, start_time)

            # 步骤1: 创建ASR任务
            # 步骤1: 创建ASR任务
            logger.info("📝 步骤1: 创建ASR任务...")
            task_info = await self._create_tus_task(audio_file_path, metadata)
            task_id = task_info['task_id']
            upload_url = task_info['upload_url']

            logger.info(f"✅ 任务创建: {task_id}")
            logger.info(f"📤 上传URL: {upload_url}")

            # 步骤2: TUS文件上传
            logger.info("📤 步骤2: TUS文件上传...")
            await self._upload_file_via_tus(audio_file_path, upload_url)
            logger.info("✅ 文件上传完成")

            # 步骤3: 等待ASR处理结果
            logger.info("🎧 步骤3: 等待ASR处理...")
            logger.info(f"准备等待任务 {task_id} 的结果")
            srt_content = await self._wait_for_tus_results(task_id)
            logger.info("✅ ASR处理完成")

            # 上传SRT内容到MinIO（如果需要的话）
            srt_url = None
            if srt_content:
                # 从metadata中获取用户和项目信息
                user_id = metadata.get('user_id', 1)
                project_id = metadata.get('project_id', 1)
                video_id = metadata.get('video_id', 'unknown')

                # 生成对象名称
                srt_filename = f"{video_id}.srt"
                srt_object_name = f"users/{user_id}/projects/{project_id}/subtitles/{srt_filename}"

                # 上传到MinIO
                try:
                    tmp_srt_path = None
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as tmp_srt_file:
                            tmp_srt_file.write(srt_content)
                            tmp_srt_path = tmp_srt_file.name

                        from app.services.minio_client import minio_service
                        srt_url = await minio_service.upload_file(
                            tmp_srt_path,
                            srt_object_name,
                            "text/srt"
                        )

                        # 清理临时文件
                        if tmp_srt_path:
                            import os
                            if os.path.exists(tmp_srt_path):
                                os.unlink(tmp_srt_path)
                    except Exception as upload_error:
                        logger.error(f"SRT文件上传失败: {upload_error}")
                        # 清理临时文件
                        if tmp_srt_path:
                            import os
                            if os.path.exists(tmp_srt_path):
                                os.unlink(tmp_srt_path)
                        raise
                except Exception as e:
                    logger.error(f"上传SRT到MinIO失败: {e}")

            return {
                'success': True,
                'strategy': 'tus',
                'task_id': task_id,
                'srt_content': srt_content,
                'srt_url': srt_url,  # 添加SRT URL
                'minio_path': srt_url,  # 兼容性字段
                'object_name': srt_object_name if 'srt_object_name' in locals() else None,
                'file_path': audio_file_path,
                'metadata': metadata,
                'processing_time': time.time() - start_time if 'start_time' in locals() else 0,
                'file_size': audio_path.stat().st_size if 'audio_path' in locals() else 0
            }
        except Exception as e:
            logger.error(f"TUS处理流水线执行失败: {e}", exc_info=True)
            elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
            raise RuntimeError(f"TUS处理流水线执行失败: {str(e)} (已处理 {elapsed_time:.1f} 秒)") from e

    async def _create_tus_task(
        self,
        audio_file_path: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建TUS ASR任务"""
        audio_path = Path(audio_file_path)

        # 准备任务创建载荷
        payload = {
            "filename": audio_path.name,
            "filesize": audio_path.stat().st_size,
            "metadata": {
                "language": metadata.get("language", "auto"),
                "model": metadata.get("model", "large-v3-turbo")
            }
        }

        # 生成回调URL
        callback_url = self._generate_callback_url()
        if callback_url:
            payload["callback_url"] = callback_url

        logger.info(f"创建TUS任务，载荷: {json.dumps(payload, indent=2)}")

        # 添加重试机制
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"尝试创建TUS任务 (尝试 {attempt + 1}/{self.max_retries})")
                logger.info(f"API请求URL: {self.api_url}/api/v1/asr-tasks")
                logger.info(f"API请求载荷: {json.dumps(payload, indent=2)}")

                async with aiohttp.ClientSession() as session:
                    logger.info("创建aiohttp客户端会话")
                    # 添加认证头 - 支持从数据库配置读取
                    headers = {}
                    # 优先从数据库配置读取，如果没有则使用环境变量
                    if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
                        headers['X-API-Key'] = settings.asr_api_key

                    # 添加ngrok绕过头
                    headers['ngrok-skip-browser-warning'] = 'true'

                    async with session.post(
                        f"{self.api_url}/api/v1/asr-tasks",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        logger.info(f"API响应状态码: {response.status}")
                        if response.status == 200:
                            logger.info("开始解析API响应JSON")
                            result = await response.json()
                            logger.info(f"API响应内容: {json.dumps(result, indent=2)}")
                            if 'task_id' not in result or 'upload_url' not in result:
                                raise ValueError(f"无效的API响应: {result}")

                            # 保存任务ID供后续使用
                            self.current_task_id = result['task_id']
                            logger.info(f"TUS任务创建成功: {result['task_id']}")
                            return result
                        else:
                            error_text = await response.text()
                            logger.warning(f"API请求失败，状态码: {response.status}, 响应: {error_text}")
                            raise RuntimeError(f"API请求失败，状态码: {response.status}, 响应: {error_text}")

            except Exception as e:
                last_error = e
                logger.warning(f"TUS任务创建失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    # 使用指数退避算法，基础等待时间为1秒，最大等待时间为30秒
                    wait_time = min(1 * (2 ** attempt), 30)
                    logger.info(f"等待 {wait_time} 秒后重试 (指数退避)...")
                    await asyncio.sleep(wait_time)
                else:
                    break

        # 所有重试都失败
        error_msg = f"TUS任务创建失败，已重试 {self.max_retries} 次。最后错误: {str(last_error)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    async def _upload_file_via_tus(
        self,
        audio_file_path: str,
        upload_url: str
    ) -> None:
        """通过TUS协议上传文件"""
        audio_path = Path(audio_file_path)
        file_size = audio_path.stat().st_size

        logger.info(f"开始TUS上传: {audio_path.name} ({file_size} bytes)")

        try:
            # 从upload_url提取upload_id
            upload_id = upload_url.split('/')[-1]

            # 创建TUS上传会话
            tus_upload_id = await self._create_tus_upload_session(upload_id, file_size, audio_path.name)

            # 分块上传文件数据
            await self._upload_tus_chunks(tus_upload_id, audio_path)

            logger.info(f"TUS上传完成: {audio_path.name}")
        except Exception as e:
            logger.error(f"TUS文件上传失败: {e}", exc_info=True)
            raise RuntimeError(f"TUS文件上传失败: {str(e)}") from e

    async def _create_tus_upload_session(
        self,
        upload_id: str,
        file_size: int,
        filename: str
    ) -> str:
        """创建TUS上传会话"""
        task_id = getattr(self, 'current_task_id', None)

        # 构建TUS元数据
        metadata_parts = [f'filename {filename}']
        if task_id:
            metadata_parts.append(f'task_id {task_id}')

        headers = {
            'Tus-Resumable': '1.0.0',
            'Upload-Length': str(file_size),
            'Upload-Metadata': ', '.join(metadata_parts)
        }

        # 添加认证头 - 支持从数据库配置读取
        if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
            headers['X-API-Key'] = settings.asr_api_key

        # 添加ngrok绕过头
        headers['ngrok-skip-browser-warning'] = 'true'

        # 添加重试机制
        last_error = None
        for attempt in range(3):  # 最多重试3次
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.tus_url}/files"
                    logger.info(f"创建TUS上传会话: {url}")
                    logger.info(f"请求头: {headers}")

                    async with session.post(url, headers=headers) as response:
                        logger.info(f"TUS响应状态码: {response.status}")
                        logger.info(f"TUS响应头: {dict(response.headers)}")

                        if response.status != 201:  # TUS创建上传会话应该返回201
                            error_text = await response.text()
                            logger.error(f"TUS上传会话创建失败，状态码: {response.status}, 响应: {error_text}")
                            raise RuntimeError(f"TUS上传会话创建失败，状态码: {response.status}, 响应: {error_text}")

                        # 从Location头获取上传URL
                        location = response.headers.get('Location', '')
                        if not location:
                            raise ValueError("TUS响应中缺少Location头")

                        # 提取实际的upload_id
                        actual_upload_id = location.split('/')[-1]
                        logger.info(f"TUS上传会话创建成功: {actual_upload_id}")

                        return actual_upload_id
            except Exception as e:
                last_error = e
                logger.warning(f"TUS上传会话创建失败 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:  # 还有重试次数
                    # 使用指数退避算法，基础等待时间为1秒，最大等待时间为30秒
                    wait_time = min(1 * (2 ** attempt), 30)
                    logger.info(f"等待 {wait_time} 秒后重试TUS上传会话创建 (指数退避)...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"TUS上传会话创建失败，已重试3次，最后错误: {e}")

        # 所有重试都失败
        error_msg = f"TUS上传会话创建失败，已重试3次。最后错误: {str(last_error)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from last_error

    async def _upload_tus_chunks(self, upload_id: str, file_path: Path) -> None:
        """分块上传文件数据"""
        chunk_size = 1024 * 1024  # 1MB chunks
        offset = 0
        file_size = file_path.stat().st_size

        logger.info(f"开始分块上传: 文件大小 {file_size} bytes, 块大小 {chunk_size} bytes")

        try:
            with open(file_path, 'rb') as f:
                async with aiohttp.ClientSession() as session:
                    while offset < file_size:
                        # 定位到offset位置
                        f.seek(offset)

                        # 读取数据块
                        chunk = f.read(chunk_size)
                        if not chunk:
                            logger.warning(f"读取数据块为空，offset={offset}")
                            break

                        # 上传数据块
                        headers = {
                            'Tus-Resumable': '1.0.0',
                            'Upload-Offset': str(offset),
                            'Content-Type': 'application/offset+octet-stream'
                        }

                        # 添加认证头 - 支持从数据库配置读取
                        if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
                            headers['X-API-Key'] = settings.asr_api_key

                        # 添加ngrok绕过头
                        headers['ngrok-skip-browser-warning'] = 'true'

                        url = f"{self.tus_url}/files/{upload_id}"
                        logger.info(f"上传数据块: offset={offset}, size={len(chunk)}, 进度 {offset/file_size*100:.1f}%")

                        # 为每个数据块添加重试机制
                        chunk_upload_success = False
                        last_chunk_error = None

                        for chunk_attempt in range(3):  # 最多重试3次
                            try:
                                logger.info(f"上传数据块尝试 {chunk_attempt + 1}/3: offset={offset}, size={len(chunk)}")

                                async with session.patch(url, data=chunk, headers=headers) as response:
                                    logger.info(f"TUS块上传响应状态码: {response.status}")

                                    if response.status not in [200, 204]:  # TUS块上传应该返回200或204
                                        error_text = await response.text()
                                        logger.error(f"TUS块上传失败，状态码: {response.status}, 响应: {error_text}")
                                        # HTTP错误不重试，直接失败
                                        raise RuntimeError(f"TUS块上传失败，状态码: {response.status}, 响应: {error_text}")

                                    # 验证offset
                                    new_offset = int(response.headers.get('Upload-Offset', offset + len(chunk)))
                                    if new_offset != offset + len(chunk):
                                        raise ValueError(f"Offset不匹配: 期望 {offset + len(chunk)}, 实际 {new_offset}")

                                    offset = new_offset
                                    chunk_upload_success = True
                                    logger.info(f"✅ 数据块上传成功，当前进度 {offset/file_size*100:.1f}%")
                                    break  # 成功则跳出重试循环

                            except aiohttp.ClientError as e:
                                last_chunk_error = e
                                logger.warning(f"数据块网络错误 (尝试 {chunk_attempt + 1}/3): {e}")
                                if chunk_attempt < 2:  # 还有重试次数
                                    # 使用指数退避算法，基础等待时间为1秒，最大等待时间为30秒
                                    wait_time = min(1 * (2 ** chunk_attempt), 30)
                                    logger.info(f"等待 {wait_time} 秒后重试数据块上传 (指数退避)...")
                                    await asyncio.sleep(wait_time)
                                else:
                                    logger.error(f"数据块上传失败，已重试3次，最后错误: {e}")

                            except Exception as e:
                                last_chunk_error = e
                                logger.error(f"数据块上传未知错误 (尝试 {chunk_attempt + 1}/3): {e}")
                                # 非网络异常不重试，直接失败
                                raise RuntimeError(f"数据块上传失败: {str(e)}") from e

                        # 检查数据块是否上传成功
                        if not chunk_upload_success:
                            error_msg = "数据块上传失败，已达到最大重试次数"
                            if last_chunk_error:
                                error_msg = f"数据块上传失败，已达到最大重试次数。最后错误: {str(last_chunk_error)}"
                            logger.error(error_msg)
                            raise RuntimeError(error_msg) from last_chunk_error

            logger.info(f"TUS分块上传完成: 最终offset={offset}")
        except Exception as e:
            logger.error(f"分块上传失败: {e}", exc_info=True)
            raise RuntimeError(f"分块上传失败: {str(e)}") from e

    async def _wait_for_tus_results(self, task_id: str) -> str:
        """等待TUS ASR处理结果"""
        logger.info(f"开始等待TUS结果，任务ID: {task_id}")

        start_time = time.time()
        # 设置一个安全的超时缓冲区，确保在Celery超时之前完成
        safe_timeout = min(self.timeout_seconds, 1700)  # 留出100秒的缓冲时间

        try:
            if self._use_standalone_callback:
                # 独立回调服务器模式
                logger.info(f"使用独立回调服务器模式等待任务 {task_id} (超时: {safe_timeout}s)")

                # 向独立回调服务器注册任务
                if self.callback_manager.register_task(task_id):
                    logger.info(f"任务 {task_id} 已向独立回调服务器注册")

                    # 等待回调结果
                    result_data = await self.callback_manager.wait_for_result(task_id, safe_timeout)

                    if result_data and isinstance(result_data, dict):
                        logger.info(f"任务 {task_id} 结果已获取: {result_data}")

                        if result_data.get('status') == 'completed':
                            result_task_id = result_data.get('task_id')
                            srt_url = result_data.get('srt_url', f"{self.api_url}/api/v1/tasks/{result_task_id}/download")
                            logger.info(f"准备下载SRT内容，URL: {srt_url}")
                            # 如果srt_url是相对路径（不以http开头），转换为完整URL
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                                logger.info(f"转换后的SRT URL: {srt_url}")
                            srt_content = await self._download_srt_content(srt_url)
                            logger.info(f"SRT内容下载完成，长度: {len(srt_content) if srt_content else 0}")
                            return srt_content
                    else:
                        logger.error(f"任务 {task_id} 未收到有效结果")
                        raise RuntimeError(f"任务 {task_id} 未收到有效结果")
                else:
                    logger.error(f"任务 {task_id} 注册失败")
                    raise RuntimeError(f"任务 {task_id} 注册失败")

            elif self._use_global_callback:
                # 全局模式：使用全局回调管理器
                logger.info(f"使用全局回调模式等待任务 {task_id} (超时: {safe_timeout}s)")
                logger.info(f"全局管理器统计: {self.callback_manager.stats}")

                # 向全局管理器注册任务
                callback_future = self.callback_manager.register_task(task_id)

                logger.info(f"任务 {task_id} 已向全局管理器注册")

                # 等待回调结果
                try:
                    result = await asyncio.wait_for(callback_future, timeout=safe_timeout)
                    logger.info(f"任务 {task_id} 的回调Future已完成")
                    logger.info(f"回调结果: {result}")

                    # 处理完成结果
                    if isinstance(result, dict) and result.get('status') == 'completed':
                        task_id = result.get('task_id')
                        srt_url = result.get('srt_url', f"{self.api_url}/api/v1/tasks/{task_id}/download")
                        logger.info(f"准备下载SRT内容，URL: {srt_url}")
                        # 如果srt_url是相对路径（不以http开头），转换为完整URL
                        if srt_url and not srt_url.startswith('http'):
                            srt_url = f"{self.api_url}{srt_url}"
                            logger.info(f"转换后的SRT URL: {srt_url}")
                        srt_content = await self._download_srt_content(srt_url)
                        logger.info(f"SRT内容下载完成，长度: {len(srt_content) if srt_content else 0}")
                        return srt_content
                    else:
                        logger.info(f"返回非完成状态的结果: {result}")
                        return result

                except asyncio.TimeoutError:
                    elapsed_time = time.time() - start_time
                    logger.warning(f"任务 {task_id} 等待超时（{safe_timeout}s），已等待 {elapsed_time:.1f} 秒")

                    # 延迟清理任务，给回调留出到达时间
                    logger.info(f"延迟清理任务 {task_id}，等待可能的延迟回调...")
                    await asyncio.sleep(5.0)  # 等待5秒给回调时间到达

                    # 再次检查是否有缓存结果（处理竞态条件）
                    cached_result = self.callback_manager.get_cached_result(task_id)
                    if cached_result:
                        logger.info(f"✅ 从缓存获取到任务 {task_id} 的结果")

                        # 处理缓存的完成结果
                        if isinstance(cached_result, dict) and cached_result.get('status') == 'completed':
                            cached_task_id = cached_result.get('task_id')
                            srt_url = cached_result.get('srt_url', f"{self.api_url}/api/v1/tasks/{cached_task_id}/download")
                            logger.info(f"准备下载SRT内容（缓存），URL: {srt_url}")
                            # 如果srt_url是相对路径（不以http开头），转换为完整URL
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                                logger.info(f"转换后的SRT URL（缓存）: {srt_url}")
                            srt_content = await self._download_srt_content(srt_url)
                            logger.info(f"SRT内容下载完成（缓存），长度: {len(srt_content) if srt_content else 0}")
                            return srt_content
                        else:
                            logger.info(f"返回缓存的非完成状态结果: {cached_result}")
                            return cached_result
                    else:
                        logger.warning(f"⚠️ 任务 {task_id} 超时且无缓存结果，但继续等待一段时间...")
                        # 再等待30秒，处理ASR服务延迟的情况
                        await asyncio.sleep(30.0)

                        # 最后一次检查缓存
                        final_cached_result = self.callback_manager.get_cached_result(task_id)
                        if final_cached_result:
                            logger.info(f"✅ 延迟检查成功，从缓存获取到任务 {task_id} 的结果")
                            if isinstance(final_cached_result, dict) and final_cached_result.get('status') == 'completed':
                                cached_task_id = final_cached_result.get('task_id')
                                srt_url = final_cached_result.get('srt_url', f"{self.api_url}/api/v1/tasks/{cached_task_id}/download")
                                if srt_url and not srt_url.startswith('http'):
                                    srt_url = f"{self.api_url}{srt_url}"
                                srt_content = await self._download_srt_content(srt_url)
                                return srt_content
                            else:
                                return final_cached_result
                        else:
                            logger.error(f"❌ 任务 {task_id} 最终超时且无缓存结果")
                            # 只有在最终超时后才清理任务
                            self.callback_manager.cleanup_task(task_id)
                            raise TimeoutError(f"任务 {task_id} 处理超时（{safe_timeout}s）且无缓存结果")

                except asyncio.CancelledError:
                    elapsed_time = time.time() - start_time
                    logger.warning(f"全局回调取消，回退到轮询任务 {task_id} (已等待 {elapsed_time:.1f} 秒)")
                    # 不要立即清理任务，让后续回调能够被缓存
                    logger.info(f"任务 {task_id} 已取消，但保留在注册表中以便接收延迟回调")

            else:
                # 传统模式：使用本地回调服务器
                logger.info(f"使用传统模式等待任务 {task_id} (超时: {safe_timeout}s)")
                callback_future = asyncio.Future()
                self.completed_tasks[task_id] = callback_future

                logger.info(f"任务已注册到本地完成任务列表，当前任务键: {list(self.completed_tasks.keys())}")

                # 等待回调或超时
                check_interval = 1.0  # 每秒检查一次
                waited_time = 0

                while waited_time < safe_timeout:
                    # 检查是否被中断
                    if not self.__class__._callback_running:
                        raise KeyboardInterrupt("用户请求关闭")

                    # 检查回调是否完成
                    if callback_future.done():
                        logger.info(f"任务 {task_id} 的回调Future已完成")
                        result = callback_future.result()
                        logger.info(f"回调结果: {result}")
                        # 如果结果是带有完成信息的字典，下载SRT内容
                        if isinstance(result, dict) and result.get('status') == 'completed':
                            task_id = result.get('task_id')
                            srt_url = result.get('srt_url', f"{self.api_url}/api/v1/tasks/{task_id}/download")
                            logger.info(f"准备下载SRT内容，URL: {srt_url}")
                            # 如果srt_url是相对路径（不以http开头），转换为完整URL
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                                logger.info(f"转换后的SRT URL: {srt_url}")
                            srt_content = await self._download_srt_content(srt_url)
                            logger.info(f"SRT内容下载完成，长度: {len(srt_content) if srt_content else 0}")
                            return srt_content
                        else:
                            logger.info(f"返回非完成状态的结果: {result}")
                            return result

                    await asyncio.sleep(check_interval)
                    waited_time += check_interval

                # 超时处理
                elapsed_time = time.time() - start_time
                logger.warning(f"本地回调超时，回退到轮询任务 {task_id} (已等待 {elapsed_time:.1f} 秒)")

            # 回退到轮询（两种模式通用）
            elapsed_time = time.time() - start_time
            logger.warning(f"回退到轮询任务 {task_id} (已等待 {elapsed_time:.1f} 秒)")

            while time.time() - start_time < safe_timeout:
                # 检查全局模式是否被中断
                if self._use_global_callback and not self.callback_manager._server_running:
                    raise KeyboardInterrupt("全局回调服务器已关闭")
                # 检查传统模式是否被中断
                if not self._use_global_callback and not self.__class__._callback_running:
                    raise KeyboardInterrupt("本地回调服务器已关闭")

                try:
                    status = await self._get_task_status(task_id)

                    if status['status'] == 'completed':
                        srt_url = f"{self.api_url}/api/v1/tasks/{task_id}/download"
                        srt_content = await self._download_srt_content(srt_url)
                        return srt_content
                    elif status['status'] == 'failed':
                        error_msg = status.get('error_message', '任务失败')
                        raise RuntimeError(f"任务失败: {error_msg}")

                    logger.info(f"任务状态: {status['status']}, 等待中...")
                    await asyncio.sleep(5)

                except Exception as e:
                    logger.error(f"轮询任务状态出错: {e}")
                    await asyncio.sleep(5)

            raise TimeoutError(f"等待任务 {task_id} 完成超时")

        except asyncio.TimeoutError:
            elapsed_time = time.time() - start_time
            logger.warning(f"TUS等待超时: 已等待 {elapsed_time:.1f} 秒，超时设置 {safe_timeout} 秒")
            raise TimeoutError(f"TUS任务等待超时: {task_id}，已等待 {elapsed_time:.1f} 秒")

        finally:
            # 清理任务
            if self._use_global_callback:
                # 全局模式：清理全局管理器中的任务
                self.callback_manager.cleanup_task(task_id)
            else:
                # 传统模式：清理本地任务
                if task_id in self.completed_tasks:
                    del self.completed_tasks[task_id]

    async def _fallback_to_standard_asr(
        self,
        audio_file_path: str,
        metadata: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """回退到标准ASR处理"""
        logger.info("🔄 回退到标准ASR处理")

        try:
            # 使用标准ASR处理
            from app.services.audio_processor import AudioProcessor
            audio_processor = AudioProcessor()

            # 直接处理音频文件
            srt_content = await audio_processor.generate_srt_from_audio(
                audio_file_path,
                {
                    'language': metadata.get('language', 'auto'),
                    'model': metadata.get('model', 'whisper'),
                    'video_id': metadata.get('video_id', 'unknown'),
                    'project_id': metadata.get('project_id', 1),
                    'user_id': metadata.get('user_id', 1)
                }
            )

            logger.info("✅ 标准ASR处理完成")

            # 上传SRT内容到MinIO
            srt_url = None
            if srt_content:
                user_id = metadata.get('user_id', 1)
                project_id = metadata.get('project_id', 1)
                video_id = metadata.get('video_id', 'unknown')

                srt_filename = f"{video_id}.srt"
                srt_object_name = f"users/{user_id}/projects/{project_id}/subtitles/{srt_filename}"

                try:
                    tmp_srt_path = None
                    try:
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as tmp_srt_file:
                            tmp_srt_file.write(srt_content)
                            tmp_srt_path = tmp_srt_file.name

                        from app.services.minio_client import minio_service
                        srt_url = await minio_service.upload_file(
                            tmp_srt_path,
                            srt_object_name,
                            "text/srt"
                        )

                        if tmp_srt_path:
                            import os
                            if os.path.exists(tmp_srt_path):
                                os.unlink(tmp_srt_path)
                    except Exception as upload_error:
                        logger.error(f"SRT文件上传失败: {upload_error}")
                        if tmp_srt_path:
                            import os
                            if os.path.exists(tmp_srt_path):
                                os.unlink(tmp_srt_path)
                        raise

                except Exception as e:
                    logger.error(f"上传SRT到MinIO失败: {e}")

            return {
                'success': True,
                'strategy': 'standard',
                'task_id': None,
                'srt_content': srt_content,
                'srt_url': srt_url,
                'minio_path': srt_url,
                'object_name': srt_object_name if 'srt_object_name' in locals() else None,
                'file_path': audio_file_path,
                'metadata': metadata,
                'processing_time': time.time() - start_time,
                'file_size': audio_path.stat().st_size if 'audio_path' in locals() else 0,
                'fallback_reason': 'redis_unavailable'
            }

        except Exception as e:
            logger.error(f"标准ASR处理失败: {e}")
            raise RuntimeError(f"TUS和标准ASR处理都失败: {str(e)}") from e

    async def _poll_tus_results(self, task_id: str) -> str:
        """轮询TUS任务结果"""
        start_time = time.time()
        # 设置一个安全的超时缓冲区，确保在Celery超时之前完成
        safe_timeout = min(self.timeout_seconds, 1700)  # 留出100秒的缓冲时间

        while time.time() - start_time < safe_timeout:
            try:
                status = await self._get_task_status(task_id)

                if status['status'] == 'completed':
                    srt_url = f"{self.api_url}/api/v1/tasks/{task_id}/download"
                    return await self._download_srt_content(srt_url)
                elif status['status'] == 'failed':
                    error_msg = status.get('error_message', '任务失败')
                    raise RuntimeError(f"TUS任务失败: {error_msg}")

                logger.info(f"任务状态: {status['status']}, 等待中...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"轮询任务状态失败: {e}")
                await asyncio.sleep(5)

        elapsed_time = time.time() - start_time
        logger.warning(f"TUS轮询超时: 已等待 {elapsed_time:.1f} 秒，超时设置 {safe_timeout} 秒")
        raise TimeoutError(f"TUS任务轮询超时: {task_id}，已等待 {elapsed_time:.1f} 秒")

    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            # 创建会话并添加认证头
                headers = {}
                # 添加认证头 - 支持从数据库配置读取
                if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
                    headers['X-API-Key'] = settings.asr_api_key

                # 添加ngrok绕过头
                headers['ngrok-skip-browser-warning'] = 'true'

                async with aiohttp.ClientSession() as session:
                    url = f"{self.api_url}/api/v1/asr-tasks/{task_id}/status"
                    logger.info(f"轮询任务状态: {url}")

                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        logger.info(f"任务状态API响应状态码: {response.status}")
                        if response.status == 200:
                            result = await response.json()
                            logger.info(f"任务状态响应: {json.dumps(result, indent=2)}")
                            return result
                        else:
                            error_text = await response.text()
                            logger.warning(f"状态API返回状态码: {response.status}, 响应: {error_text}")
                            return {"status": "unknown"}

        except Exception as e:
            logger.error(f"获取任务状态失败: {e}", exc_info=True)
            return {"status": "unknown"}

    async def _download_srt_content(self, srt_url: str) -> str:
        """下载SRT内容"""
        try:
            logger.info(f"下载SRT内容: {srt_url}")

            # 创建会话并添加认证头
            headers = {}
            # 添加认证头 - 支持从数据库配置读取
            if hasattr(settings, 'asr_api_key') and settings.asr_api_key:
                headers['X-API-Key'] = settings.asr_api_key

            # 添加ngrok绕过头
            headers['ngrok-skip-browser-warning'] = 'true'

            async with aiohttp.ClientSession() as session:
                async with session.get(srt_url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    logger.info(f"SRT下载响应状态码: {response.status}")

                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"SRT下载失败，状态码: {response.status}, 响应: {error_text}")
                        raise RuntimeError(f"SRT下载失败，状态码: {response.status}, 响应: {error_text}")

                    # 尝试解析JSON响应
                    content_type = response.headers.get('Content-Type', '').lower()
                    logger.info(f"响应内容类型: {content_type}")

                    try:
                        if 'application/json' in content_type:
                            result = await response.json()
                            # logger.info(f"JSON响应: {json.dumps(result, indent=2)}")
                            if result.get("code") == 0 and result.get("data"):
                                srt_content = result["data"]
                                logger.info(f"下载SRT内容成功 (JSON格式, {len(srt_content)} 字符)")
                                return srt_content
                            else:
                                raise ValueError(f"无效的JSON响应: {result}")
                        else:
                            # 如果不是JSON，尝试纯文本
                            srt_content = await response.text()
                            logger.info(f"下载SRT内容成功 (纯文本格式, {len(srt_content)} 字符)")
                            return srt_content
                    except aiohttp.ContentTypeError as e:
                        # 如果Content-Type解析失败，尝试纯文本
                        logger.warning(f"Content-Type解析失败: {e}，尝试纯文本")
                        srt_content = await response.text()
                        logger.info(f"下载SRT内容成功 (纯文本格式, {len(srt_content)} 字符)")
                        return srt_content

        except Exception as e:
            logger.error(f"下载SRT内容失败: {e}", exc_info=True)
            raise RuntimeError(f"下载SRT内容失败: {str(e)}") from e

    def _generate_callback_url(self) -> Optional[str]:
        """生成回调URL，使用host上的公開IP地址"""
        try:
            # 从环境变量获取public IP，如果没有则使用当前主机IP
            public_ip = os.getenv('PUBLIC_IP')
            if public_ip:
                logger.info(f"使用PUBLIC_IP环境变量: {public_ip}")
                callback_url = f"http://{public_ip}:{self.callback_port}/callback"
            else:
                # 回退到自动检测
                if self.callback_host == "auto":
                    logger.info("PUBLIC_IP环境变量未设置，自动检测本地IP地址用于回调URL")
                    try:
                        import socket
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.connect(("8.8.8.8", 80))
                        local_ip = s.getsockname()[0]
                        s.close()
                        logger.info(f"检测到本地IP: {local_ip}")
                        callback_url = f"http://{local_ip}:{self.callback_port}/callback"
                    except Exception as e:
                        logger.warning(f"无法检测本地IP: {e}，使用localhost")
                        local_ip = "localhost"
                        callback_url = f"http://localhost:{self.callback_port}/callback"
                        logger.info(f"检测本地IP失败，使用默认: {callback_url}")
                else:
                    callback_url = f"http://{self.callback_host}:{self.callback_port}/callback"

            logger.info(f"生成的回调URL: {callback_url}")
            return callback_url
        except Exception as e:
            logger.error(f"生成回调URL失败: {e}", exc_info=True)
            return None

    def _start_callback_server(self):
        """启动回调服务器，自动处理端口冲突"""
        # 检查进程级别回调服务器是否已启动
        if self.__class__._callback_running and self.__class__._callback_server_thread and self.__class__._callback_server_thread.is_alive():
            logger.info(f"进程级别回调服务器已在运行 (PID: {self.process_id}, 端口: {self.callback_port})")
            return

        # 检查端口是否可用
        port_available = self._is_port_available(self.callback_port)
        if not port_available:
            logger.warning(f"端口 {self.callback_port} 不可用，尝试更换端口")
            self.callback_port = self._get_available_port()
            logger.info(f"更换到新端口: {self.callback_port}")

        # 设置进程级别服务器状态
        self.__class__._callback_running = True

        logger.info(f"准备启动回调服务器线程，端口: {self.callback_port}")
        self.__class__._callback_server_thread = threading.Thread(target=self._run_callback_server, name=f"CallbackServer-{self.callback_port}")
        self.__class__._callback_server_thread.daemon = True
        self.__class__._callback_server_thread.start()
        logger.info(f"回调服务器线程已启动，线程ID: {self.__class__._callback_server_thread.ident}")

        # 小睡一会儿确保线程开始执行
        time.sleep(0.5)

    def _run_callback_server(self):
        """运行回调服务器"""
        async def callback_handler(request):
            try:
                logger.info("回调处理程序被触发")
                logger.info(f"请求方法: {request.method}")
                logger.info(f"请求头: {dict(request.headers)}")
                logger.info(f"请求远程地址: {request.remote}")

                # 检查内容类型
                content_type = request.headers.get('Content-Type', '')
                logger.info(f"内容类型: {content_type}")

                payload = await request.json()
                logger.info(f"收到回调: {json.dumps(payload, indent=2)}")

                task_id = payload.get('task_id')
                logger.info(f"处理任务ID: {task_id}")
                logger.info(f"当前完成任务键: {list(self.completed_tasks.keys())}")

                if task_id in self.completed_tasks:
                    logger.info(f"在完成任务中找到任务 {task_id}")
                    future = self.completed_tasks[task_id]

                    if not future.done():
                        logger.info(f"任务 {task_id} 的Future未完成，正在处理...")
                        if payload.get('status') == 'completed':
                            logger.info(f"任务 {task_id} 完成，设置结果")
                            # 对于完成的任务，稍后下载SRT内容
                            # 标记完成并让轮询回退处理下载
                            # 确保srt_url是完整URL（如果不是相对URL）
                            srt_url = payload.get('srt_url')
                            logger.info(f"原始srt_url: {srt_url}")
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                                logger.info(f"修改后的srt_url: {srt_url}")
                            future.set_result({'status': 'completed', 'task_id': task_id, 'srt_url': srt_url})
                            logger.info(f"为任务 {task_id} 设置结果")
                        else:
                            error_msg = payload.get('error_message', '任务失败')
                            logger.info(f"任务 {task_id} 失败，错误: {error_msg}")
                            future.set_exception(RuntimeError(error_msg))
                            logger.info(f"为任务 {task_id} 设置异常")
                    else:
                        logger.info(f"任务 {task_id} 的Future已完成")

                    # 清理
                    logger.info(f"从完成任务中清理任务 {task_id}")
                    if task_id in self.completed_tasks:
                        del self.completed_tasks[task_id]
                    logger.info(f"任务 {task_id} 已从完成任务中移除")

                else:
                    logger.warning(f"在完成任务中未找到任务 {task_id}")
                    logger.info(f"可用任务ID: {list(self.completed_tasks.keys())}")

                logger.info("返回OK响应")
                return web.Response(text='OK')

            except Exception as e:
                logger.error(f"回调错误: {e}")
                logger.exception(e)  # 记录完整回溯
                return web.Response(status=500, text=str(e))

        async def create_app():
            app = web.Application()
            app.router.add_post('/callback', callback_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.callback_port)
            await site.start()

            logger.info(f"回调服务器启动于端口 {self.callback_port}")
            if self.callback_host == "auto":
                logger.info(f"回调URL (自动检测): http://[YOUR_LOCAL_IP]:{self.callback_port}/callback")
            else:
                logger.info(f"回调URL: http://{self.callback_host}:{self.callback_port}/callback")

            # 保持运行
            while self.__class__._callback_running:
                await asyncio.sleep(1)

        try:
            # 创建新的事件循环用于回调服务器
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(create_app())
        except Exception as e:
            logger.error(f"回调服务器失败: {e}")
            logger.exception(e)


# 全局实例
tus_asr_client = TusASRClient()