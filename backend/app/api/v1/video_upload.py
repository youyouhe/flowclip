from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask
from app.schemas.video import VideoResponse
from app.core.constants import ProcessingTaskType
from app.core.celery import celery_app
from app.services.state_manager import get_state_manager

router = APIRouter()

import logging
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    project_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传视频文件，支持后台上传"""
    logger.info(f"开始视频上传 - user_id: {current_user.id}, project_id: {project_id}, filename: {file.filename}")
    
    try:
        # 验证项目属于当前用户
        stmt = select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 验证文件类型
        allowed_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_extension}. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # 验证文件大小（限制为6GB）
        max_file_size = 6 * 1024 * 1024 * 1024  # 6GB
        logger.info(f"开始读取上传文件内容，最大允许大小: {max_file_size} bytes")
        
        # 分块读取文件以避免内存问题，并实时监控进度
        content = bytearray()
        chunk_size = 8192  # 8KB chunks
        total_read = 0
        
        # 读取文件内容并监控进度
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            content.extend(chunk)
            total_read += len(chunk)
            
            # 检查是否超过最大文件大小
            if total_read > max_file_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large. Maximum size: {max_file_size / (1024*1024*1024):.1f}GB"
                )
            
            # 每读取10MB记录一次日志
            if total_read % (10 * 1024 * 1024) == 0:
                logger.info(f"已读取文件内容: {total_read / (1024*1024):.1f}MB")
        
        file_size = len(content)
        logger.info(f"文件读取完成，总大小: {file_size / (1024*1024):.1f}MB")
        
        # 重置文件指针到开始位置，以便后续读取
        await file.seek(0)
        
        # 创建视频记录
        new_video = Video(
            title=title,
            description=description,
            url="upload://local",  # 标记为本地上传
            project_id=project_id,
            filename=file.filename,
            status="pending",
            download_progress=0.0,
            file_size=file_size  # 立即设置文件大小
        )
        
        db.add(new_video)
        await db.commit()
        await db.refresh(new_video)
        logger.info(f"已创建视频记录: video_id={new_video.id}")
        
        # 创建临时文件目录
        temp_dir = f"/tmp/uploads/{current_user.id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{new_video.id}_{file.filename}")
        logger.info(f"准备保存文件到临时位置: {temp_path}")
        
        # 保存文件到临时位置
        try:
            with open(temp_path, "wb") as buffer:
                buffer.write(content)
            
            logger.info(f"文件已保存到临时位置: {temp_path}, 大小: {file_size} bytes")
            
        except Exception as e:
            logger.error(f"保存临时文件失败: {str(e)}")
            # 清理视频记录
            await db.delete(new_video)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save uploaded file: {str(e)}"
            )
        
        # 启动Celery后台上传任务
        try:
            from app.tasks.video_tasks import upload_video as celery_upload_video
            
            logger.info(f"准备启动Celery上传任务: video_id={new_video.id}")
            task = celery_app.send_task('app.tasks.video_tasks.upload_video', 
                args=[new_video.id, project_id, current_user.id, temp_path]
            )
            
            # 创建处理任务记录
            state_manager = get_state_manager(db)
            processing_task = await state_manager.create_processing_task(
                video_id=new_video.id,
                task_type=ProcessingTaskType.DOWNLOAD,  # 复用DOWNLOAD类型
                task_name="视频上传",
                celery_task_id=task.id,
                input_data={"temp_path": temp_path, "filename": file.filename}
            )
            
            await db.commit()
            
            logger.info(f"Celery上传任务已启动 - task_id: {task.id}, processing_task_id: {processing_task.id}")
            
        except Exception as e:
            logger.error(f"启动Celery上传任务失败: {str(e)}")
            # 清理临时文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.info(f"已清理临时文件: {temp_path}")
                except Exception as cleanup_error:
                    logger.error(f"清理临时文件失败: {cleanup_error}")
            # 清理视频记录
            await db.delete(new_video)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start upload task: {str(e)}"
            )
        
        # 返回响应
        video_dict = {
            'id': new_video.id,
            'title': new_video.title,
            'description': new_video.description,
            'url': new_video.url,
            'project_id': new_video.project_id,
            'filename': new_video.filename,
            'file_path': new_video.file_path,
            'duration': new_video.duration,
            'file_size': new_video.file_size,
            'thumbnail_url': new_video.thumbnail_url,
            'status': new_video.status,
            'download_progress': new_video.download_progress,
            'created_at': new_video.created_at,
            'updated_at': new_video.updated_at,
            'project_name': project.name
        }
        
        logger.info(f"视频上传请求处理完成: video_id={new_video.id}, task_id={task.id}")
        return {
            "video": video_dict,
            "task_id": task.id,
            "processing_task_id": processing_task.id,
            "message": "Video upload started successfully",
            "status": "processing"
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"视频上传处理失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video upload failed: {str(e)}"
        )


@router.post("/upload-chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    chunkIndex: int = Form(...),
    totalChunks: int = Form(...),
    fileName: str = Form(...),
    fileSize: int = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    project_id: int = Form(...),
    video_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """分块上传视频文件"""
    logger.info(f"开始分块上传 - user_id: {current_user.id}, project_id: {project_id}, filename: {fileName}, chunk: {chunkIndex+1}/{totalChunks}")
    
    try:
        # 验证项目属于当前用户
        stmt = select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 创建临时文件目录
        temp_dir = f"/tmp/uploads/{current_user.id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # 如果是第一个分块，创建视频记录
        new_video = None
        if chunkIndex == 0 and not video_id:
            # 创建视频记录
            new_video = Video(
                title=title if title else os.path.splitext(fileName)[0],
                description=description,
                url="upload://local",  # 标记为本地上传
                project_id=project_id,
                filename=fileName,
                status="pending",
                download_progress=0.0,
                file_size=fileSize
            )
            
            db.add(new_video)
            await db.commit()
            await db.refresh(new_video)
            video_id = new_video.id
            logger.info(f"已创建视频记录: video_id={video_id}")
        elif not video_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing video_id for chunked upload"
            )
        
        # 保存分块到临时文件
        chunk_dir = os.path.join(temp_dir, f"video_{video_id}_chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path = os.path.join(chunk_dir, f"chunk_{chunkIndex}")
        
        # 保存分块内容
        content = await chunk.read()
        with open(chunk_path, "wb") as f:
            f.write(content)
        
        logger.info(f"分块保存成功: {chunk_path}, 大小: {len(content)} bytes")
        
        # 如果是最后一个分块，合并所有分块
        if chunkIndex == totalChunks - 1:
            logger.info(f"最后一个分块，开始合并文件: video_id={video_id}")
            
            # 获取视频记录
            if not new_video:
                stmt = select(Video).where(Video.id == video_id)
                result = await db.execute(stmt)
                new_video = result.scalar_one_or_none()
                if not new_video:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Video not found"
                    )
            
            # 合并所有分块
            final_temp_path = os.path.join(temp_dir, f"{video_id}_{fileName}")
            with open(final_temp_path, "wb") as outfile:
                for i in range(totalChunks):
                    chunk_file = os.path.join(chunk_dir, f"chunk_{i}")
                    if os.path.exists(chunk_file):
                        with open(chunk_file, "rb") as infile:
                            outfile.write(infile.read())
                        # 删除已合并的分块
                        os.remove(chunk_file)
            
            # 删除分块目录
            os.rmdir(chunk_dir)
            
            logger.info(f"文件合并完成: {final_temp_path}, 大小: {os.path.getsize(final_temp_path)} bytes")
            
            # 启动Celery后台上传任务
            try:
                logger.info(f"准备启动Celery上传任务: video_id={video_id}")
                task = celery_app.send_task('app.tasks.video_tasks.upload_video', 
                    args=[video_id, project_id, current_user.id, final_temp_path]
                )
                logger.info(f"Celery任务发送完成: task_id={task.id}")
                
                # 更新视频状态
                new_video.status = "processing"
                new_video.download_progress = 10.0
                logger.info("准备提交数据库更新")
                await db.commit()
                await db.refresh(new_video)  # 刷新对象以确保所有属性都已加载
                logger.info("数据库更新提交完成")
                
                logger.info(f"Celery上传任务已启动 - task_id: {task.id}")
                
                # 返回响应
                video_dict = {
                    'id': new_video.id,
                    'title': new_video.title,
                    'description': new_video.description,
                    'url': new_video.url,
                    'project_id': new_video.project_id,
                    'filename': new_video.filename,
                    'file_path': new_video.file_path,
                    'duration': new_video.duration,
                    'file_size': new_video.file_size,
                    'thumbnail_url': new_video.thumbnail_url,
                    'status': new_video.status,
                    'download_progress': new_video.download_progress,
                    'created_at': new_video.created_at,
                    'updated_at': new_video.updated_at,
                    'project_name': project.name
                }
                
                logger.info(f"分块上传处理完成: video_id={video_id}, task_id={task.id}")
                return {
                    "video": video_dict,
                    "task_id": task.id,
                    "message": "Video upload started successfully",
                    "status": "processing",
                    "completed": True
                }
                
            except Exception as e:
                logger.error(f"启动Celery上传任务失败: {str(e)}", exc_info=True)
                # 清理临时文件
                if os.path.exists(final_temp_path):
                    try:
                        os.remove(final_temp_path)
                        logger.info(f"已清理临时文件: {final_temp_path}")
                    except Exception as cleanup_error:
                        logger.error(f"清理临时文件失败: {cleanup_error}")
                # 注意：在异常处理中不进行数据库操作以避免greenlet错误
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start upload task: {str(e)}"
                )
        
        # 如果不是最后一个分块，返回成功状态
        return {
            "message": f"Chunk {chunkIndex+1}/{totalChunks} uploaded successfully",
            "video_id": video_id,
            "completed": False
        }
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"分块上传处理失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chunk upload failed: {str(e)}"
        )