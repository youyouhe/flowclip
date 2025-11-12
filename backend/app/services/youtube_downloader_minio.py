import subprocess
import os
import aiofiles
import tempfile
import shutil
import re
from typing import Dict, Any, Optional, Callable
import asyncio
from pathlib import Path
import logging
import yt_dlp
import urllib.request
import socket
from app.core.config import settings
from app.services.minio_client import minio_service
from app.services.progress_service import update_video_progress

logger = logging.getLogger(__name__)

async def validate_downloaded_file(file_path: Path) -> Dict[str, Any]:
    """验证下载的视频文件是否完整可用"""
    try:
        if not file_path.exists():
            return {"valid": False, "reason": "文件不存在"}

        file_size = file_path.stat().st_size
        if file_size < 1024 * 1024:  # 小于1MB认为不完整
            return {"valid": False, "reason": f"文件过小: {file_size} bytes"}

        # 使用ffprobe验证文件完整性
        try:
            import subprocess
            result = await asyncio.create_subprocess_exec(
                'ffprobe', '-v', 'error', '-show_format', '-show_streams',
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                # 解析ffprobe输出验证视频流
                output = stdout.decode('utf-8')
                has_video = 'codec_name=h264' in output or 'codec_name=hevc' in output
                has_audio = 'codec_name=aac' in output or 'codec_name=mp3' in output
                has_duration = 'duration=' in output

                if has_video and has_audio and has_duration:
                    logger.info(f"✓ 文件完整性验证通过: {file_path.name} ({file_size} bytes)")
                    return {
                        "valid": True,
                        "file_size": file_size,
                        "has_video": has_video,
                        "has_audio": has_audio,
                        "has_duration": has_duration
                    }
                else:
                    return {
                        "valid": False,
                        "reason": f"文件缺少必要流: video={has_video}, audio={has_audio}, duration={has_duration}"
                    }
            else:
                return {"valid": False, "reason": f"ffprobe验证失败: {stderr.decode('utf-8')}"}

        except Exception as e:
            logger.warning(f"ffprobe验证失败，尝试基础检查: {e}")
            # 如果ffprobe不可用，进行基础检查
            if file_size > 10 * 1024 * 1024:  # 大于10MB认为可能完整
                return {"valid": True, "file_size": file_size, "method": "基础检查"}
            else:
                return {"valid": False, "reason": f"文件可能不完整: {file_size} bytes"}

    except Exception as e:
        return {"valid": False, "reason": f"验证过程异常: {str(e)}"}

def is_recoverable_error(error_output: str) -> bool:
    """判断是否为可恢复的yt-dlp错误"""
    recoverable_errors = [
        "Did not get any data blocks",
        "fragment not found",
        "HTTP Error 404",
        "Unable to download video data",
        "This video is unavailable",
        "'false' is not a valid URL",  # 布尔参数错误
        "nsig extraction failed",      # YouTube签名提取失败
        "Unable to extract nsig function"  # n函数提取失败
    ]

    error_lower = error_output.lower()
    return any(error.lower() in error_lower for error in recoverable_errors)

class YouTubeDownloaderMinio:
    """集成MinIO的YouTube下载器"""
    
    def __init__(self, cookies_file: str = None):
        self.cookies_file = cookies_file
        
    async def get_video_info(self, url: str, cookies_file: str = None) -> Dict[str, Any]:
        """获取视频信息"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        # 使用提供的cookie文件或默认的cookie文件
        effective_cookies_file = cookies_file or self.cookies_file
        if effective_cookies_file and os.path.exists(effective_cookies_file):
            ydl_opts['cookiefile'] = effective_cookies_file
            logger.info(f"使用cookie文件: {effective_cookies_file}")
        else:
            logger.warning(f"未找到cookie文件: {effective_cookies_file}")
            if cookies_file:
                logger.error(f"上传的cookie文件不存在: {cookies_file}")
            if self.cookies_file:
                logger.error(f"默认cookie文件不存在: {self.cookies_file}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'view_count': info.get('view_count'),
                    'description': info.get('description'),
                    'thumbnail': info.get('thumbnail'),
                    'formats': self._extract_formats(info.get('formats', [])),
                    'filesize': info.get('filesize_approx'),
                    'video_id': info.get('id')
                }
        except Exception as e:
            raise Exception(f"获取视频信息失败: {str(e)}")
    
    def _extract_formats(self, formats: list) -> list:
        """提取可用的视频格式"""
        video_formats = []
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                video_formats.append({
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution'),
                    'filesize': f.get('filesize'),
                    'quality': f.get('quality')
                })
        return video_formats
    
    def _parse_download_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """解析yt-dlp的下载进度输出，提供更详细的实时进度信息"""
        
        # 匹配下载进度行: [download]  25.8% of ~959.74MiB at    2.67MiB/s ETA 05:44 (frag 24/893)
        download_pattern = r'\[download\]\s+(\d+\.?\d*)%.*of\s+~?(\d+\.?\d*)(MiB|GiB|KiB|MB|GB|KB|bytes).*at\s+([\d\.]+)(MiB|GiB|KiB|MB|GB|KB|bytes)/s.*ETA\s+([\d:]+)'
        
        # 匹配片段进度: (frag 24/893)
        fragment_pattern = r'\(frag\s+(\d+)/(\d+)\)'
        
        # 匹配HLS片段进度: [hlsnative] Downloading m3u8 manifest
        hls_manifest_pattern = r'\[hlsnative\]\s+Downloading\s+m3u8\s+manifest'
        
        # 匹配HLS片段总数: [hlsnative] Total fragments: 893
        hls_total_pattern = r'\[hlsnative\]\s+Total\s+fragments:\s+(\d+)'
        
        # 匹配合并进度: [ffmpeg] Merging formats into "output.mp4"
        merge_pattern = r'\[ffmpeg\]\s+Merging formats'
        
        # 匹配转换进度: [ffmpeg] Destination: output.mp4
        convert_pattern = r'\[ffmpeg\]\s+Destination:'
        
        # 匹配完成信息: [download] 100% of 959.74MiB in 05:44
        complete_pattern = r'\[download\]\s+100%.*in\s+[\d:]+'
        
        # 匹配错误信息
        error_pattern = r'\[download\]\s+ERROR:\s+(.+)'  
        warning_pattern = r'\[download\]\s+WARNING:\s+(.+)'
        
        # 匹配文件已存在
        exists_pattern = r'\[download\]\s+(.+)\s+has\s+already\s+been\s+downloaded'
        
        # 匹配正在下载文件
        destination_pattern = r'\[download\]\s+Destination:\s+(.+)'
        
        # 匹配视频信息提取
        info_pattern = r'\[youtube\]\s+(.+):\s+Downloading\s+webpage'
        
        # 匹配格式选择
        format_pattern = r'\[info\]\s+Downloading\s+(\d+)\s+format\(s\):\s+(.+)'
        
        # 检查是否为下载进度行
        match = re.search(download_pattern, line)
        if match:
            percentage = float(match.group(1))
            total_size = float(match.group(2))
            unit = match.group(3)
            speed = float(match.group(4))
            speed_unit = match.group(5)
            eta = match.group(6)
            
            # 尝试获取片段信息
            fragment_match = re.search(fragment_pattern, line)
            current_frag = int(fragment_match.group(1)) if fragment_match else None
            total_frags = int(fragment_match.group(2)) if fragment_match else None
            
            # 计算基于片段的进度（如果有片段信息）
            fragment_progress = 0
            if current_frag and total_frags and total_frags > 0:
                fragment_progress = (current_frag / total_frags) * 100
                # 使用片段进度作为更准确的进度指示
                if abs(percentage - fragment_progress) > 5:  # 如果差异较大，使用片段进度
                    percentage = fragment_progress
            
            # 构建详细消息
            message_parts = []
            message_parts.append(f"下载中 {percentage:.1f}%")
            
            # 添加文件大小信息
            if total_size and unit:
                message_parts.append(f"文件大小: {total_size:.1f}{unit}")
            
            # 添加速度信息
            if speed and speed_unit:
                message_parts.append(f"速度: {speed:.1f}{speed_unit}/s")
            
            # 添加剩余时间
            if eta:
                message_parts.append(f"剩余: {eta}")
            
            # 添加片段信息
            if current_frag and total_frags:
                message_parts.append(f"片段: {current_frag}/{total_frags}")
            
            message = " | ".join(message_parts)
            
            return {
                'percentage': percentage,
                'total_size': total_size,
                'unit': unit,
                'speed': speed,
                'speed_unit': speed_unit,
                'eta': eta,
                'current_fragment': current_frag,
                'total_fragments': total_frags,
                'message': message,
                'stage': 'downloading'
            }
        
        # 检查HLS下载阶段
        if re.search(hls_manifest_pattern, line):
            return {
                'percentage': 5,
                'message': "正在获取HLS播放列表...",
                'stage': 'preparing'
            }
        
        hls_total_match = re.search(hls_total_pattern, line)
        if hls_total_match:
            total_frags = int(hls_total_match.group(1))
            return {
                'percentage': 10,
                'message': f"检测到 {total_frags} 个HLS片段",
                'stage': 'preparing',
                'total_fragments': total_frags
            }
        
        # 检查视频信息提取
        info_match = re.search(info_pattern, line)
        if info_match:
            video_id = info_match.group(1)
            return {
                'percentage': 2,
                'message': f"正在获取视频 {video_id} 信息...",
                'stage': 'analyzing'
            }
        
        # 检查格式选择
        format_match = re.search(format_pattern, line)
        if format_match:
            format_count = format_match.group(1)
            format_info = format_match.group(2)
            return {
                'percentage': 15,
                'message': f"选择格式: {format_info}",
                'stage': 'preparing'
            }
        
        # 检查目标文件
        dest_match = re.search(destination_pattern, line)
        if dest_match:
            filename = dest_match.group(1)
            return {
                'percentage': 20,
                'message': f"准备下载: {filename}",
                'stage': 'starting'
            }
        
        # 匹配合并进度
        if re.search(merge_pattern, line):
            return {
                'percentage': 95,
                'message': "正在合并音视频流...",
                'stage': 'merging'
            }
        
        # 匹配转换进度
        if re.search(convert_pattern, line):
            return {
                'percentage': 98,
                'message': "正在转换视频格式...",
                'stage': 'converting'
            }
        
        # 匹配完成信息
        if re.search(complete_pattern, line):
            return {
                'percentage': 100,
                'message': "下载完成",
                'stage': 'completed'
            }
        
        # 匹配文件已存在
        exists_match = re.search(exists_pattern, line)
        if exists_match:
            filename = exists_match.group(1)
            return {
                'percentage': 100,
                'message': f"文件已存在: {filename}",
                'stage': 'completed'
            }
        
        # 匹配错误信息
        error_match = re.search(error_pattern, line)
        if error_match:
            error_msg = error_match.group(1)
            return {
                'percentage': 0,
                'message': f"错误: {error_msg}",
                'stage': 'error'
            }
        
        # 匹配警告信息
        warning_match = re.search(warning_pattern, line)
        if warning_match:
            warning_msg = warning_match.group(1)
            return {
                'percentage': 0,
                'message': f"警告: {warning_msg}",
                'stage': 'warning'
            }
        
        # 匹配其他状态信息
        if '[download]' in line:
            # 提取关键信息
            msg = line.strip().replace('[download]', '').strip()
            if msg and not msg.startswith('Destination:'):
                # 根据消息内容估计进度
                estimated_progress = 0
                if 'Downloading' in msg:
                    estimated_progress = 25
                elif 'writing' in msg.lower():
                    estimated_progress = 30
                elif 'merging' in msg.lower():
                    estimated_progress = 95
                
                return {
                    'percentage': estimated_progress,
                    'message': msg,
                    'stage': 'processing'
                }
        
        return None
    
    async def download_and_upload_video(
        self, 
        url: str, 
        project_id: int, 
        user_id: int,
        video_id: int = None,  # 新增视频ID参数
        quality: str = 'best',  # '360p', '720p', '1080p', 'best'
        cookies_file: str = None,  # 新增cookie文件参数
        progress_callback: Optional[Callable[[float, str], None]] = None  # 进度回调函数
    ) -> Dict[str, Any]:
        """使用yt-dlp命令行下载视频并上传到MinIO"""

        logger.info(f"开始命令行下载视频: {url}")
        logger.info(f"项目ID: {project_id}, 用户ID: {user_id}, 质量: {quality}")

        # 初始化容错状态变量
        download_succeeded_with_recovery = False
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            logger.info(f"创建临时目录: {temp_path}")
            
            # 使用提供的cookie文件或实例的cookie文件
            effective_cookies_file = cookies_file or self.cookies_file
            
            # 构建yt-dlp命令 - 添加容错参数
            cmd = [
                'yt-dlp',
                url,
                '--output', str(temp_path / '%(id)s.%(ext)s'),
                '--no-playlist',
                '--write-info-json',
                '--write-thumbnail',
                '--newline',  # 确保每行输出都立即刷新
                '--verbose',  # 添加详细输出以获取更多进度信息
                # 容错参数
                '--ignore-errors',  # 忽略可恢复的下载错误
                '--hls-use-mpegts',  # 使用MPEG-TS格式以提高HLS容错性
                '--retries', '3',  # 重试次数
                '--fragment-retries', '5',  # 分片重试次数
                '--skip-unavailable-fragments',  # 跳过不可用的分片
                '--no-check-certificate'  # 跳过证书检查（如果需要）
            ]
            
            # 添加cookie文件（如果存在）
            if effective_cookies_file and os.path.exists(effective_cookies_file):
                cmd.extend(['--cookies', effective_cookies_file])
                logger.info(f"使用cookie文件下载: {effective_cookies_file}")
            else:
                logger.warning(f"未使用cookie文件: {effective_cookies_file}")
            
            # 只在非'best'时添加format参数
            if quality != 'best':
                cmd.extend(['--format', quality])
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            try:
                # 记录环境信息用于调试
                logger.info(f"执行环境信息:")
                logger.info(f"  工作目录权限: {os.stat(temp_path).st_mode}")
                logger.info(f"  当前用户: {os.getuid()}")
                logger.info(f"  环境变量PATH: {os.environ.get('PATH', 'N/A')}")
                
                # 检查yt-dlp是否可执行
                import shutil as shutil_module
                yt_dlp_path = shutil_module.which('yt-dlp')
                if yt_dlp_path:
                    logger.info(f"  yt-dlp路径: {yt_dlp_path}")
                    # 检查yt-dlp版本
                    try:
                        version_result = subprocess.run(['yt-dlp', '--version'], 
                                                       capture_output=True, text=True, timeout=10)
                        logger.info(f"  yt-dlp版本: {version_result.stdout.strip()}")
                    except Exception as version_error:
                        logger.warning(f"  无法获取yt-dlp版本: {version_error}")
                else:
                    logger.error("  yt-dlp未找到在PATH中")
                
                # 执行命令行下载，实时解析输出
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    cwd=str(temp_path),
                    universal_newlines=True,
                    bufsize=1  # 行缓冲
                )
                
                logger.info("开始实时解析yt-dlp输出...")
                
                # 实时解析输出
                download_progress = 0.0
                last_progress = -1  # 记录上一次进度，避免重复更新
                last_update_time = 0  # 记录上次更新时间
                
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        line = output.strip()
                        if line:
                            logger.debug(f"yt-dlp输出: {line}")
                            
                            # 解析进度信息
                            progress_info = self._parse_download_progress(line)
                            if progress_info:
                                download_progress = progress_info['percentage']
                                message = progress_info['message']
                                stage = progress_info.get('stage', 'downloading')
                                
                                # 只在进度有变化或间隔超过1秒时更新，避免过于频繁的更新
                                import time
                                current_time = time.time()
                                should_update = (
                                    abs(download_progress - last_progress) > 0.5 or  # 进度变化超过0.5%
                                    current_time - last_update_time > 1.0 or      # 间隔超过1秒
                                    download_progress == 100 or                    # 完成时
                                    stage in ['error', 'completed']                # 重要阶段
                                )
                                
                                if should_update:
                                    last_progress = download_progress
                                    last_update_time = current_time
                                    
                                    # 调用进度回调函数
                                    if progress_callback:
                                        try:
                                            # 由于progress_callback可能是同步函数，使用asyncio创建任务
                                            if asyncio.iscoroutinefunction(progress_callback):
                                                await progress_callback(download_progress, message)
                                            else:
                                                # 对于同步回调，使用线程池执行
                                                import asyncio as _asyncio
                                                loop = _asyncio.get_event_loop()
                                                await loop.run_in_executor(None, progress_callback, download_progress, message)
                                        except Exception as e:
                                            logger.warning(f"进度回调失败: {e}")
                                    
                                    # 更新进度到数据库和WebSocket
                                    if video_id:
                                        try:
                                            progress_data = {
                                                'download_progress': download_progress,
                                                'status': 'downloading',
                                                'processing_message': message,
                                                'processing_stage': stage,
                                                'download_speed': progress_info.get('speed'),
                                                'download_speed_unit': progress_info.get('speed_unit'),
                                                'file_size': progress_info.get('total_size'),
                                                'file_size_unit': progress_info.get('unit'),
                                                'eta': progress_info.get('eta'),
                                                'current_fragment': progress_info.get('current_fragment'),
                                                'total_fragments': progress_info.get('total_fragments')
                                            }
                                            await update_video_progress(video_id, user_id, progress_data)
                                        except Exception as e:
                                            logger.warning(f"更新进度失败: {e}")
                                    
                                    logger.info(f"下载进度: {download_progress:.1f}% - {message}")
                            else:
                                # 记录未解析的输出用于调试
                                if '[download]' in line or '[youtube]' in line or '[info]' in line:
                                    logger.debug(f"未解析的输出: {line}")
                
                # 确保进程结束
                process.wait()
                
                # 检查命令执行结果
                if process.returncode != 0:
                    # 获取剩余的错误输出
                    remaining_output = process.stdout.read()
                    if remaining_output:
                        logger.error(f"yt-dlp额外输出: {remaining_output}")
                    
                    # 收集所有错误信息
                    error_lines = []
                    for line in remaining_output.split('\n') if remaining_output else []:
                        if line.strip():
                            error_lines.append(line.strip())
                    
                    # 尝试直接执行yt-dlp命令以获取更详细的错误信息
                    logger.info("尝试直接执行yt-dlp命令以获取更详细的错误信息...")
                    try:
                        direct_result = subprocess.run(cmd, 
                                                     cwd=str(temp_path),
                                                     capture_output=True, 
                                                     text=True, 
                                                     timeout=30)
                        if direct_result.returncode != 0:
                            logger.error(f"直接执行yt-dlp命令失败:")
                            logger.error(f"  返回码: {direct_result.returncode}")
                            logger.error(f"  标准输出: {direct_result.stdout}")
                            logger.error(f"  错误输出: {direct_result.stderr}")
                    except subprocess.TimeoutExpired:
                        logger.error("直接执行yt-dlp命令超时")
                    except Exception as direct_error:
                        logger.error(f"直接执行yt-dlp命令时发生异常: {direct_error}")
                    
                    # 记录完整的错误输出用于调试
                    logger.error(f"yt-dlp命令执行失败，返回码: {process.returncode}")
                    logger.error(f"完整命令: {' '.join(cmd)}")
                    logger.error(f"工作目录: {temp_path}")
                    logger.error(f"工作目录内容: {list(temp_path.iterdir()) if temp_path.exists() else '目录不存在'}")
                    
                    # 检查系统环境
                    try:
                        # 检查磁盘空间
                        import shutil as shutil_module
                        disk_usage = shutil_module.disk_usage(temp_path)
                        logger.error(f"磁盘空间 - 总计: {disk_usage.total}, 已用: {disk_usage.used}, 可用: {disk_usage.free}")
                        
                        # 检查内存使用情况
                        try:
                            import psutil
                            memory = psutil.virtual_memory()
                            logger.error(f"内存使用 - 总计: {memory.total}, 可用: {memory.available}, 使用率: {memory.percent}%")
                        except ImportError:
                            logger.warning("psutil未安装，跳过内存检查")
                    except Exception as sys_error:
                        logger.warning(f"系统信息检查失败: {sys_error}")
                    
                    # 检查网络连接
                    try:
                        import urllib.request
                        urllib.request.urlopen('https://www.youtube.com', timeout=5)
                        logger.info("网络连接正常")
                    except Exception as net_error:
                        logger.error(f"网络连接检查失败: {net_error}")
                        # 尝试备用网络检查
                        try:
                            import socket
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(5)
                            result = sock.connect_ex(('8.8.8.8', 53))
                            sock.close()
                            if result == 0:
                                logger.info("DNS连接正常")
                            else:
                                logger.error("DNS连接失败")
                        except Exception as dns_error:
                            logger.error(f"DNS连接检查失败: {dns_error}")
                    
                    logger.error(f"错误输出详情: {'; '.join(error_lines) if error_lines else '无详细错误信息'}")

                    # 智能容错机制：检查是否为可恢复的错误且文件已基本下载完成
                    error_text = ' '.join(error_lines) if error_lines else ''

                    if is_recoverable_error(error_text):
                        logger.info("检测到可恢复的yt-dlp错误，尝试验证已下载的文件...")

                        # 检查临时目录中是否有视频文件
                        temp_path_for_check = Path(temp_dir)
                        files_in_temp = list(temp_path_for_check.glob('*')) if temp_path_for_check.exists() else []
                        video_files_in_temp = [f for f in files_in_temp if f.suffix in ['.mp4', '.webm', '.mkv'] and f.name != 'NA']

                        if video_files_in_temp:
                            downloaded_file_for_check = video_files_in_temp[0]
                            logger.info(f"找到已下载文件: {downloaded_file_for_check.name}")

                            # 验证文件完整性
                            validation_result = await validate_downloaded_file(downloaded_file_for_check)

                            if validation_result.get("valid", False):
                                file_size = validation_result.get("file_size", 0)
                                logger.warning(f"✓ yt-dlp虽然报错但文件验证通过: {file_size} bytes")
                                logger.warning("忽略yt-dlp返回码错误，继续处理...")

                                # 跳过错误抛出，继续执行后续处理逻辑
                                download_succeeded_with_recovery = True
                            else:
                                logger.error(f"✗ 文件验证失败: {validation_result.get('reason', '未知原因')}")
                                download_succeeded_with_recovery = False
                        else:
                            logger.error("未找到已下载的视频文件")
                            download_succeeded_with_recovery = False
                    else:
                        logger.error("错误类型不可恢复，抛出异常")
                        download_succeeded_with_recovery = False

                    # 如果容错失败，则抛出异常
                    if not download_succeeded_with_recovery:
                        error_msg = f"yt-dlp下载失败，返回码: {process.returncode}"
                        if error_lines:
                            error_msg += f"\n错误详情: {'; '.join(error_lines)}"

                        logger.error(error_msg)
                        raise Exception(error_msg)
                
                if download_succeeded_with_recovery:
                    logger.warning("yt-dlp下载通过容错机制完成")
                else:
                    logger.info("yt-dlp下载完成")

                # 查找下载的文件
                files = list(temp_path.glob('*'))
                video_files = [f for f in files if f.suffix in ['.mp4', '.webm', '.mkv'] and f.name != 'NA']
                info_files = [f for f in files if f.suffix == '.json']
                thumbnail_files = [f for f in files if f.suffix in ['.jpg', '.webp', '.png']]
                
                if not video_files:
                    raise Exception("未找到下载的视频文件")

                downloaded_file = video_files[0]
                info_file = info_files[0] if info_files else None
                thumbnail_file = thumbnail_files[0] if thumbnail_files else None

                # 如果是通过容错机制完成的，再次验证文件
                if download_succeeded_with_recovery:
                    logger.info("容错机制：对下载文件进行最终验证")
                    final_validation = await validate_downloaded_file(downloaded_file)
                    if not final_validation.get("valid", False):
                        logger.error(f"容错下载的文件最终验证失败: {final_validation.get('reason', '未知原因')}")
                        raise Exception("容错下载的文件验证失败")
                
                # 读取info.json获取信息
                if info_file and info_file.exists():
                    import json
                    with open(info_file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                else:
                    # 从文件名提取信息
                    info = {
                        'id': downloaded_file.stem,
                        'title': downloaded_file.stem,
                        'duration': 0,
                        'uploader': 'Unknown',
                        'upload_date': '20250101',
                        'view_count': 0,
                        'ext': downloaded_file.suffix[1:]
                    }
                
                logger.info(f"下载完成: {downloaded_file.name}, 大小: {downloaded_file.stat().st_size} bytes")
                
                # 上传到MinIO
                video_filename = f"{info['id']}.{info['ext']}"
                video_object_name = minio_service.generate_object_name(
                    user_id, project_id, video_filename
                )
                
                logger.info(f"开始上传到MinIO: {video_object_name}")
                video_url = await minio_service.upload_file(
                    str(downloaded_file),
                    video_object_name,
                    f"video/{info['ext']}"
                )
                logger.info(f"上传完成: {video_url}")
                
                # 验证文件是否上传成功
                file_exists = await minio_service.file_exists(video_object_name)
                if file_exists:
                    logger.info(f"✓ 验证文件存在: {video_object_name}")
                else:
                    logger.error(f"✗ 文件上传后验证失败: {video_object_name}")
                    raise Exception(f"文件上传验证失败: {video_object_name}")
                
                # 上传缩略图
                thumbnail_url = None
                if thumbnail_file and thumbnail_file.exists():
                    thumbnail_object_name = minio_service.generate_thumbnail_object_name(
                        user_id, project_id, info['id']
                    )
                    uploaded_thumbnail = await minio_service.upload_file(
                        str(thumbnail_file),
                        thumbnail_object_name,
                        "image/jpeg" if thumbnail_file.suffix == '.jpg' else f"image/{thumbnail_file.suffix[1:]}"
                    )
                    if uploaded_thumbnail:
                        # 生成缩略图的预签名URL
                        thumbnail_url = await minio_service.get_file_url(
                            thumbnail_object_name,
                            expiry=86400  # 24小时有效期
                        )
                
                # 上传信息文件
                info_url = None
                if info_file and info_file.exists():
                    info_object_name = f"users/{user_id}/projects/{project_id}/info/{info['id']}.json"
                    info_url = await minio_service.upload_file(
                        str(info_file),
                        info_object_name,
                        "application/json"
                    )
                
                return {
                    'success': True,
                    'video_id': info['id'],
                    'title': info.get('title', 'Unknown'),
                    'filename': video_filename,
                    'minio_path': video_url,
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', '20250101'),
                    'view_count': info.get('view_count', 0),
                    'filesize': downloaded_file.stat().st_size,
                    'thumbnail_url': thumbnail_url or info.get('thumbnail'),
                    'info_url': info_url,
                    'video_ext': info['ext']
                }
                
            except Exception as e:
                logger.error(f"命令行下载失败: {str(e)}", exc_info=True)
                raise Exception(f"命令行下载失败: {str(e)}")
    
    async def download_and_upload_audio(
        self, 
        url: str, 
        project_id: int, 
        user_id: int,
        format_id: str = 'bestaudio'
    ) -> Dict[str, Any]:
        """下载音频并上传到MinIO"""
        
        # 获取视频信息
        video_info = await self.get_video_info(url)
        video_id = video_info['video_id']
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 设置下载选项
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': str(temp_path / '%(id)s.%(ext)s'),
                'noplaylist': True,
                'writeinfojson': True,
                'no_warnings': True,
                'quiet': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            if self.cookies_file and os.path.exists(self.cookies_file):
                ydl_opts['cookiefile'] = self.cookies_file
            
            try:
                # 下载音频到临时目录
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # 获取输出的音频文件（应该是mp3）
                    audio_file = temp_path / f"{info['id']}.mp3"
                    info_file = temp_path / f"{info['id']}.info.json"
                    
                    if not audio_file.exists():
                        # 尝试查找实际的输出文件
                        for file in temp_path.iterdir():
                            if file.suffix == '.mp3' and file.stem == info['id']:
                                audio_file = file
                                break
                        else:
                            raise Exception("音频文件未找到")
                    
                    # 上传到MinIO
                    audio_object_name = minio_service.generate_audio_object_name(
                        user_id, project_id, info['id']
                    )
                    
                    audio_url = await minio_service.upload_file(
                        str(audio_file),
                        audio_object_name,
                        "audio/mpeg"
                    )
                    
                    if not audio_url:
                        raise Exception("上传到MinIO失败")
                    
                    return {
                        'success': True,
                        'video_id': info['id'],
                        'title': info['title'],
                        'filename': audio_file.name,
                        'minio_path': audio_url,
                        'duration': info['duration'],
                        'filesize': audio_file.stat().st_size,
                        'audio_ext': 'mp3'
                    }
                    
            except Exception as e:
                raise Exception(f"音频下载和上传失败: {str(e)}")

# 全局实例
downloader_minio = YouTubeDownloaderMinio(
    cookies_file=settings.youtube_cookies_file
)