"""
Jianying（剪映）服务 - 基于CapCut服务的实现
"""
import asyncio
import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List

# 创建logger
logger = logging.getLogger(__name__)

class JianyingService:
    def __init__(self, api_base_url: str = None, api_key: str = None):
        if api_base_url is None or api_key is None:
            # 从数据库获取最新的配置
            try:
                from app.core.database import get_sync_db
                from app.services.system_config_service import SystemConfigService
                from app.core.config import settings

                with get_sync_db() as db:
                    db_configs = SystemConfigService.get_all_configs_sync(db)
                    if api_base_url is None:
                        api_base_url = db_configs.get("jianying_api_url", settings.jianying_api_url)
                    if api_key is None:
                        api_key = db_configs.get("jianying_api_key", settings.jianying_api_key)
            except Exception as e:
                # 如果无法从数据库获取配置，使用默认值
                from app.core.config import settings
                if api_base_url is None:
                    api_base_url = settings.jianying_api_url
                if api_key is None:
                    api_key = settings.jianying_api_key
                logger.warning(f"无法从数据库获取Jianying配置，使用默认配置: {e}")

        self.base_url = api_base_url
        self.api_key = api_key

    async def create_draft(self, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """创建草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试创建Jianying草稿 (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key
                    print(f"DEBUG: 发送请求到 {self.base_url}/create_draft")
                    print(f"DEBUG: 使用API Key: '{self.api_key}' (长度: {len(self.api_key)})")
                else:
                    print("DEBUG: 警告 - API Key 为空！")

                response = requests.post(
                    f"{self.base_url}/create_draft",
                    json={
                        "width": width,
                        "height": height
                    },
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()  # 检查HTTP错误
                result = response.json()
                logger.info("Jianying草稿创建成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"创建Jianying草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise Exception("创建Jianying草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"创建Jianying草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"创建Jianying草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"创建Jianying草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying草稿响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying草稿响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"创建Jianying草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"创建Jianying草稿失败: {str(e)}")

    async def add_effect(self, draft_id: str, effect_type: str, start: float, end: float,
                        track_name: str, params: List[float] = None, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加特效"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加Jianying特效 '{effect_type}' 到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")

                # 构造请求数据
                payload = {
                    "draft_id": draft_id,
                    "effect_type": effect_type,
                    "start": start,
                    "end": end,
                    "track_name": track_name,
                    "width": width,
                    "height": height
                }

                # 如果提供了params参数，则添加到请求数据中
                if params is not None:
                    payload["params"] = params

                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/add_effect",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"Jianying特效 '{effect_type}' 添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加Jianying特效超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加Jianying特效超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加Jianying特效连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加Jianying特效请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying特效请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying特效响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying特效响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加Jianying特效未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying特效失败: {str(e)}")

    async def add_audio(self, draft_id: str, audio_url: str, start: float, end: float,
                       track_name: str, volume: float = 0.5, target_start: float = 0,
                       width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加音频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加Jianying音频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/add_audio",
                    json={
                        "draft_id": draft_id,
                        "audio_url": audio_url,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "volume": volume,
                        "target_start": target_start,
                        "width": width,
                        "height": height
                    },
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Jianying音频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加Jianying音频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加Jianying音频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加Jianying音频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加Jianying音频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying音频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying音频响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying音频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加Jianying音频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying音频失败: {str(e)}")

    async def add_video(self, draft_id: str, video_url: str, start: float, end: float,
                       track_name: str, width: int = 1080, height: int = 1920,
                       target_start: float = 0, max_retries: int = 3) -> Dict[str, Any]:
        """添加视频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加Jianying视频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/add_video",
                    json={
                        "draft_id": draft_id,
                        "video_url": video_url,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "width": width,
                        "height": height,
                        "target_start": target_start
                    },
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Jianying视频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加Jianying视频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加Jianying视频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加Jianying视频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加Jianying视频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying视频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying视频响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying视频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加Jianying视频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying视频失败: {str(e)}")

    async def add_text(self, draft_id: str, text: str, start: float, end: float,
                      font: str = "默认字体", font_color: str = "#ffde00", font_size: float = 12.0,
                      track_name: str = "text_track_1", transform_x: float = 0,
                      transform_y: float = 0.75, font_alpha: float = 1.0,
                      border_alpha: float = 1.0, border_color: str = "#000000",
                      border_width: float = 15.0, width: int = 1080, height: int = 1920,
                      intro_animation: str = None, intro_duration: float = 0.5,
                      outro_animation: str = None, outro_duration: float = 0.5,
                      max_retries: int = 3) -> Dict[str, Any]:
        """添加文本"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加Jianying文本到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                # 构建请求数据
                data = {
                    "draft_id": draft_id,
                    "text": text,
                    "start": start,
                    "end": end,
                    "font": font,
                    "font_color": font_color,
                    "font_size": font_size,
                    "track_name": track_name,
                    "transform_x": transform_x,
                    "transform_y": transform_y,
                    "font_alpha": font_alpha,
                    "border_alpha": border_alpha,
                    "border_color": border_color,
                    "border_width": border_width,
                    "width": width,
                    "height": height
                }

                # 添加可选的动画参数
                if intro_animation is not None:
                    data["intro_animation"] = intro_animation
                if intro_duration is not None:
                    data["intro_duration"] = intro_duration
                if outro_animation is not None:
                    data["outro_animation"] = outro_animation
                if outro_duration is not None:
                    data["outro_duration"] = outro_duration

                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/add_text",
                    json=data,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Jianying文本添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加Jianying文本超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加Jianying文本超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加Jianying文本连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加Jianying文本请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying文本请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying文本响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying文本响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加Jianying文本未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying文本失败: {str(e)}")

    async def add_subtitle(self, draft_id: str, srt_path: str, time_offset: float = 0.0,
                          font: str = "默认字体", font_size: float = 8.0, font_color: str = "#ffde00",
                          bold: bool = False, italic: bool = False, underline: bool = False,
                          vertical: bool = False, alpha: float = 1.0,
                          border_alpha: float = 1.0, border_color: str = "#000000",
                          border_width: float = 15.0,
                          background_color: str = "#000000", background_style: int = 0, background_alpha: float = 0.0,
                          transform_x: float = 0.0, transform_y: float = -0.8,
                          scale_x: float = 1.0, scale_y: float = 1.0, rotation: float = 0.0,
                          track_name: str = "subtitle", width: int = 1080, height: int = 1920,
                          max_retries: int = 3) -> Dict[str, Any]:
        """添加字幕"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加Jianying字幕到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/add_subtitle",
                    json={
                        "draft_id": draft_id,
                        "srt": srt_path,
                        "time_offset": time_offset,
                        "font": font,
                        "font_size": font_size,
                        "font_color": font_color,
                        "bold": bold,
                        "italic": italic,
                        "underline": underline,
                        "vertical": vertical,
                        "alpha": alpha,
                        "border_alpha": border_alpha,
                        "border_color": border_color,
                        "border_width": border_width,
                        "background_color": background_color,
                        "background_style": background_style,
                        "background_alpha": background_alpha,
                        "transform_x": transform_x,
                        "transform_y": transform_y,
                        "scale_x": scale_x,
                        "scale_y": scale_y,
                        "rotation": rotation,
                        "track_name": track_name,
                        "width": width,
                        "height": height
                    },
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Jianying字幕添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加Jianying字幕超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加Jianying字幕超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加Jianying字幕连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加Jianying字幕请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying字幕请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying字幕响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying字幕响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加Jianying字幕未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加Jianying字幕失败: {str(e)}")

    async def query_draft_status(self, task_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """查询草稿状态"""
        for attempt in range(max_retries):
            try:
                logger.info(f"查询Jianying草稿状态 - TaskID: {task_id} (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/query_draft_status",
                    json={"task_id": task_id},
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"Jianying草稿状态查询成功: {result}")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"查询Jianying草稿状态超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("查询Jianying草稿状态超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"查询Jianying草稿状态连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"查询Jianying草稿状态请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"查询Jianying草稿状态失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying草稿状态响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying草稿状态响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"查询Jianying草稿状态未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"查询Jianying草稿状态失败: {str(e)}")

    async def save_draft_and_wait_result(self, draft_id: str, draft_folder: str, timeout: int = 300, poll_interval: int = 3) -> Dict[str, Any]:
        """异步保存草稿并等待最终结果"""
        logger.info(f"开始异步保存Jianying草稿 {draft_id} 并等待结果")

        # 1. 提交保存任务
        save_result = await self.save_draft(draft_id, draft_folder)

        if not save_result.get("success"):
            raise Exception(f"提交Jianying保存任务失败: {save_result.get('error', '未知错误')}")

        # 检查是否已经包含draft_url（向后兼容）
        if "output" in save_result and "draft_url" in save_result["output"] and save_result["output"]["draft_url"]:
            logger.info(f"Jianying草稿保存成功（同步模式）: {save_result['output']['draft_url']}")
            return {
                "success": True,
                "draft_url": save_result["output"]["draft_url"],
                "task_id": None
            }

        # 2. 异步模式 - 提取task_id并轮询
        task_info = save_result.get("output", {})
        task_id = task_info.get("task_id")

        if not task_id:
            raise Exception(f"Jianying保存任务返回异步响应但缺少task_id: {save_result}")

        logger.info(f"Jianying任务已提交到队列，开始轮询 - TaskID: {task_id}")

        # 3. 轮询查询状态
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status_result = await self.query_draft_status(task_id)

                if not status_result.get("success"):
                    logger.warning(f"查询Jianying状态失败，继续轮询: {status_result.get('error', '未知错误')}")
                    time.sleep(poll_interval)
                    continue

                status_info = status_result.get("output", {})
                status = status_info.get("status")
                progress = status_info.get("progress", 0)
                message = status_info.get("message", "")

                logger.info(f"Jianying任务状态: {status}, 进度: {progress}%, 消息: {message}")

                # 4. 检查是否完成
                if status == "completed":
                    draft_url = status_info.get("draft_url")
                    if not draft_url:
                        raise Exception(f"Jianying任务完成但缺少draft_url: {status_result}")

                    logger.info(f"Jianying任务完成! Draft URL: {draft_url}")
                    return {
                        "success": True,
                        "draft_url": draft_url,
                        "task_id": task_id
                    }
                elif status == "failed":
                    error_msg = status_info.get("message", "Jianying任务失败")
                    raise Exception(f"Jianying任务失败: {error_msg}")

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"轮询Jianying任务过程中出错: {e}")
                time.sleep(poll_interval)

        raise Exception(f"Jianying任务超时 ({timeout}秒) - TaskID: {task_id}")

    async def save_draft(self, draft_id: str, draft_folder: str, max_retries: int = 3) -> Dict[str, Any]:
        """保存草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试保存Jianying草稿 {draft_id} 到文件夹 {draft_folder} (尝试 {attempt + 1}/{max_retries})")
                # 准备请求头
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["X-API-KEY"] = self.api_key

                response = requests.post(
                    f"{self.base_url}/save_draft",
                    json={
                        "draft_id": draft_id,
                        "draft_folder": draft_folder
                    },
                    headers=headers,
                    timeout=120
                )
                response.raise_for_status()
                result = response.json()
                logger.info("Jianying草稿保存成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"保存Jianying草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("保存Jianying草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"保存Jianying草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到Jianying服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"保存Jianying草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"保存Jianying草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析Jianying草稿保存响应JSON失败: {str(e)}")
                raise Exception(f"解析Jianying草稿保存响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"保存Jianying草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"保存Jianying草稿失败: {str(e)}")

# 全局实例
jianying_service = JianyingService()