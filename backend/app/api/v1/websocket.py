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
        if (
            progress_data.get('video_status') != pending_data.get('video_status') or
            progress_data.get('status') == 'completed' or
            progress_data.get('download_progress') == 100 or
            abs(progress_data.get('download_progress', 0) - pending_data.get('download_progress', 0)) >= 5
        ):
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = now
            # 清空待发送数据
            if key in self.pending_updates:
                del self.pending_updates[key]
        elif now - last_sent >= 10.0:  # 普通更新最多10秒间隔
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
                    # Explicitly begin a transaction for each message processing cycle
                    async with db_session.begin(): # Begin a transaction
                        # 保持连接活跃，等待客户端消息
                        data = await websocket.receive_text()
                        
                        # 处理客户端消息（例如订阅特定视频的进度）
                        try:
                            message = json.loads(data)
                            
                            if message.get('type') == 'subscribe':
                                video_id = message.get('video_id')
                                if video_id:
                                    # 立即发送当前进度状态
                                    await send_current_progress(websocket, video_id, user_id, db_session) # Pass db_session
                            
                            elif message.get('type') == 'ping':
                                # 响应心跳
                                await websocket.send_text(json.dumps({"type": "pong"}))
                            
                            elif message.get('type') == 'request_status_update':
                                logger.info(f"收到来自用户 {user_id} 的状态更新请求")
                                # 获取该用户所有处于活跃状态（pending, downloading, processing）的视频
                                active_statuses = ["pending", "downloading", "processing"]
                                stmt = select(Video).where(
                                    Video.user_id == user_id,
                                    Video.status.in_(active_statuses)
                                )
                                result = await db_session.execute(stmt) # Use db_session
                                active_videos = result.scalars().all()
                                
                                for video in active_videos:
                                    # 为每个活跃视频发送当前进度状态
                                    await send_current_progress(websocket, video.id, user_id, db_session)
                            
                        except json.JSONDecodeError:
                            logger.warning(f"收到无效的JSON消息: {data}")
                        
                        # Explicitly commit the transaction after processing the message
                        await db_session.commit()
                            
            except WebSocketDisconnect:
                manager.disconnect(user_id)
                logger.info(f"WebSocket断开连接 - user_id: {user_id}")
                
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
        if user_id is not None: # Check if user_id was successfully assigned
            manager.disconnect(user_id)

async def send_current_progress(websocket: WebSocket, video_id: int, user_id: int, db: AsyncSession):
    """发送当前进度状态 - 修复权限验证和状态同步"""
    try:
        # 检查视频是否存在，支持延迟创建的情况
        stmt = select(Video).where(Video.id == video_id)
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
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
            
        # 验证用户权限（更宽松的验证）
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
        
        # 重新查询最新视频状态，避免缓存问题
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
                "tasks": [] # Initialize tasks list
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
