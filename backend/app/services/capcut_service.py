"""
CapCut服务 - 独立于API模块以避免循环导入
"""
import asyncio
import requests
import json
import time
import logging
from typing import Dict, Any, Optional

# 创建logger
logger = logging.getLogger(__name__)

class CapCutService:
    def __init__(self, api_base_url: str = "http://192.168.8.107:9002"):
        self.base_url = api_base_url
    
    async def create_draft(self, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """创建草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试创建草稿 (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/create_draft",
                    json={
                        "width": width,
                        "height": height
                    },
                    timeout=30
                )
                response.raise_for_status()  # 检查HTTP错误
                result = response.json()
                logger.info("草稿创建成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"创建草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise Exception("创建草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"创建草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"创建草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"创建草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析草稿响应JSON失败: {str(e)}")
                raise Exception(f"解析草稿响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"创建草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"创建草稿失败: {str(e)}")
    
    async def add_effect(self, draft_id: str, effect_type: str, start: float, end: float, 
                        track_name: str, width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加特效"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加特效 '{effect_type}' 到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_effect",
                    json={
                        "draft_id": draft_id,
                        "effect_type": effect_type,
                        "start": start,
                        "end": end,
                        "track_name": track_name,
                        "width": width,
                        "height": height
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"特效 '{effect_type}' 添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加特效超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加特效超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加特效连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加特效请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加特效请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析特效响应JSON失败: {str(e)}")
                raise Exception(f"解析特效响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加特效未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加特效失败: {str(e)}")
    
    async def add_audio(self, draft_id: str, audio_url: str, start: float, end: float,
                       track_name: str, volume: float = 0.5, target_start: float = 0,
                       width: int = 1080, height: int = 1920, max_retries: int = 3) -> Dict[str, Any]:
        """添加音频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加音频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
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
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("音频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加音频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加音频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加音频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加音频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加音频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析音频响应JSON失败: {str(e)}")
                raise Exception(f"解析音频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加音频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加音频失败: {str(e)}")
    
    async def add_video(self, draft_id: str, video_url: str, start: float, end: float,
                       track_name: str, width: int = 1080, height: int = 1920,
                       target_start: float = 0, max_retries: int = 3) -> Dict[str, Any]:
        """添加视频"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加视频到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
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
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("视频添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加视频超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加视频超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加视频连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加视频请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加视频请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析视频响应JSON失败: {str(e)}")
                raise Exception(f"解析视频响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加视频未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加视频失败: {str(e)}")
    
    async def add_text(self, draft_id: str, text: str, start: float, end: float,
                      font: str = "挥墨体", font_color: str = "#ffde00", font_size: float = 12.0,
                      track_name: str = "text_track_1", transform_x: float = 0,
                      transform_y: float = 0.75, font_alpha: float = 1.0,
                      border_alpha: float = 1.0, border_color: str = "#000000",
                      border_width: float = 15.0, width: int = 1080, height: int = 1920,
                      max_retries: int = 3) -> Dict[str, Any]:
        """添加文本"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试添加文本到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/add_text",
                    json={
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
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                logger.info("文本添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加文本超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加文本超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加文本连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加文本请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加文本请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析文本响应JSON失败: {str(e)}")
                raise Exception(f"解析文本响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加文本未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加文本失败: {str(e)}")
    
    async def add_subtitle(self, draft_id: str, srt_path: str, time_offset: float = 0.0,
                          font: str = "挥墨体", font_size: float = 8.0, font_color: str = "#ffde00",
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
                logger.info(f"尝试添加字幕到草稿 {draft_id} (尝试 {attempt + 1}/{max_retries})")
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
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                logger.info("字幕添加成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"添加字幕超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("添加字幕超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"添加字幕连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"添加字幕请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加字幕请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析字幕响应JSON失败: {str(e)}")
                raise Exception(f"解析字幕响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"添加字幕未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"添加字幕失败: {str(e)}")
    
    async def save_draft(self, draft_id: str, draft_folder: str, max_retries: int = 3) -> Dict[str, Any]:
        """保存草稿"""
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试保存草稿 {draft_id} 到文件夹 {draft_folder} (尝试 {attempt + 1}/{max_retries})")
                response = requests.post(
                    f"{self.base_url}/save_draft",
                    json={
                        "draft_id": draft_id,
                        "draft_folder": draft_folder
                    },
                    timeout=120
                )
                response.raise_for_status()
                result = response.json()
                logger.info("草稿保存成功")
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"保存草稿超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception("保存草稿超时")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"保存草稿连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"无法连接到CapCut服务: {str(e)}")
            except requests.exceptions.RequestException as e:
                logger.error(f"保存草稿请求错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"保存草稿请求失败: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"解析草稿保存响应JSON失败: {str(e)}")
                raise Exception(f"解析草稿保存响应失败: {str(e)}")
            except Exception as e:
                logger.error(f"保存草稿未知错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise Exception(f"保存草稿失败: {str(e)}")

# 全局实例
capcut_service = CapCutService()