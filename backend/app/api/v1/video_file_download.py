from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re
import urllib.parse
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.services.minio_client import minio_service

router = APIRouter()

import logging
logger = logging.getLogger(__name__)


@router.get("/{video_id}/audio-download-url")
async def get_audio_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取音频文件的预签名下载URL"""
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # 构建音频文件对象名称
    audio_object_name = f"users/{current_user.id}/projects/{video.project_id}/audio/{video.id}.wav"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(audio_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found"
        )
    
    # 生成预签名URL
    url = await minio_service.get_file_url(audio_object_name, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate audio download URL"
        )
    
    # 从处理元数据中获取音频时长
    duration = 0
    if video.processing_metadata and video.processing_metadata.get('audio_info'):
        audio_info = video.processing_metadata.get('audio_info', {})
        duration = audio_info.get('duration', 0)
    
    return {
        "download_url": url, 
        "expires_in": expiry, 
        "object_name": audio_object_name,
        "duration": duration,
        "content_type": "audio/wav"
    }


@router.get("/{video_id}/srt-download-url")
async def get_srt_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取SRT字幕文件的预签名下载URL"""
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # 构建SRT文件对象名称
    srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(srt_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT file not found"
        )
    
    # 生成预签名URL
    url = await minio_service.get_file_url(srt_object_name, expiry)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate SRT download URL"
        )
    
    return {
        "download_url": url, 
        "expires_in": expiry, 
        "object_name": srt_object_name,
        "content_type": "text/plain; charset=utf-8"
    }


@router.get("/{video_id}/srt-download")
async def download_srt_direct(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """直接下载SRT文件，确保正确的UTF-8编码"""
    logger.info(f"=== SRT下载请求开始 ===")
    logger.info(f"用户ID: {current_user.id}, 视频ID: {video_id}")
    
    try:
        # 验证视频属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            logger.error(f"视频未找到: video_id={video_id}, user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        logger.info(f"找到视频: {video.title} (ID: {video.id})")
        
        # 构建SRT文件对象名称
        srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
        logger.info(f"SRT对象名称: {srt_object_name}")
        
        # 检查文件是否存在
        file_exists = await minio_service.file_exists(srt_object_name)
        if not file_exists:
            logger.error(f"SRT文件不存在: {srt_object_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SRT file not found"
            )
        
        logger.info(f"SRT文件存在: {srt_object_name}")
        
        # 获取文件内容
        try:
            response = minio_service.internal_client.get_object(
                settings.minio_bucket_name, 
                srt_object_name
            )
            content = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"成功读取SRT文件, 大小: {len(content)} 字节")
            
            # 确保内容以UTF-8编码返回
            from fastapi.responses import StreamingResponse
            import io
            
            try:
                # 直接使用UTF-8解码，因为SRT文件应该是UTF-8编码的
                try:
                    logger.info("尝试UTF-8解码SRT内容")
                    text_content = content.decode('utf-8')
                    # 检查是否已经包含BOM，如果包含则直接使用，否则添加
                    if text_content.startswith('\ufeff'):
                        utf8_content = text_content.encode('utf-8')
                        logger.info("SRT内容已包含BOM")
                    else:
                        utf8_content = text_content.encode('utf-8-sig')  # 带BOM的UTF-8
                        logger.info("添加UTF-8 BOM到SRT内容")
                    logger.info(f"成功解码UTF-8内容，长度: {len(text_content)} 字符")
                except UnicodeDecodeError as e:
                    logger.error(f"UTF-8解码失败，尝试GBK: {str(e)}")
                    try:
                        text_content = content.decode('gbk')
                        utf8_content = text_content.encode('utf-8-sig')
                        logger.info("使用GBK解码成功")
                    except UnicodeDecodeError as e2:
                        logger.error(f"GBK解码也失败，使用Latin-1: {str(e2)}")
                        text_content = content.decode('latin-1')
                        utf8_content = text_content.encode('utf-8-sig')
                        logger.info("使用Latin-1解码作为最后手段")
                
                # 安全处理文件名中的特殊字符 - 使用URL编码处理中文
                safe_filename = urllib.parse.quote(video.title.replace(' ', '_').replace('/', '_').replace('\\', '_'), safe='')
                
                logger.info(f"准备返回SRT文件, 内容长度: {len(utf8_content)} 字节")
                
                return StreamingResponse(
                    io.BytesIO(utf8_content),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}.srt",
                        "Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-cache",
                    }
                )
                
            except UnicodeDecodeError as e:
                logger.error(f"Unicode解码错误: {str(e)}")
                # 如果解码失败，尝试用更宽松的方式处理
                text_content = content.decode('utf-8', errors='replace')
                utf8_content = text_content.encode('utf-8-sig')
                
                safe_filename = urllib.parse.quote(video.title.replace(' ', '_').replace('/', '_').replace('\\', '_'), safe='')
                
                return StreamingResponse(
                    io.BytesIO(utf8_content),
                    media_type="text/plain; charset=utf-8",
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}.srt",
                        "Content-Type": "text/plain; charset=utf-8",
                        "Cache-Control": "no-cache",
                    }
                )
            except Exception as e:
                logger.error(f"SRT内容处理错误: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"从MinIO获取文件错误: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read SRT content: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SRT下载处理错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}"
        )


@router.get("/{video_id}/srt-content")
async def get_srt_content(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取SRT字幕文件内容用于预览"""
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # 构建SRT文件对象名称
    srt_object_name = f"users/{current_user.id}/projects/{video.project_id}/subtitles/{video.id}.srt"
    
    # 检查文件是否存在
    file_exists = await minio_service.file_exists(srt_object_name)
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT file not found"
        )
    
    # 获取文件内容
    try:
        response = minio_service.internal_client.get_object(
            settings.minio_bucket_name, 
            srt_object_name
        )
        content_bytes = response.read()
        response.close()
        response.release_conn()
        
        # 尝试多种编码解码字节内容
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode('gbk')
                except UnicodeDecodeError:
                    content = content_bytes.decode('latin-1')
        
        # 解析SRT内容
        import re
        subtitles = []
        
        # 按字幕块分割
        blocks = re.split(r'\n\s*\n', content.strip())
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                subtitle = {
                    'id': lines[0],
                    'time': lines[1],
                    'text': '\n'.join(lines[2:])
                }
                subtitles.append(subtitle)
        
        return {
            "content": content,
            "subtitles": subtitles,
            "total_subtitles": len(subtitles),
            "file_size": len(content.encode('utf-8'))
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read SRT content: {str(e)}"
        )


@router.get("/{video_id}/thumbnail-download-url")
async def get_thumbnail_download_url(
    video_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取缩略图的预签名下载URL"""
    
    # 验证视频属于当前用户
    stmt = select(Video).join(Project).where(
        Video.id == video_id,
        Project.user_id == current_user.id
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # 如果视频ID为空，返回错误
    if not video.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video URL is empty"
        )
    
    # 从YouTube URL中提取视频ID
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', video.url)
    if not video_id_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL"
        )
    
    youtube_video_id = video_id_match.group(1)
    
    # 生成缩略图对象名称
    thumbnail_object_name = minio_service.generate_thumbnail_object_name(
        current_user.id, 
        video.project_id, 
        youtube_video_id
    )
    
    # 检查缩略图是否存在
    thumbnail_exists = await minio_service.file_exists(thumbnail_object_name)
    if not thumbnail_exists:
        # 如果缩略图不存在，返回原始YouTube缩略图URL
        if video.thumbnail_url:
            return {"download_url": video.thumbnail_url, "expires_in": expiry, "object_name": None}
        else:
            # 如果也没有原始缩略图，返回默认缩略图
            default_thumbnail = f"https://img.youtube.com/vi/{youtube_video_id}/default.jpg"
            return {"download_url": default_thumbnail, "expires_in": expiry, "object_name": None}
    
    # 生成预签名URL
    url = await minio_service.get_file_url(thumbnail_object_name, expiry)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate thumbnail download URL"
        )
    
    return {"download_url": url, "expires_in": expiry, "object_name": thumbnail_object_name}


@router.get("/{video_id}/video-download")
async def download_video_direct(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """直接下载视频文件，通过后端代理避免MinIO直链问题"""
    # 在执行下载前重新加载MinIO配置，确保使用最新的访问密钥
    try:
        from app.services.system_config_service import SystemConfigService
        from app.core.database import get_sync_db
        
        # 重新加载系统配置
        db_sync = get_sync_db()
        SystemConfigService.update_settings_from_db_sync(db_sync)
        db_sync.close()
        
        # 重新加载MinIO客户端配置
        minio_service.reload_config()
        
        logger.info("已重新加载MinIO配置")
    except Exception as config_error:
        logger.error(f"重新加载MinIO配置失败: {config_error}")
    
    logger.info(f"=== 视频下载请求开始 ===")
    logger.info(f"用户ID: {current_user.id}, 视频ID: {video_id}")
    
    try:
        # 验证视频属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            logger.error(f"视频未找到: video_id={video_id}, user_id={current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        logger.info(f"找到视频: {video.title} (ID: {video.id})")
        
        # 检查视频文件是否存在
        if not video.file_path:
            logger.error(f"视频文件路径为空: video_id={video_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not available"
            )
        
        # 从MinIO获取文件流
        file_stream = await minio_service.get_file_stream(video.file_path)
        if not file_stream:
            logger.error(f"无法从MinIO获取文件流: {video.file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found in storage"
            )
        
        # 获取文件信息
        file_stat = await minio_service.get_file_stat(video.file_path)
        if not file_stat:
            logger.error(f"无法获取文件统计信息: {video.file_path}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get file information"
            )
        
        logger.info(f"开始下载视频文件: {video.file_path}, 大小: {file_stat.size} bytes")
        
        # 返回文件流响应
        from fastapi.responses import StreamingResponse
        import io
        
        # 创建文件流生成器
        async def file_stream_generator():
            try:
                # 分块读取文件
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = file_stream.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                file_stream.close()
        
        # 确定内容类型
        content_type = "video/mp4"  # 默认
        if video.filename:
            if video.filename.endswith('.webm'):
                content_type = "video/webm"
            elif video.filename.endswith('.mkv'):
                content_type = "video/x-matroska"
            elif video.filename.endswith('.avi'):
                content_type = "video/x-msvideo"
            elif video.filename.endswith('.mov'):
                content_type = "video/quicktime"
        
        # 设置下载文件名
        download_filename = video.filename or f"{video.title}.mp4"
        
        logger.info(f"返回视频文件流: {download_filename}, 内容类型: {content_type}")
        
        return StreamingResponse(
            file_stream_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{download_filename}",
                "Content-Length": str(file_stat.size),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"视频下载失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video download failed: {str(e)}"
        )