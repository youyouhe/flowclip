from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional
import json
import asyncio
from app.core.database import get_db, AsyncSessionLocal # Import AsyncSessionLocal
from app.core.security import get_current_user_from_token
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask
from app.services.state_manager import get_state_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConnectionManager:
    """管理WebSocket连接"""
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.last_sent_time: Dict[tuple, float] = {}  # (user_id, video_id) -> 上次发送时间
        self.pending_updates: Dict[tuple, Dict[str, Any]] = {}  # (user_id, video_id) -> 待发送数据
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket连接建立 - user_id: {user_id}")
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket连接断开 - user_id: {user_id}")
    
    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(message)
            except Exception as e:
                logger.error(f"发送消息失败 - user_id: {user_id}, error: {str(e)}")
                self.disconnect(user_id)
    
    async def broadcast_to_user(self, message: Dict[str, Any], user_id: int):
        """向特定用户广播消息"""
        await self.send_personal_message(json.dumps(message), user_id)
    
    async def send_throttled_progress(self, video_id: int, user_id: int, progress_data: Dict[str, Any]):
        """智能节流推送进度更新：关键状态变化立即推送，其他变化合并"""
        key = (user_id, video_id)
        now = asyncio.get_event_loop().time()
        last_sent = self.last_sent_time.get(key, 0)
        
        # 检查是否有状态变化
        is_status_change = False
        is_completion = False
        
        # 与待发送数据对比
        pending_data = self.pending_updates.get(key, {})
        
        # 状态变化或完成立即推送
        is_status_change = progress_data.get('video_status') != pending_data.get('video_status')
        is_completion = progress_data.get('status') == 'completed' or progress_data.get('download_progress') == 100
        progress_change = abs(progress_data.get('download_progress', 0) - pending_data.get('download_progress', 0))
        
        if is_status_change or is_completion or progress_change >= 10:  # 进度变化超过10%才推送
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = now
            # 清空待发送数据
            if key in self.pending_updates:
                del self.pending_updates[key]
        elif now - last_sent >= 30.0:  # 普通更新最多30秒间隔
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = now
            if key in self.pending_updates:
                del self.pending_updates[key]
        else:
            # 缓存最新数据
            self.pending_updates[key] = progress_data
    
    async def _schedule_delayed_send(self, key: tuple, video_id: int, user_id: int, scheduled_time: float):
        """延迟发送进度更新"""
        await asyncio.sleep(2.0)
        
        # 检查是否已经有更新的数据
        if key in self.pending_updates:
            progress_data = self.pending_updates[key]
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = asyncio.get_event_loop().time()
            del self.pending_updates[key]
    
    async def _send_progress_update(self, video_id: int, user_id: int, progress_data: Dict[str, Any]):
        """实际发送进度更新"""
        message = {
            "type": "progress_update",
            "video_id": video_id,
            "timestamp": asyncio.get_event_loop().time(),
            **progress_data
        }
        
        await self.send_personal_message(json.dumps(message), user_id)

manager = ConnectionManager()

@router.websocket("/ws/progress/{token}")
async def websocket_progress_endpoint(websocket: WebSocket, token: str): # Removed db dependency
    """WebSocket端点用于实时进度更新"""
    user_id: Optional[int] = None # Initialize user_id outside try block for finally
    try:
        async with AsyncSessionLocal() as db_session: # Manually manage session
            # 验证token
            user = await get_current_user_from_token(token=token, db=db_session) # Pass db_session
            
            if not user:
                await websocket.close(code=4001, reason="Invalid token")
                return
            
            user_id = user.id
            await manager.connect(websocket, user_id)
            
            try:
                while True:
                    # 保持连接活跃，等待客户端消息
                    data = await websocket.receive_text()
                    
                    # 处理客户端消息（例如订阅特定视频的进度）
                    try:
                        message = json.loads(data)
                        
                        if message.get('type') == 'subscribe':
                            # 订阅模式已废弃，返回确认消息
                            await websocket.send_text(json.dumps({
                                "type": "subscription_ack",
                                "message": "Subscription mode deprecated, using query mode instead"
                            }))
                        
                        elif message.get('type') == 'ping':
                            # 响应心跳
                            await websocket.send_text(json.dumps({"type": "pong"}))
                        
                        elif message.get('type') == 'request_status_update':
                            logger.info(f"收到来自用户 {user_id} 的状态更新请求")
                            
                            # 使用 consistent read 确保数据一致性
                            try:
                                # 开始一个新的事务，确保读取最新数据
                                await db_session.begin()
                                
                                # 获取该用户所有需要状态更新的视频
                                active_statuses = ["pending", "downloading", "processing", "completed"]
                                stmt = select(Video).where(
                                    Video.project_id.in_(
                                        select(Project.id).where(Project.user_id == user_id)
                                    ),
                                    Video.status.in_(active_statuses)
                                ).with_for_update()  # 使用 SELECT FOR UPDATE 锁定记录
                                
                                result = await db_session.execute(stmt)
                                active_videos = result.scalars().all()
                                
                                # Debug: 添加日志显示查询结果
                                logger.info(f"用户 {user_id} 的项目查询结果: {len(active_videos)} 个视频")
                                for video in active_videos:
                                    logger.info(f"视频 {video.id}: project_id={video.project_id}, status={video.status}")
                                
                                # 过滤掉真正完全完成的视频
                                videos_to_update = []
                                for video in active_videos:
                                    # 如果视频还在处理中，肯定要更新
                                    if video.status in ["pending", "downloading", "processing"]:
                                        videos_to_update.append(video)
                                    # 如果视频已下载完成，检查是否还有未完成的处理任务
                                    elif video.status == "completed":
                                        try:
                                            stmt = select(ProcessingTask).where(
                                                ProcessingTask.video_id == video.id,
                                                ProcessingTask.status.in_(['pending', 'running'])
                                            )
                                            result = await db_session.execute(stmt)
                                            active_tasks = result.scalars().all()
                                            
                                            # 如果还有活跃任务，需要更新
                                            if active_tasks:
                                                videos_to_update.append(video)
                                                logger.debug(f"视频 {video.id} 仍有活跃任务，需要状态更新")
                                            else:
                                                logger.debug(f"视频 {video.id} 已完全完成，跳过状态更新")
                                        except Exception as e:
                                            logger.warning(f"检查视频 {video.id} 的处理任务失败: {str(e)}")
                                            # 如果检查失败，为了安全起见还是更新
                                            videos_to_update.append(video)
                                
                                logger.info(f"用户 {user_id} 有 {len(videos_to_update)} 个视频需要状态更新")
                                
                                # 提交事务
                                await db_session.commit()
                                
                                for video in videos_to_update:
                                    # 为每个需要更新的视频发送当前进度状态
                                    await send_current_progress(websocket, video.id, user_id, db_session)
                                    
                            except Exception as e:
                                logger.error(f"状态更新查询失败: {str(e)}")
                                await db_session.rollback()
                                # 降级处理：直接查询不使用锁定
                                try:
                                    active_statuses = ["pending", "downloading", "processing", "completed"]
                                    stmt = select(Video).where(
                                        Video.project_id.in_(
                                            select(Project.id).where(Project.user_id == user_id)
                                        ),
                                        Video.status.in_(active_statuses)
                                    )
                                    result = await db_session.execute(stmt)
                                    active_videos = result.scalars().all()
                                    
                                    for video in active_videos:
                                        await send_current_progress(websocket, video.id, user_id, db_session)
                                except Exception as fallback_error:
                                    logger.error(f"降级查询也失败: {str(fallback_error)}")
                        
                    except json.JSONDecodeError:
                        logger.warning(f"收到无效的JSON消息: {data}")
                            
            except WebSocketDisconnect:
                manager.disconnect(user_id)
                logger.info(f"WebSocket断开连接 - user_id: {user_id}")
                
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
        if user_id is not None: # Check if user_id was successfully assigned
            manager.disconnect(user_id)

async def send_current_progress(websocket: WebSocket, video_id: int, user_id: int, db: AsyncSession):
    """发送当前进度状态 - 修复权限验证和状态同步，确保数据一致性"""
    try:
        # 使用 consistent read 读取最新数据
        try:
            await db.begin()
            
            # 检查视频是否存在，支持延迟创建的情况
            stmt = select(Video).where(Video.id == video_id).with_for_update()
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                await db.commit()
                # 可能是新创建的视频，直接返回空数据避免错误
                await websocket.send_text(json.dumps({
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": "",
                    "video_status": "pending",
                    "download_progress": 0,
                    "processing_progress": 0,
                    "processing_stage": "",
                    "processing_message": "等待处理...",
                    "tasks": []
                }))
                return
                
            # 验证用户权限
            stmt = select(Project.user_id).where(Project.id == video.project_id)
            result = await db.execute(stmt)
            project_user_id = result.scalar_one_or_none()
            
            if project_user_id != user_id:
                await db.commit()
                logger.warning(f"用户 {user_id} 尝试访问不属于自己的视频 {video_id}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Access denied"
                }))
                return
            
            # 重新查询最新视频状态，避免缓存问题
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                await db.commit()
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": "",
                    "video_status": "error",
                    "download_progress": 0,
                    "processing_progress": 0,
                    "processing_stage": "",
                    "processing_message": "Video not found",
                    "tasks": []
                }
            else:
                # 获取处理任务（单独查询确保最新）
                stmt = select(ProcessingTask).where(
                    ProcessingTask.video_id == video_id
                ).order_by(ProcessingTask.created_at.desc())
                result = await db.execute(stmt)
                tasks = result.scalars().all()
                
                # 构建最新进度消息
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": video.title,
                    "video_status": video.status,
                    "download_progress": video.download_progress or 0,
                    "processing_progress": video.processing_progress or 0,
                    "processing_stage": video.processing_stage or "",
                    "processing_message": video.processing_message or "",
                    "tasks": []
                }
                
                # Add task information
                for task in tasks:
                    task_data = {
                        "id": task.id,
                        "task_type": task.task_type,
                        "task_name": task.task_name,
                        "status": task.status,
                        "progress": task.progress,
                        "stage": task.stage,
                        "message": task.message,
                        "created_at": task.created_at.isoformat(),
                        "updated_at": task.updated_at.isoformat()
                    }
                    progress_data["tasks"].append(task_data)
            
            await db.commit()
            
        except Exception as transaction_error:
            await db.rollback()
            logger.error(f"事务查询失败，使用降级模式: {str(transaction_error)}")
            
            # 降级模式：不使用事务
            stmt = select(Video).where(Video.id == video_id)
            result = await db.execute(stmt)
            video = result.scalar_one_or_none()
            
            if not video:
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": "",
                    "video_status": "error",
                    "download_progress": 0,
                    "processing_progress": 0,
                    "processing_stage": "",
                    "processing_message": "Video not found",
                    "tasks": []
                }
            else:
                # 验证用户权限
                stmt = select(Project.user_id).where(Project.id == video.project_id)
                result = await db.execute(stmt)
                project_user_id = result.scalar_one_or_none()
                
                if project_user_id != user_id:
                    logger.warning(f"用户 {user_id} 尝试访问不属于自己的视频 {video_id}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Access denied"
                    }))
                    return
                
                # 获取处理任务
                stmt = select(ProcessingTask).where(
                    ProcessingTask.video_id == video_id
                ).order_by(ProcessingTask.created_at.desc())
                result = await db.execute(stmt)
                tasks = result.scalars().all()
                
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": video.title,
                    "video_status": video.status,
                    "download_progress": video.download_progress or 0,
                    "processing_progress": video.processing_progress or 0,
                    "processing_stage": video.processing_stage or "",
                    "processing_message": video.processing_message or "",
                    "tasks": []
                }
                
                for task in tasks:
                    task_data = {
                        "id": task.id,
                        "task_type": task.task_type,
                        "task_name": task.task_name,
                        "status": task.status,
                        "progress": task.progress,
                        "stage": task.stage,
                        "message": task.message,
                        "created_at": task.created_at.isoformat(),
                        "updated_at": task.updated_at.isoformat()
                    }
                    progress_data["tasks"].append(task_data)
        
        await websocket.send_text(json.dumps(progress_data))
        
    except Exception as e:
        logger.error(f"发送当前进度失败: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Failed to get progress: {str(e)}"
        }))

async def broadcast_progress_update(video_id: int, user_id: int, progress_data: Dict[str, Any]):
    """广播进度更新到WebSocket客户端（已废弃，使用节流版本）"""
    logger.warning("broadcast_progress_update 已废弃，请使用 send_throttled_progress")
    await manager.send_throttled_progress(video_id, user_id, progress_data)

# 导出给其他模块使用的函数
async def notify_progress_update(video_id: int, user_id: int, progress_data: Dict[str, Any]):
    """通知进度更新（供其他模块调用）- 使用节流版本"""
    await manager.send_throttled_progress(video_id, user_id, progress_data)

async def notify_log_update(user_id: int, log_data: Dict[str, Any]):
    """通知日志更新（供其他模块调用）"""
    message = {
        "type": "log_update",
        "timestamp": asyncio.get_event_loop().time(),
        **log_data
    }
    await manager.broadcast_to_user(message, user_id)
