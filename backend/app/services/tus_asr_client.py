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
from pathlib import Path
from typing import Dict, Any, Optional
from aiohttp import web

from app.core.config import settings

logger = logging.getLogger(__name__)


class TusASRClient:
    """TUS ASR客户端，为FlowClip系统提供TUS协议支持"""

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
        self.callback_port = callback_port or settings.tus_callback_port
        self.callback_host = callback_host or settings.tus_callback_host
        self.max_retries = max_retries or settings.tus_max_retries
        self.timeout_seconds = timeout_seconds or settings.tus_timeout_seconds

        # 然后尝试从数据库动态更新配置
        self._load_config_from_database()

        # 内部状态
        self.completed_tasks = {}
        self.running = True
        self.callback_thread = None

        logger.info(f"TUS ASR客户端初始化完成:")
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

        logger.info(f"开始TUS ASR处理: {audio_file_path}")
        logger.info(f"文件大小: {audio_path.stat().st_size} bytes")

        # 启动回调服务器
        self._start_callback_server()
        time.sleep(0.5)  # 等待回调服务器启动

        try:
            # 执行TUS处理流程
            result = await self._execute_tus_pipeline(audio_file_path, metadata or {})
            return result

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
            raise RuntimeError(f"TUS ASR处理失败: {str(e)}") from e
        finally:
            self.running = False

    async def _execute_tus_pipeline(
        self,
        audio_file_path: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行完整的TUS处理流水线"""
        audio_path = Path(audio_file_path)
        start_time = time.time()  # 记录开始时间用于统计

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
        srt_content = await self._wait_for_tus_results(task_id)
        logger.info("✅ ASR处理完成")

        return {
            'success': True,
            'strategy': 'tus',
            'task_id': task_id,
            'srt_content': srt_content,
            'file_path': audio_file_path,
            'metadata': metadata,
            'processing_time': time.time() - start_time if 'start_time' in locals() else 0,
            'file_size': audio_path.stat().st_size if 'audio_path' in locals() else 0
        }

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
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/api/v1/asr-tasks",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if 'task_id' not in result or 'upload_url' not in result:
                                raise ValueError(f"无效的API响应: {result}")

                            # 保存任务ID供后续使用
                            self.current_task_id = result['task_id']
                            logger.info(f"TUS任务创建成功: {result['task_id']}")
                            return result
                        else:
                            error_text = await response.text()
                            raise RuntimeError(f"API请求失败，状态码: {response.status}, 响应: {error_text}")

            except Exception as e:
                last_error = e
                logger.warning(f"TUS任务创建失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    # 指数退避等待
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time} 秒后重试...")
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

        # 从upload_url提取upload_id
        upload_id = upload_url.split('/')[-1]

        # 创建TUS上传会话
        tus_upload_id = await self._create_tus_upload_session(upload_id, file_size, audio_path.name)

        # 分块上传文件数据
        await self._upload_tus_chunks(tus_upload_id, audio_path)

        logger.info(f"TUS上传完成: {audio_path.name}")

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

        async with aiohttp.ClientSession() as session:
            url = f"{self.tus_url}/files"
            logger.info(f"创建TUS上传会话: {url}")

            async with session.post(url, headers=headers) as response:
                response.raise_for_status()

                # 从Location头获取上传URL
                location = response.headers.get('Location', '')
                if not location:
                    raise ValueError("TUS响应中缺少Location头")

                # 提取实际的upload_id
                actual_upload_id = location.split('/')[-1]
                logger.info(f"TUS上传会话创建成功: {actual_upload_id}")

                return actual_upload_id

    async def _upload_tus_chunks(self, upload_id: str, file_path: Path) -> None:
        """分块上传文件数据"""
        chunk_size = 1024 * 1024  # 1MB chunks
        offset = 0

        with open(file_path, 'rb') as f:
            async with aiohttp.ClientSession() as session:
                while offset < file_path.stat().st_size:
                    # 定位到offset位置
                    f.seek(offset)

                    # 读取数据块
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    # 上传数据块
                    headers = {
                        'Tus-Resumable': '1.0.0',
                        'Upload-Offset': str(offset),
                        'Content-Type': 'application/offset+octet-stream'
                    }

                    url = f"{self.tus_url}/files/{upload_id}"
                    logger.debug(f"上传数据块: offset={offset}, size={len(chunk)}")

                    async with session.patch(url, data=chunk, headers=headers) as response:
                        response.raise_for_status()

                        # 验证offset
                        new_offset = int(response.headers['Upload-Offset'])
                        if new_offset != offset + len(chunk):
                            raise ValueError(f"Offset不匹配: 期望 {offset + len(chunk)}, 实际 {new_offset}")

                        offset = new_offset

        logger.info(f"TUS分块上传完成: 最终offset={offset}")

    async def _wait_for_tus_results(self, task_id: str) -> str:
        """等待TUS ASR处理结果"""
        callback_future = asyncio.Future()
        self.completed_tasks[task_id] = callback_future

        start_time = time.time()

        try:
            # 等待回调或超时
            while time.time() - start_time < self.timeout_seconds:
                if not self.running:
                    raise KeyboardInterrupt("用户请求停止")

                if callback_future.done():
                    result = callback_future.result()
                    if isinstance(result, dict) and result.get('status') == 'completed':
                        srt_url = result.get('srt_url')
                        if srt_url and not srt_url.startswith('http'):
                            srt_url = f"{self.api_url}{srt_url}"
                        return await self._download_srt_content(srt_url)
                    else:
                        return result

                await asyncio.sleep(1.0)

            # 超时后切换到轮询
            logger.warning("回调超时，切换到轮询模式")
            return await self._poll_tus_results(task_id)

        finally:
            # 清理任务
            if task_id in self.completed_tasks:
                del self.completed_tasks[task_id]

    async def _poll_tus_results(self, task_id: str) -> str:
        """轮询TUS任务结果"""
        start_time = time.time()

        while time.time() - start_time < self.timeout_seconds:
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

        raise TimeoutError(f"TUS任务超时: {task_id}")

    async def _get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/api/v1/asr-tasks/{task_id}/status"

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"状态API返回状态码: {response.status}")
                        return {"status": "unknown"}

        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return {"status": "unknown"}

    async def _download_srt_content(self, srt_url: str) -> str:
        """下载SRT内容"""
        try:
            logger.info(f"下载SRT内容: {srt_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(srt_url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response.raise_for_status()

                    # 尝试解析JSON响应
                    try:
                        result = await response.json()
                        if result.get("code") == 0 and result.get("data"):
                            srt_content = result["data"]
                            logger.info(f"下载SRT内容成功 (JSON格式, {len(srt_content)} 字符)")
                            return srt_content
                        else:
                            raise ValueError(f"无效的JSON响应: {result}")
                    except aiohttp.ContentTypeError:
                        # 如果不是JSON，尝试纯文本
                        srt_content = await response.text()
                        logger.info(f"下载SRT内容成功 (纯文本格式, {len(srt_content)} 字符)")
                        return srt_content

        except Exception as e:
            logger.error(f"下载SRT内容失败: {e}")
            raise

    def _generate_callback_url(self) -> Optional[str]:
        """生成回调URL"""
        if self.callback_host == "auto":
            # 自动检测本地IP
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                local_ip = "localhost"
            return f"http://{local_ip}:{self.callback_port}/callback"
        else:
            return f"http://{self.callback_host}:{self.callback_port}/callback"

    def _start_callback_server(self):
        """启动回调服务器"""
        if self.callback_thread and self.callback_thread.is_alive():
            logger.info("回调服务器已在运行")
            return

        self.callback_thread = threading.Thread(target=self._run_callback_server)
        self.callback_thread.daemon = True
        self.callback_thread.start()

    def _run_callback_server(self):
        """运行回调服务器"""
        async def callback_handler(request):
            try:
                payload = await request.json()
                logger.info(f"收到回调: {json.dumps(payload, indent=2)}")

                task_id = payload.get('task_id')
                if task_id in self.completed_tasks:
                    future = self.completed_tasks[task_id]

                    if not future.done():
                        if payload.get('status') == 'completed':
                            srt_url = payload.get('srt_url')
                            if srt_url and not srt_url.startswith('http'):
                                srt_url = f"{self.api_url}{srt_url}"
                            # 传递完整的回调负载，包含更多统计信息
                            future.set_result({
                                'status': 'completed',
                                'task_id': task_id,
                                'srt_url': srt_url,
                                'payload': payload  # 包含所有回调数据
                            })
                        else:
                            error_msg = payload.get('error_message', '任务失败')
                            future.set_exception(RuntimeError(error_msg))

                    # 清理任务
                    del self.completed_tasks[task_id]

                return web.Response(text='OK')

            except Exception as e:
                logger.error(f"回调处理失败: {e}")
                return web.Response(status=500, text=str(e))

        async def create_app():
            app = web.Application()
            app.router.add_post('/callback', callback_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', self.callback_port)
            await site.start()

            logger.info(f"回调服务器启动: 端口 {self.callback_port}")
            if self.callback_host == "auto":
                logger.info(f"回调URL (自动检测): http://[本地IP]:{self.callback_port}/callback")
            else:
                logger.info(f"回调URL: http://{self.callback_host}:{self.callback_port}/callback")

            # 保持运行
            while self.running:
                await asyncio.sleep(1)

        try:
            asyncio.run(create_app())
        except Exception as e:
            logger.error(f"回调服务器运行失败: {e}")


# 全局实例
tus_asr_client = TusASRClient()