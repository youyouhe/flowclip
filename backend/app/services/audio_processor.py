import subprocess
import os
import tempfile
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.minio_client import minio_service

logger = logging.getLogger(__name__)

class AudioProcessor:
    """音频处理服务，负责从视频中提取音频、切割音频等操作"""
    
    def __init__(self):
        self.temp_dir = getattr(settings, 'temp_dir', None) or "/tmp"
    
    async def extract_audio_from_video(
        self, 
        video_path: str, 
        video_id: str, 
        project_id: int, 
        user_id: int,
        audio_format: str = "wav",
        custom_filename: str = None
    ) -> Dict[str, Any]:
        """从视频中提取音频并保存到MinIO"""
        
        logger.info(f"开始从视频提取音频: {video_path}")
        
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 构建输出音频文件路径
                if custom_filename:
                    audio_filename = f"{custom_filename}.{audio_format}"
                else:
                    audio_filename = f"{video_id}.{audio_format}"
                output_path = temp_path / audio_filename
                
                # 使用ffmpeg提取音频
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-vn',  # 禁用视频
                    '-acodec', 'pcm_s16le',  # 16-bit PCM
                    '-ar', '16000',  # 采样率 16kHz
                    '-ac', '1',  # 单声道
                    '-y',  # 覆盖输出文件
                    str(output_path)
                ]
                
                logger.info(f"执行ffmpeg命令: {' '.join(cmd)}")
                
                # 执行命令
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"ffmpeg音频提取失败: {result.stderr}")
                    raise Exception(f"音频提取失败: {result.stderr}")
                
                # 检查输出文件
                if not output_path.exists():
                    raise Exception("音频文件未生成")
                
                # 获取音频信息
                audio_info = await self._get_audio_info(str(output_path))
                
                # 上传到MinIO
                if custom_filename:
                    audio_object_name = f"users/{user_id}/projects/{project_id}/audio/{custom_filename}.{audio_format}"
                else:
                    audio_object_name = minio_service.generate_audio_object_name(
                        user_id, project_id, video_id, audio_format
                    )
                
                audio_url = await minio_service.upload_file(
                    str(output_path),
                    audio_object_name,
                    f"audio/{audio_format}"
                )
                
                if not audio_url:
                    raise Exception("音频文件上传到MinIO失败")
                
                logger.info(f"音频提取完成，上传到: {audio_url}")
                
                return {
                    'success': True,
                    'video_id': video_id,
                    'audio_filename': audio_filename,
                    'minio_path': audio_url,
                    'object_name': audio_object_name,
                    'duration': audio_info.get('duration', 0),
                    'file_size': output_path.stat().st_size,
                    'audio_format': audio_format,
                    'sample_rate': audio_info.get('sample_rate', 16000),
                    'channels': audio_info.get('channels', 1)
                }
                
        except Exception as e:
            logger.error(f"音频提取失败: {str(e)}", exc_info=True)
            raise Exception(f"音频提取失败: {str(e)}")
    

    async def _get_audio_info(self, audio_path: str) -> Dict[str, Any]:
        """获取音频文件信息"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"无法获取音频信息: {result.stderr}")
                return {}
            
            import json
            probe_data = json.loads(result.stdout)
            
            # 提取音频流信息
            audio_stream = None
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break
            
            if not audio_stream:
                return {}
            
            format_info = probe_data.get('format', {})
            
            return {
                'duration': float(format_info.get('duration', 0)),
                'file_size': int(format_info.get('size', 0)),
                'sample_rate': int(audio_stream.get('sample_rate', 16000)),
                'channels': int(audio_stream.get('channels', 1)),
                'codec': audio_stream.get('codec_name', 'unknown'),
                'bit_rate': int(audio_stream.get('bit_rate', 0))
            }
            
        except Exception as e:
            logger.error(f"获取音频信息失败: {str(e)}")
            return {}
    
    async def convert_audio_sample_rate(self, audio_path: str, target_sample_rate: int = 16000) -> str:
        """转换音频文件的采样率到目标采样率（默认16000Hz）"""
        try:
            logger.info(f"检查音频采样率: {audio_path}")
            
            # 获取音频信息
            audio_info = await self._get_audio_info(audio_path)
            current_sample_rate = audio_info.get('sample_rate', 16000)
            
            # 如果已经是目标采样率，直接返回原路径
            if current_sample_rate == target_sample_rate:
                logger.info(f"音频采样率已经是 {target_sample_rate}Hz，无需转换")
                return audio_path
            
            logger.info(f"音频采样率 {current_sample_rate}Hz 需要转换为 {target_sample_rate}Hz")
            
            # 创建临时输出文件路径
            from pathlib import Path
            audio_path_obj = Path(audio_path)
            converted_path = audio_path_obj.parent / f"{audio_path_obj.stem}_converted{audio_path_obj.suffix}"
            
            # 使用ffmpeg转换采样率
            cmd = [
                'ffmpeg',
                '-i', audio_path,
                '-ar', str(target_sample_rate),
                '-ac', '1',  # 单声道
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-y',  # 覆盖输出文件
                str(converted_path)
            ]
            
            logger.info(f"执行采样率转换命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"ffmpeg采样率转换失败: {result.stderr}")
                raise Exception(f"音频采样率转换失败: {result.stderr}")
            
            # 检查输出文件
            if not converted_path.exists():
                raise Exception("采样率转换后的音频文件未生成")
            
            logger.info(f"采样率转换完成: {converted_path}")
            return str(converted_path)
            
        except Exception as e:
            logger.error(f"音频采样率转换失败: {str(e)}")
            raise Exception(f"音频采样率转换失败: {str(e)}")
    
    # DEPRECATED: 此方法已弃用，系统不再支持音频分割功能
    # 保留在这里仅为了向后兼容，建议使用generate_srt_from_audio直接处理完整音频文件
    async def split_audio_file(
        self,
        audio_path: str,
        video_id: str,
        project_id: int,
        user_id: int,
        max_segment_len: int = 45000,
        min_segment_len: int = 10000,
        silence_thresh: int = -35,
        min_silence_len: int = 500
    ) -> Dict[str, Any]:
        """切割音频文件"""

        import os
        import sys
        from pathlib import Path
        
        logger.info(f"开始切割音频文件: {audio_path}")
        
        try:
            # 检查音频文件是否存在
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
            # 检查文件大小
            file_size = os.path.getsize(audio_path)
            if file_size == 0:
                raise ValueError(f"音频文件为空: {audio_path}")
            
            # 导入音频分割模块
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            
            # 创建临时目录 - 在整个流程完成前都保持打开
            temp_dir = tempfile.mkdtemp()
            try:
                temp_path = Path(temp_dir)
                
                # 设置输出目录
                output_dir = temp_path / f"splits_{video_id}"
                output_dir.mkdir(exist_ok=True)
                
                try:
                    from audio_splitter_enhanced import split_audio
                    logger.info("使用增强版音频分割器")
                    
                    output_files = split_audio(
                        input_file=audio_path,
                        output_dir=str(output_dir),
                        max_segment_len=max_segment_len,
                        min_segment_len=min_segment_len,
                        silence_thresh=silence_thresh,
                        min_silence_len=min_silence_len
                    )
                    # 确保返回的是列表格式
                    if output_files is None:
                        output_files = []
                    elif not isinstance(output_files, list):
                        output_files = list(output_files)
                        
                except ImportError:
                    # 如果pydub缺失，使用简化版本
                    logger.warning("pydub缺失，使用简化音频分割器")
                    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    from simple_audio_splitter import split_audio_simple as split_audio
                    output_files = split_audio(
                        input_file=audio_path,
                        output_dir=str(output_dir),
                        max_segment_len=max_segment_len,
                        min_segment_len=min_segment_len,
                        silence_thresh=silence_thresh,
                        min_silence_len=min_silence_len
                    )
                    # 确保返回的是列表格式
                    if output_files is None:
                        output_files = []
                    elif not isinstance(output_files, list):
                        output_files = list(output_files)
                        
            except ImportError as e:
                logger.warning(f"所有音频分割模块导入失败: {e} - 使用内置ffmpeg方案")
                output_files = await self._simple_audio_split(
                    audio_path, video_id, max_segment_len, min_segment_len
                )
                
                if not output_files or not isinstance(output_files, list):
                    raise Exception("音频分割失败，未生成文件")
                
                # 确保返回的是列表格式
                if output_files is None:
                    output_files = []
                elif not isinstance(output_files, list):
                    output_files = list(output_files)
                    
            # 确保所有文件都存在
            valid_files = []
            for f in output_files:
                if os.path.exists(f):
                    valid_files.append(f)
                else:
                    logger.warning(f"分割文件不存在: {f}")
            output_files = valid_files
            
            # 上传分割后的音频文件到MinIO
            split_files_info = []
            logger.info(f"开始上传 {len(output_files)} 个分割文件到MinIO")
            
            for i, split_file in enumerate(output_files):
                try:
                    split_filename = Path(split_file).name
                    split_object_name = minio_service.generate_split_audio_object_name(
                        user_id, project_id, video_id, i+1
                    )
                    
                    logger.info(f"上传文件 {i+1}: {split_file} -> {split_object_name}")
                    
                    split_url = await minio_service.upload_file(
                        split_file,
                        split_object_name,
                        "audio/wav"
                    )
                    
                    if split_url:
                        file_size = Path(split_file).stat().st_size
                        split_files_info.append({
                            'segment_index': i+1,
                            'filename': split_filename,
                            'minio_path': split_url,
                            'object_name': split_object_name,
                            'file_size': file_size
                        })
                        logger.info(f"成功上传: {split_url} ({file_size} bytes)")
                    else:
                        logger.error(f"上传失败: {split_file}")
                except Exception as e:
                    logger.error(f"上传文件 {split_file} 失败: {e}")
                    continue
            
            logger.info(f"音频分割完成，成功上传 {len(split_files_info)} 个片段")
            
            if not split_files_info:
                logger.error("没有成功上传任何分割文件")
                return {
                    'success': False,
                    'error': '没有成功上传任何分割文件',
                    'video_id': video_id,
                    'total_segments': 0,
                    'split_files': [],
                    'segmentation_params': {
                        'max_segment_len': max_segment_len,
                        'min_segment_len': min_segment_len,
                        'silence_thresh': silence_thresh,
                        'min_silence_len': min_silence_len
                    }
                }
            

            return {
                'success': True,
                'video_id': video_id,
                'total_segments': len(split_files_info),
                'split_files': split_files_info,
                'segmentation_params': {
                    'max_segment_len': max_segment_len,
                    'min_segment_len': min_segment_len,
                    'silence_thresh': silence_thresh,
                    'min_silence_len': min_silence_len
                }
            }
            
        finally:
            # 清理临时目录
            import shutil
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"已清理临时目录: {temp_dir}")
            except Exception as cleanup_error:
                logger.warning(f"清理临时目录失败: {cleanup_error}")
                
            except Exception as e:
                logger.error(f"音频分割失败: {str(e)}", exc_info=True)
                raise Exception(f"音频分割失败: {str(e)}")
    
    async def _simple_audio_split(self, audio_path: str, video_id: str, max_segment_len: int, min_segment_len: int) -> list:
        """简单的音频分割方案，使用ffmpeg作为备选"""
        logger.info("使用简单的ffmpeg分割方案")

        import subprocess
        import os
        
        # 获取音频时长
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        
        # 计算分割点（每段30秒）
        segment_duration = min(max_segment_len / 1000, 30)  # 30秒或用户指定的最大值
        num_segments = int(duration // segment_duration) + 1
        
        output_files = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(num_segments):
                start_time = i * segment_duration
                end_time = min((i + 1) * segment_duration, duration)
                
                if end_time - start_time < min_segment_len / 1000:
                    break
                
                output_file = os.path.join(temp_dir, f"segment_{i+1:03d}.wav")
                
                cmd = [
                    'ffmpeg',
                    '-i', audio_path,
                    '-ss', str(start_time),
                    '-t', str(end_time - start_time),
                    '-c', 'copy',
                    '-y',
                    output_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    output_files.append(output_file)
                else:
                    logger.error(f"ffmpeg分割失败: {result.stderr}")
                    raise Exception(f"音频分割失败: {result.stderr}")
        
        return output_files
    
    async def segment_audio_by_time(
        self,
        audio_path: str,
        start_time: float,
        end_time: float,
        output_path: str = None
    ) -> str:
        """根据时间范围分割音频文件"""
        import subprocess
        import os
        from pathlib import Path
        
        logger.info(f"分割音频文件: {audio_path}, 时间范围: {start_time}s - {end_time}s")
        
        try:
            # 如果没有指定输出路径，创建临时文件
            if output_path is None:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    output_path = tmp_file.name
            
            # 构建FFmpeg命令进行音频分割
            duration = end_time - start_time
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),  # 开始时间
                '-i', audio_path,  # 输入文件
                '-t', str(duration),  # 持续时间
                '-c:a', 'pcm_s16le',  # 重新编码为16-bit PCM
                '-ar', '16000',  # 采样率16kHz
                '-ac', '1',  # 单声道
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")
            
            # 执行FFmpeg命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg执行失败: {result.stderr}")
                raise Exception(f"音频分割失败: {result.stderr}")
            
            # 检查输出文件
            if not os.path.exists(output_path):
                raise Exception("分割后的音频文件不存在")
            
            # 检查文件大小
            file_size = os.path.getsize(output_path)
            logger.info(f"音频分割成功: {output_path}, 文件大小: {file_size} bytes")
            
            # 如果文件太小(小于100字节)，可能是空文件
            if file_size < 100:
                logger.warning(f"警告: 分割后的音频文件可能为空，大小: {file_size} bytes")
                # 直接抛出异常，避免将空文件提交给ASR服务
                raise Exception(f"分割后的音频文件为空，大小: {file_size} bytes，跳过ASR处理")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            logger.error("音频分割超时")
            raise Exception("音频分割超时")
        except Exception as e:
            logger.error(f"音频分割失败: {str(e)}")
            raise Exception(f"音频分割失败: {str(e)}")

    async def generate_srt_from_audio(
        self,
        audio_path: str,
        video_id: str,
        project_id: int,
        user_id: int,
        api_url: str = None,
        lang: str = "auto",
        max_workers: int = 5,
        custom_filename: str = None,
        start_time: float = None,
        end_time: float = None,
        asr_service_url: str = None,
        asr_model_type: str = "whisper",  # 添加模型类型参数，默认为whisper
        enable_tus_routing: bool = None,  # 保留参数兼容性
        force_standard_asr: bool = False  # 保留参数兼容性
    ) -> Dict[str, Any]:
        """从音频文件生成SRT字幕文件 - 统一使用TUS处理"""

        logger.info(f"开始生成SRT字幕: {audio_path}")
        logger.info("统一使用TUS客户端处理ASR请求")

        try:
            from app.services.file_size_detector import asr_strategy_selector
            metadata = {
                'language': lang,
                'model': asr_model_type,
                'video_id': video_id,
                'project_id': project_id,
                'user_id': user_id
            }

            # 使用TUS客户端处理 - 只启动上传，不等待结果
            from app.services.tus_asr_client import tus_asr_client

            # 获取Celery任务ID
            current_celery_task_id = None
            try:
                import celery
                current_task = celery.current_task
                if current_task:
                    current_celery_task_id = current_task.request.id
                    logger.info(f"当前Celery任务ID: {current_celery_task_id}")
            except Exception as e:
                logger.debug(f"无法获取当前Celery任务ID: {e}")

            # 启动TUS任务（不等待结果）
            logger.info("启动TUS上传任务...")
            tus_task_result = await tus_asr_client._start_tus_task_only(audio_path, metadata)
            tus_task_id = tus_task_result.get('task_id')

            if not tus_task_id:
                raise Exception("TUS任务启动失败，未获取到任务ID")

            logger.info(f"TUS任务已启动，task_id: {tus_task_id}")

            # 提取slice_id和sub_slice_id信息用于链式任务
            slice_id = None
            sub_slice_id = None

            # 从metadata中获取slice_id和sub_slice_id
            if 'slice_id' in metadata:
                slice_id = metadata['slice_id']
            if 'sub_slice_id' in metadata:
                sub_slice_id = metadata['sub_slice_id']

            # 启动callback处理任务（链式任务）
            from app.tasks.subtasks.srt_task import process_tus_callback
            callback_task = process_tus_callback.delay(
                task_id=tus_task_id,
                video_id=video_id,
                project_id=project_id,
                user_id=user_id,
                slice_id=slice_id,
                sub_slice_id=sub_slice_id,
                original_celery_task_id=current_celery_task_id
            )

            logger.info(f"已启动callback处理任务: {callback_task.id}")

            # 立即返回，释放worker
            return {
                'success': True,
                'strategy': 'tus_async',  # 标记为异步TUS处理
                'task_id': tus_task_id,
                'callback_task_id': callback_task.id,
                'video_id': video_id,
                'project_id': project_id,
                'user_id': user_id,
                'status': 'processing',  # 标记为处理中状态
                'message': 'TUS任务已启动，等待callback处理',
                'processing_info': {
                    'tus_task_id': tus_task_id,
                    'callback_task_id': callback_task.id,
                    'async_processing': True
                },
                'audio_path': audio_path
            }

        except Exception as e:
            logger.error(f"TUS ASR处理失败: {e}")
            raise Exception(f"TUS ASR处理失败: {e}")

# 全局实例
audio_processor = AudioProcessor()
