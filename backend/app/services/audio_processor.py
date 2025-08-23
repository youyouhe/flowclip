import subprocess
import os
import tempfile
import asyncio
import logging
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
        import tempfile
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
        import tempfile
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
        import tempfile
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
        lang: str = "zh",
        max_workers: int = 5,
        custom_filename: str = None,
        start_time: float = None,
        end_time: float = None,
        asr_service_url: str = None  # 添加新参数
    ) -> Dict[str, Any]:
        """从音频文件生成SRT字幕文件 - 更新为直接处理音频文件"""
        
        logger.info(f"开始生成SRT字幕: {audio_path}")
        
        # 优先使用传入的asr_service_url，其次是api_url，最后是默认配置
        if asr_service_url:
            final_api_url = f"{asr_service_url.rstrip('/')}/asr"
            logger.info(f"使用动态传入的ASR服务URL: {final_api_url}")
        elif api_url:
            final_api_url = api_url
            logger.info(f"使用api_url参数指定的ASR服务URL: {final_api_url}")
        else:
            from app.core.config import settings
            final_api_url = f"{settings.asr_service_url}/asr"
            logger.info(f"使用默认配置的ASR服务URL: {final_api_url}")
        
        
        try:
            # 导入SRT生成模块和工具
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from wav_to_srt_direct_updated import process_directory
            from app.services.asr_timestamp_utils import (
                adjust_timestamps_with_duration, 
                create_srt_content, 
                validate_segments,
                get_wav_duration
            )
            
            # 如果提供了时间范围，先分割音频
            audio_to_process = audio_path
            temp_segmented_file = None
            
            if start_time is not None and end_time is not None:
                logger.info(f"根据时间范围分割音频: {start_time}s - {end_time}s")
                temp_segmented_file = await self.segment_audio_by_time(
                    audio_path=audio_path,
                    start_time=start_time,
                    end_time=end_time
                )
                audio_to_process = temp_segmented_file
                logger.info(f"使用分割后的音频文件: {audio_to_process}")
                
                # 检查分割后的文件是否存在和大小
                if os.path.exists(audio_to_process):
                    file_size = os.path.getsize(audio_to_process)
                    logger.info(f"分割后文件大小: {file_size} bytes")
                    if file_size < 100:
                        logger.warning(f"警告: 分割后的音频文件可能为空，大小: {file_size} bytes")
                        # 如果文件为空，直接返回错误，不提交给ASR服务
                        raise Exception(f"分割后的音频文件为空，大小: {file_size} bytes，跳过ASR处理")
            
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 如果传入的是音频文件，创建临时目录并复制文件
                if os.path.isfile(audio_to_process):
                    import shutil
                    temp_audio_dir = temp_path / "audio"
                    temp_audio_dir.mkdir()
                    dest_audio_path = temp_audio_dir / Path(audio_to_process).name
                    shutil.copy2(audio_to_process, dest_audio_path)
                    process_dir = str(temp_audio_dir)
                else:
                    # 如果传入的是目录，直接使用
                    process_dir = audio_to_process
                
                # 处理音频文件生成SRT
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                from wav_to_srt_direct_updated import process_audio_file
                
                # 检查process_dir是文件还是目录
                if os.path.isfile(audio_to_process):
                    # 处理单个音频文件
                    logger.info(f"处理单个音频文件: {audio_to_process}")
                    result = process_audio_file(
                        file_path=audio_to_process,
                        api_url=final_api_url,
                        index=1,  # 为单个文件指定索引
                        lang=lang
                    )
                    results = [result] if result else []
                else:
                    # 处理目录中的音频文件 - 这种情况现在很少见
                    logger.info(f"处理音频文件目录: {process_dir}")
                    
                    # 对于目录处理，需要确保文件名格式正确
                    wav_files = [f for f in os.listdir(process_dir) if f.endswith('.wav')]
                    if wav_files:
                        # 检查是否是分割文件格式 (xxx_yyy.wav)
                        sample_file = wav_files[0]
                        if '_' in sample_file and sample_file.split('_')[1].split('.')[0].isdigit():
                            # 使用原有的目录处理方法
                            results = process_directory(
                                directory=process_dir,
                                api_url=api_url,
                                lang=lang,
                                max_workers=max_workers
                            )
                        else:
                            # 不是分割文件格式，逐个处理每个文件
                            results = []
                            for idx, wav_file in enumerate(wav_files, 1):
                                file_path = os.path.join(process_dir, wav_file)
                                result = process_audio_file(
                                    file_path=file_path,
                                    api_url=api_url,
                                    index=idx,
                                    lang=lang
                                )
                                if result:
                                    results.append(result)
                    else:
                        results = []
                
                # 添加WAV时长信息到结果中
                for result in results:
                    if 'error' not in result:
                        wav_duration = get_wav_duration(result['file_path'])
                        result['wav_duration'] = wav_duration
                
                # 统计结果
                success_count = len([r for r in results if 'error' not in r])
                fail_count = len([r for r in results if 'error' in r])
                
                if success_count == 0:
                    raise Exception("没有成功处理的音频文件")
                
                # 使用增强版时间戳调整（基于wav_to_srt_direct_updated.py的修复）
                # 如果提供了时间范围，使用start_time作为时间偏移量
                time_offset = start_time if start_time is not None else 0.0
                adjusted_segments = adjust_timestamps_with_duration(results, time_offset)
                
                # 验证和清理字幕片段
                adjusted_segments = validate_segments(adjusted_segments)
                
                # 生成SRT文件
                if custom_filename:
                    srt_filename = custom_filename
                else:
                    srt_filename = f"{video_id}.srt"
                srt_path = temp_path / srt_filename
                
                # 使用增强版SRT内容生成，带UTF-8 BOM
                srt_content = create_srt_content(adjusted_segments)
                with open(srt_path, 'w', encoding='utf-8-sig') as f:
                    f.write(srt_content)
                
                # 上传SRT文件到MinIO
                if custom_filename:
                    # 使用自定义文件名生成对象名称
                    srt_object_name = f"users/{user_id}/projects/{project_id}/subtitles/{custom_filename}"
                else:
                    # 使用原来的逻辑
                    srt_object_name = minio_service.generate_srt_object_name(
                        user_id, project_id, video_id
                    )
                
                srt_url = await minio_service.upload_file(
                    str(srt_path),
                    srt_object_name,
                    "text/srt"
                )
                
                if not srt_url:
                    raise Exception("SRT文件上传到MinIO失败")
                
                # 保存原始JSON结果
                json_filename = f"{video_id}_asr_result.json"
                json_path = temp_path / json_filename
                import json
                with open(json_path, 'w', encoding='utf-8-sig') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                
                json_object_name = minio_service.generate_asr_json_object_name(
                    user_id, project_id, video_id
                )
                
                json_url = await minio_service.upload_file(
                    str(json_path),
                    json_object_name,
                    "application/json"
                )
                
                logger.info(f"SRT字幕生成完成，共 {len(adjusted_segments)} 条字幕")
                
                # 清理临时分割的音频文件
                if temp_segmented_file and os.path.exists(temp_segmented_file):
                    try:
                        os.unlink(temp_segmented_file)
                        logger.info(f"已清理临时分割音频文件: {temp_segmented_file}")
                    except Exception as cleanup_error:
                        logger.warning(f"清理临时分割音频文件失败: {cleanup_error}")
                
                return {
                    'success': True,
                    'video_id': video_id,
                    'srt_filename': srt_filename,
                    'minio_path': srt_url,
                    'object_name': srt_object_name,
                    'json_result_path': json_url,
                    'total_segments': len(adjusted_segments),
                    'processing_stats': {
                        'success_count': success_count,
                        'fail_count': fail_count,
                        'total_files': len(results)
                    },
                    'asr_params': {
                        'api_url': api_url,
                        'lang': lang,
                        'max_workers': max_workers
                    }
                }
                
        except Exception as e:
            logger.error(f"SRT字幕生成失败: {str(e)}", exc_info=True)
            raise Exception(f"SRT字幕生成失败: {str(e)}")

# 全局实例
audio_processor = AudioProcessor()