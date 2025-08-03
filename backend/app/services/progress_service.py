import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask
from app.models.user import User
from app.core.database import get_db

logger = logging.getLogger(__name__)

# 全局进度服务实例
_progress_service = None

def get_progress_service() -> 'ProgressUpdateService':
    """获取进度服务实例"""
    global _progress_service
    if _progress_service is None:
        _progress_service = ProgressUpdateService()
        # 启动服务
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环已经在运行，创建任务来启动服务
                loop.create_task(_progress_service.start())
            else:
                # 否则直接运行
                loop.run_until_complete(_progress_service.start())
        except Exception as e:
            logger.error(f"启动进度服务失败: {e}")
    return _progress_service

class ProgressUpdateService:
    """进度更新服务"""
    
    def __init__(self):
        self._update_queue = asyncio.Queue()
        self._running = False
    
    async def start(self):
        """启动进度更新服务"""
        if self._running:
            return
        
        self._running = True
        logger.info("进度更新服务已启动")
        
        # 启动后台任务处理器
        asyncio.create_task(self._process_updates())
    
    async def stop(self):
        """停止进度更新服务"""
        self._running = False
        logger.info("进度更新服务已停止")
    
    async def _process_updates(self):
        """处理进度更新队列"""
        while self._running:
            try:
                # 从队列获取更新任务，如果没有则等待
                update_task = await self._update_queue.get()
                
                # 处理更新
                await self._handle_update(update_task)
                
            except Exception as e:
                logger.error(f"处理进度更新失败: {str(e)}")
    
    async def _handle_update(self, update_task: Dict[str, Any]):
        """处理单个更新任务"""
        try:
            video_id = update_task['video_id']
            user_id = update_task['user_id']
            progress_data = update_task['data']
            
            # 更新数据库
            updated_video = await self._update_database(video_id, progress_data)
            
            # 获取最新视频状态并发送WebSocket通知
            try:
                from app.api.v1.websocket import notify_progress_update
                
                if updated_video:
                    # 构建最新进度消息
                    latest_progress_data = {
                        "video_status": updated_video.status,
                        "download_progress": updated_video.download_progress or 0,
                        "processing_progress": updated_video.processing_progress or 0,
                        "processing_stage": updated_video.processing_stage or "",
                        "processing_message": updated_video.processing_message or "",
                    }
                    await notify_progress_update(video_id, user_id, latest_progress_data)
                    logger.debug(f"WebSocket通知已发送 - video_id: {video_id}, status: {updated_video.status}")
                else:
                    logger.warning(f"视频 {video_id} 未找到，无法发送WebSocket通知")
            except ImportError:
                logger.debug("WebSocket通知功能不可用，跳过实时通知")
            except Exception as e:
                logger.warning(f"WebSocket通知失败: {e}")
            
        except Exception as e:
            logger.error(f"处理进度更新任务失败: {str(e)}")
    
    async def _update_database(self, video_id: int, progress_data: Dict[str, Any]):
        """更新数据库中的进度信息并立即获取最新状态"""
        try:
            from app.core.database import AsyncSessionLocal
            from app.api.v1.websocket import notify_progress_update # Import here to avoid circular dependency
            
            async with AsyncSessionLocal() as db:
                # 更新视频进度
                stmt = select(Video).where(Video.id == video_id)
                result = await db.execute(stmt)
                video = result.scalar_one_or_none()
                
                if video:
                    if 'download_progress' in progress_data:
                        video.download_progress = progress_data['download_progress']
                    
                    if 'processing_progress' in progress_data:
                        video.processing_progress = progress_data['processing_progress']
                    
                    if 'processing_stage' in progress_data:
                        video.processing_stage = progress_data['processing_stage']
                    
                    if 'processing_message' in progress_data:
                        video.processing_message = progress_data['processing_message']
                    
                    if 'status' in progress_data:
                        video.status = progress_data['status']
                    
                    await db.commit()
                    logger.debug(f"数据库进度已更新 - video_id: {video_id}")
                    await db.refresh(video) # Ensure video object is refreshed after commit
                    return video # Return the updated video object
            return None # Return None if video not found
        except Exception as e:
            logger.error(f"更新数据库进度失败: {str(e)}")
            return None
    
    async def update_progress(
        self,
        video_id: int,
        user_id: int,
        progress_data: Dict[str, Any]
    ):
        """更新进度"""
        try:
            # 将更新任务放入队列
            await self._update_queue.put({
                'video_id': video_id,
                'user_id': user_id,
                'data': progress_data
            })
            
            logger.debug(f"进度更新已加入队列 - video_id: {video_id}")
            
        except Exception as e:
            logger.error(f"加入进度更新队列失败: {str(e)}")
    
    def queue_update(
        self,
        video_id: int,
        user_id: int,
        progress_data: Dict[str, Any]
    ):
        """同步版本的进度更新 - 用于Celery任务"""
        try:
            # 将更新任务放入队列
            asyncio.run(self._update_queue.put({
                'video_id': video_id,
                'user_id': user_id,
                'data': progress_data
            }))
            
            logger.debug(f"进度更新已加入队列 (sync) - video_id: {video_id}")
            
        except Exception as e:
            logger.error(f"加入进度更新队列失败 (sync): {str(e)}")
    
    async def update_task_progress(
        self,
        task_id: int,
        progress_data: Dict[str, Any]
    ):
        """更新处理任务进度"""
        try:
            from app.core.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                # 获取处理任务
                stmt = select(ProcessingTask).where(ProcessingTask.id == task_id)
                result = await db.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    # 更新任务进度
                    if 'progress' in progress_data:
                        task.progress = progress_data['progress']
                    
                    if 'stage' in progress_data:
                        task.stage = progress_data['stage']
                    
                    if 'message' in progress_data:
                        task.message = progress_data['message']
                    
                    if 'status' in progress_data:
                        task.status = progress_data['status']
                    
                    await db.commit()
                    
                    # 同时更新视频进度
                    await self.update_progress(
                        task.video_id,
                        task.user_id,
                        progress_data
                    )
                    
                    logger.debug(f"任务进度已更新 - task_id: {task_id}")
            
        except Exception as e:
            logger.error(f"更新任务进度失败: {str(e)}")

# 全局实例
progress_service = ProgressUpdateService()

# 便捷函数
async def update_video_progress(video_id: int, user_id: int, progress_data: Dict[str, Any]):
    """更新视频进度"""
    await progress_service.update_progress(video_id, user_id, progress_data)

async def update_task_progress(task_id: int, progress_data: Dict[str, Any]):
    """更新任务进度"""
    await progress_service.update_task_progress(task_id, progress_data)
