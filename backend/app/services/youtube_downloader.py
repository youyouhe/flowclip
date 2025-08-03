import yt_dlp
import os
import aiofiles
from typing import Dict, Any, Optional
import asyncio
from pathlib import Path

class YouTubeDownloader:
    def __init__(self, download_dir: str = "./downloads", cookies_file: str = None):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = cookies_file
        
        # Debug logging
        if self.cookies_file and os.path.exists(self.cookies_file):
            print(f"Using cookies file: {self.cookies_file}")
        else:
            print(f"Cookies file not found: {self.cookies_file}")
    
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
                    'filesize': info.get('filesize_approx')
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
    
    async def download_video(self, url: str, project_id: int, user_id: int, 
                           format_id: str = 'best', output_dir: Optional[str] = None) -> Dict[str, Any]:
        """下载视频"""
        if output_dir is None:
            output_dir = self.download_dir / str(user_id) / str(project_id)
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"%(id)s.%(ext)s"
        output_path = output_dir / filename
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
            'noplaylist': True,
            'writeinfojson': True,
            'writethumbnail': True,
            'no_warnings': True,
            'quiet': True,
        }
        
        if self.cookies_file and os.path.exists(self.cookies_file):
            ydl_opts['cookiefile'] = self.cookies_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # 获取实际下载的文件路径
                downloaded_file = output_dir / f"{info['id']}.{info['ext']}"
                thumbnail_file = output_dir / f"{info['id']}.jpg"
                info_file = output_dir / f"{info['id']}.info.json"
                
                return {
                    'success': True,
                    'video_id': info['id'],
                    'title': info['title'],
                    'filename': downloaded_file.name,
                    'filepath': str(downloaded_file),
                    'duration': info['duration'],
                    'uploader': info['uploader'],
                    'upload_date': info['upload_date'],
                    'view_count': info['view_count'],
                    'filesize': downloaded_file.stat().st_size if downloaded_file.exists() else 0,
                    'thumbnail': str(thumbnail_file) if thumbnail_file.exists() else None,
                    'info_file': str(info_file) if info_file.exists() else None
                }
        except Exception as e:
            raise Exception(f"下载视频失败: {str(e)}")
    
    async def download_audio_only(self, url: str, project_id: int, user_id: int,
                                format_id: str = 'bestaudio') -> Dict[str, Any]:
        """仅下载音频"""
        output_dir = self.download_dir / str(user_id) / str(project_id) / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
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
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                audio_file = output_dir / f"{info['id']}.mp3"
                info_file = output_dir / f"{info['id']}.info.json"
                
                return {
                    'success': True,
                    'video_id': info['id'],
                    'title': info['title'],
                    'filename': audio_file.name,
                    'filepath': str(audio_file),
                    'duration': info['duration'],
                    'filesize': audio_file.stat().st_size if audio_file.exists() else 0,
                    'info_file': str(info_file) if info_file.exists() else None
                }
        except Exception as e:
            raise Exception(f"下载音频失败: {str(e)}")

from app.core.config import settings
from app.services.minio_client import minio_service

# 全局实例
downloader = YouTubeDownloader(
    cookies_file=settings.youtube_cookies_file
)