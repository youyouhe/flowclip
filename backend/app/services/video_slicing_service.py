"""
视频切片服务 - 基于FFMPEG进行视频切割
"""
import os
import subprocess
import json
import asyncio
import tempfile
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from app.core.config import settings
from app.services.minio_client import minio_service

logger = logging.getLogger(__name__)

class VideoSlicingService:
    """视频切片服务类"""
    
    def __init__(self):
        self.temp_dir = settings.temp_dir or "/tmp"
        self.ffmpeg_path = "ffmpeg"  # 假设ffmpeg在PATH中
        self.ffprobe_path = "ffprobe"  # 假设ffprobe在PATH中
        
    async def slice_video(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cover_title: str,
        user_id: int,
        project_id: int,
        video_id: int
    ) -> Dict[str, Any]:
        """
        异步版本 - 视频切割
        """
        return await self._slice_video_impl(
            video_path, start_time, end_time, output_filename, 
            cover_title, user_id, project_id, video_id
        )
    
    def slice_video_sync(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cover_title: str,
        user_id: int,
        project_id: int,
        video_id: int
    ) -> Dict[str, Any]:
        """
        同步版本 - 视频切割，用于Celery任务
        """
        try:
            return self._slice_video_impl_sync(
                video_path, start_time, end_time, output_filename,
                cover_title, user_id, project_id, video_id
            )
        except Exception as e:
            logger.error(f"同步视频切片失败: {str(e)}")
            raise

    async def _slice_video_impl(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cover_title: str,
        user_id: int,
        project_id: int,
        video_id: int
    ) -> Dict[str, Any]:
        """
        切割视频片段的异步实现
        
        Args:
            video_path: 原视频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_filename: 输出文件名
            cover_title: 封面标题
            
        Returns:
            切割结果
        """
        try:
            # 计算持续时间
            duration = end_time - start_time
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file_path = os.path.join(temp_dir, output_filename)
                
                # 构建ffmpeg命令
                cmd = [
                    self.ffmpeg_path,
                    '-ss', str(start_time),  # 开始时间
                    '-i', video_path,  # 输入文件
                    '-t', str(duration),  # 持续时间
                    '-c', 'copy',  # 使用流拷贝，保持原质量
                    '-avoid_negative_ts', 'make_zero',  # 避免负时间戳
                    '-y',  # 覆盖输出文件
                    temp_file_path
                ]
                
                logger.info(f"执行FFMPEG命令: {' '.join(cmd)}")
                
                # 执行FFMPEG命令
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5分钟超时
                    )
                )
                
                if result.returncode != 0:
                    logger.error(f"FFMPEG执行失败: {result.stderr}")
                    raise Exception(f"视频切割失败: {result.stderr}")
                
                # 检查输出文件
                if not os.path.exists(temp_file_path):
                    raise Exception("切割后的文件不存在")
                
                # 获取实际的视频时长
                actual_duration = duration
                try:
                    cmd = [
                        self.ffprobe_path,
                        '-v', 'quiet',
                        '-print_format', 'json',
                        '-show_format',
                        temp_file_path
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        info = json.loads(result.stdout)
                        actual_duration = float(info.get('format', {}).get('duration', duration))
                except Exception as e:
                    logger.warning(f"获取实际视频时长失败，使用计算值: {str(e)}")
                
                # 获取文件信息
                file_size = os.path.getsize(temp_file_path)
                
                # 上传到MinIO
                minio_path = minio_service.generate_slice_object_name(user_id, project_id, video_id, output_filename)
                upload_result = await minio_service.upload_file(
                    temp_file_path,
                    minio_path,
                    content_type="video/mp4"
                )
                
                logger.info(f"视频切割成功: {output_filename}, 大小: {file_size} bytes, 理论时长: {duration}秒, 实际时长: {actual_duration}秒")
                
                return {
                    "success": True,
                    "filename": output_filename,
                    "file_path": minio_path,
                    "file_size": file_size,
                    "duration": actual_duration
                }
                
        except subprocess.TimeoutExpired:
            logger.error("视频切割超时")
            raise Exception("视频切割超时")
        except Exception as e:
            logger.error(f"视频切割失败: {str(e)}")
            raise Exception(f"视频切割失败: {str(e)}")

    def _slice_video_impl_sync(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_filename: str,
        cover_title: str,
        user_id: int,
        project_id: int,
        video_id: int
    ) -> Dict[str, Any]:
        """
        同步版本的视频切割实现
        
        Args:
            video_path: 原视频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_filename: 输出文件名
            cover_title: 封面标题
            
        Returns:
            切割结果
        """
        try:
            # 计算持续时间
            duration = end_time - start_time
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file_path = os.path.join(temp_dir, output_filename)
                
                # 构建ffmpeg命令
                cmd = [
                    self.ffmpeg_path,
                    '-ss', str(start_time),  # 开始时间
                    '-i', video_path,  # 输入文件
                    '-t', str(duration),  # 持续时间
                    '-c', 'copy',  # 使用流拷贝，保持原质量
                    '-avoid_negative_ts', 'make_zero',  # 避免负时间戳
                    '-y',  # 覆盖输出文件
                    temp_file_path
                ]
                
                logger.info(f"执行FFMPEG命令 (同步): {' '.join(cmd)}")
                
                # 同步执行FFMPEG命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode != 0:
                    logger.error(f"FFMPEG执行失败: {result.stderr}")
                    raise Exception(f"视频切割失败: {result.stderr}")
                
                # 检查输出文件
                if not os.path.exists(temp_file_path):
                    raise Exception("切割后的文件不存在")
                
                # 获取实际的视频时长
                actual_duration = duration
                try:
                    cmd = [
                        self.ffprobe_path,
                        '-v', 'quiet',
                        '-print_format', 'json',
                        '-show_format',
                        temp_file_path
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        info = json.loads(result.stdout)
                        actual_duration = float(info.get('format', {}).get('duration', duration))
                except Exception as e:
                    logger.warning(f"获取实际视频时长失败，使用计算值: {str(e)}")
                
                # 获取文件信息
                file_size = os.path.getsize(temp_file_path)
                
                # 上传到MinIO (使用同步版本)
                minio_path = minio_service.generate_slice_object_name(user_id, project_id, video_id, output_filename)
                upload_result = minio_service.upload_file_sync(
                    temp_file_path,
                    minio_path,
                    content_type="video/mp4"
                )
                
                logger.info(f"视频切割成功 (同步): {output_filename}, 大小: {file_size} bytes, 理论时长: {duration}秒, 实际时长: {actual_duration}秒")
                
                return {
                    "success": True,
                    "filename": output_filename,
                    "file_path": minio_path,
                    "file_size": file_size,
                    "duration": actual_duration
                }
                
        except subprocess.TimeoutExpired:
            logger.error("视频切割超时")
            raise Exception("视频切割超时")
        except Exception as e:
            logger.error(f"视频切割失败: {str(e)}")
            raise Exception(f"视频切割失败: {str(e)}")
    
    async def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息
        """
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            )
            
            if result.returncode != 0:
                raise Exception(f"获取视频信息失败: {result.stderr}")
            
            info = json.loads(result.stdout)
            
            # 提取关键信息
            duration = float(info.get('format', {}).get('duration', 0))
            file_size = int(info.get('format', {}).get('size', 0))
            
            # 获取视频流信息
            video_stream = None
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            return {
                "duration": duration,
                "file_size": file_size,
                "width": video_stream.get('width') if video_stream else None,
                "height": video_stream.get('height') if video_stream else None,
                "fps": eval(video_stream.get('r_frame_rate', '30/1')) if video_stream else 30
            }
            
        except Exception as e:
            logger.error(f"获取视频信息失败: {str(e)}")
            raise Exception(f"获取视频信息失败: {str(e)}")
    
    async def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        time_offset: float = 1.0
    ) -> str:
        """
        生成视频缩略图
        
        Args:
            video_path: 视频文件路径
            output_path: 输出路径
            time_offset: 时间偏移（秒）
            
        Returns:
            缩略图路径
        """
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-ss', str(time_offset),
                '-vframes', '1',
                '-s', '320x240',
                '-y',
                output_path
            ]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            )
            
            if result.returncode != 0:
                raise Exception(f"生成缩略图失败: {result.stderr}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"生成缩略图失败: {str(e)}")
            raise Exception(f"生成缩略图失败: {str(e)}")
    
    async def validate_slice_timing(
        self,
        video_duration: float,
        slices: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        验证切片时间是否有效
        
        Args:
            video_duration: 视频总时长
            slices: 切片列表
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        for i, slice_item in enumerate(slices):
            start_time = self._parse_time_str(slice_item.get('start', '00:00:00,000'))
            end_time = self._parse_time_str(slice_item.get('end', '00:00:00,000'))
            
            # 检查时间格式
            if start_time is None or end_time is None:
                errors.append(f"切片 {i+1}: 时间格式错误")
                continue
            
            # 检查时间范围
            if start_time < 0 or end_time > video_duration:
                errors.append(f"切片 {i+1}: 时间超出视频范围")
                continue
            
            # 检查开始时间是否小于结束时间
            if start_time >= end_time:
                errors.append(f"切片 {i+1}: 开始时间必须小于结束时间")
                continue
            
            # 检查持续时间（至少5秒）
            if end_time - start_time < 5:
                errors.append(f"切片 {i+1}: 持续时间太短，至少需要5秒")
                continue
            
            # 检查子切片
            for j, sub_slice in enumerate(slice_item.get('subtitles', [])):
                sub_start = self._parse_time_str(sub_slice.get('start', '00:00:00,000'))
                sub_end = self._parse_time_str(sub_slice.get('end', '00:00:00,000'))
                
                if sub_start is None or sub_end is None:
                    errors.append(f"切片 {i+1} 子切片 {j+1}: 时间格式错误")
                    continue
                
                if sub_start < start_time or sub_end > end_time:
                    errors.append(f"切片 {i+1} 子切片 {j+1}: 时间超出父切片范围")
                    continue
                
                if sub_start >= sub_end:
                    errors.append(f"切片 {i+1} 子切片 {j+1}: 开始时间必须小于结束时间")
                    continue
                
                # 检查子切片持续时间（至少2秒）
                if sub_end - sub_start < 2:
                    errors.append(f"切片 {i+1} 子切片 {j+1}: 持续时间太短，至少需要2秒")
                    continue
        
        return len(errors) == 0, errors
    
    def _parse_time_str(self, time_str: str) -> Optional[float]:
        """
        解析时间字符串为秒数
        
        Args:
            time_str: 时间字符串，格式如 "00:05:01,199"
            
        Returns:
            秒数
        """
        try:
            # 处理格式 "HH:MM:SS,mmm"
            if ',' in time_str:
                time_part, ms_part = time_str.split(',')
                hours, minutes, seconds = time_part.split(':')
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                return total_seconds + int(ms_part) / 1000.0
            else:
                # 处理格式 "HH:MM:SS"
                hours, minutes, seconds = time_str.split(':')
                return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        except:
            return None
    
    def _parse_time_str_sync(self, time_str: str) -> Optional[float]:
        """
        同步版本 - 解析时间字符串为秒数
        
        Args:
            time_str: 时间字符串，格式如 "00:05:01,199"
            
        Returns:
            秒数
        """
        return self._parse_time_str(time_str)
    
    def generate_filename(self, cover_title: str, index: int, is_sub_slice: bool = False) -> str:
        """
        生成文件名
        
        Args:
            cover_title: 封面标题
            index: 索引
            is_sub_slice: 是否为子切片
            
        Returns:
            文件名
        """
        import uuid
        
        # 生成UUID作为文件名
        file_uuid = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if is_sub_slice:
            return f"sub_{file_uuid}_{timestamp}.mp4"
        else:
            return f"slice_{file_uuid}_{timestamp}.mp4"

# 创建全局视频切片服务实例
video_slicing_service = VideoSlicingService()