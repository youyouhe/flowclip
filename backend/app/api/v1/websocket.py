from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, Optional
import json
import asyncio
from app.core.database import get_db, AsyncSessionLocal # Import AsyncSessionLocal
from fastapi import Depends
from app.core.security import get_current_user, get_current_user_from_token, oauth2_scheme
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models.processing_task import ProcessingTask
from app.models.processing_task import ProcessingStatus
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
        is_significant_progress = False
        
        # 与待发送数据对比
        pending_data = self.pending_updates.get(key, {})
        
        # 状态变化或完成立即推送
        is_status_change = progress_data.get('video_status') != pending_data.get('video_status')
        is_completion = progress_data.get('status') == 'completed' or progress_data.get('download_progress') == 100
        
        # 计算进度变化
        current_progress = progress_data.get('download_progress', 0)
        pending_progress = pending_data.get('download_progress', 0)
        progress_change = abs(current_progress - pending_progress)
        
        # 判断是否是显著的进度变化
        # 1. 进度变化超过1%（降低阈值，更频繁更新）
        # 2. 或者进度是整数变化（如从10.0%到11.0%）
        is_significant_progress = progress_change >= 1 or (
            int(current_progress) != int(pending_progress) and progress_change > 0
        )
        
        # 关键状态变化立即推送
        if is_status_change or is_completion:
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = now
            # 清空待发送数据
            if key in self.pending_updates:
                del self.pending_updates[key]
        # 显著的进度变化也推送
        elif is_significant_progress:
            await self._send_progress_update(video_id, user_id, progress_data)
            self.last_sent_time[key] = now
            # 清空待发送数据
            if key in self.pending_updates:
                del self.pending_updates[key]
        # 普通更新最多5秒间隔（降低时间间隔）
        elif now - last_sent >= 5.0:
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

@router.websocket("/ws/test")
async def websocket_test_endpoint(websocket: WebSocket):
    """简单的WebSocket测试端点，不需要token验证"""
    logger.info(f"WS: Test connection attempt received")
    
    try:
        await websocket.accept()
        logger.info(f"WS: Test connection accepted")
        
        # 发送测试消息
        await websocket.send_text(json.dumps({
            "type": "test_ack",
            "message": "WebSocket test connection successful"
        }))
        logger.info(f"WS: Test message sent")
        
        # 保持连接并等待消息
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"WS: Received test message: {data}")
                
                # 回显消息
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "message": f"Echo: {data}"
                }))
                
            except WebSocketDisconnect:
                logger.info(f"WS: Test client disconnected")
                break
                
    except Exception as e:
        logger.error(f"WS: Test connection error: {str(e)}")
        await websocket.close(code=1011, reason=f"Server error: {str(e)}")


@router.websocket("/progress/{token}")
async def websocket_progress_endpoint(websocket: WebSocket, token: str):
    """WebSocket端点用于实时进度更新"""
    user_id: Optional[int] = None
    try:
        async with AsyncSessionLocal() as db_session:
            # 验证token
            user = await get_current_user_from_token(token=token, db=db_session)
            
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
                            
                            # 查询用户需要状态更新的视频
                            try:
                                # 获取video_id参数，支持指定视频查询
                                video_id = message.get('video_id')
                                
                                if video_id:
                                    # 查询特定视频的最新状态（不管是什么状态）
                                    logger.info(f"查询特定视频状态 - video_id: {video_id}")
                                    
                                    stmt = select(Video).where(
                                        Video.id == video_id,
                                        Video.project_id.in_(
                                            select(Project.id).where(Project.user_id == user_id)
                                        )
                                    )
                                    result = await db_session.execute(stmt)
                                    video = result.scalar_one_or_none()
                                    
                                    if video:
                                        logger.info(f"找到视频 {video_id}，状态: {video.status}，发送更新")
                                        # 为特定视频发送当前进度状态
                                        await send_current_progress(websocket, video_id, user_id, db_session)
                                    else:
                                        logger.warning(f"未找到视频 {video_id} 或无权限访问")
                                
                                else:
                                    # 查询用户所有活跃的视频状态（不包含已完成的视频）
                                    logger.info("查询用户所有活跃视频状态")
                                    
                                    active_statuses = ["pending", "downloading", "processing"]
                                    stmt = select(Video).where(
                                        Video.project_id.in_(
                                            select(Project.id).where(Project.user_id == user_id)
                                        ),
                                        Video.status.in_(active_statuses)
                                    )
                                    
                                    result = await db_session.execute(stmt)
                                    active_videos = result.scalars().all()
                                    
                                    # Debug: 添加日志显示查询结果
                                    logger.info(f"用户 {user_id} 的活跃视频查询结果: {len(active_videos)} 个视频")
                                    for video in active_videos:
                                        logger.info(f"视频 {video.id}: project_id={video.project_id}, status={video.status}")
                                    
                                    # 简化过滤逻辑：所有查询到的视频都需要状态更新
                                    videos_to_update = []
                                    for video in active_videos:
                                        # 所有查询到的视频都是活跃状态，直接加入更新列表
                                        videos_to_update.append(video)
                                        logger.debug(f"视频 {video.id} 状态为 {video.status}，需要状态更新")
                                    
                                    logger.info(f"用户 {user_id} 有 {len(videos_to_update)} 个活跃视频需要状态更新")
                                    
                                    for video in videos_to_update:
                                        # 为每个需要更新的视频发送当前进度状态
                                        await send_current_progress(websocket, video.id, user_id, db_session)
                                    
                            except Exception as e:
                                logger.error(f"状态更新查询失败: {str(e)}")
                                # 在异常情况下，上下文管理器会自动回滚
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
        # 读取最新数据
        try:
            # 检查视频是否存在
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
                # 获取处理状态，以获取更准确的下载状态
                stmt = select(ProcessingStatus).where(
                    ProcessingStatus.video_id == video_id
                )
                result = await db.execute(stmt)
                processing_status = result.scalar_one_or_none()
                
                # 获取处理任务（单独查询确保最新）
                stmt = select(ProcessingTask).where(
                    ProcessingTask.video_id == video_id
                ).order_by(ProcessingTask.created_at.desc())
                result = await db.execute(stmt)
                tasks = result.scalars().all()
                
                # 确定实际的下载状态
                actual_download_progress = video.download_progress or 0
                actual_status = video.status
                
                # 检查所有任务是否都已完成，如果都完成了，将视频状态设置为completed
                all_tasks_completed = len(tasks) > 0 and all(task.status == 'success' for task in tasks)
                if all_tasks_completed and len(tasks) >= 2:  # 至少要有下载和音频提取任务
                    actual_status = 'completed'
                
                # 如果processing_status存在，使用更精确的状态信息
                if processing_status:
                    # 优先使用processing_status中的下载进度
                    if processing_status.download_progress > 0:
                        actual_download_progress = processing_status.download_progress
                    
                    # 状态判断逻辑：
                    # 1. 如果video.status是completed，保持completed
                    # 2. 如果所有任务都已完成，设置为completed
                    # 3. 如果video.status是processing，保持processing  
                    # 4. 如果video.status是pending或downloading，但processing_status.download_status是success，则设为downloaded
                    if actual_status == 'completed':
                        # 保持completed状态
                        pass
                    elif all_tasks_completed and len(tasks) >= 2:
                        actual_status = 'completed'
                    elif actual_status in ['pending', 'downloading'] and processing_status.download_status == 'success':
                        actual_status = 'downloaded'
                        actual_download_progress = 100.0
                    elif actual_status in ['pending', 'downloading'] and processing_status.download_progress > 0:
                        # 如果有下载进度但还没完成，保持原状态但更新进度
                        actual_download_progress = processing_status.download_progress
                
                # 构建最新进度消息
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": video.title,
                    "video_status": actual_status,
                    "download_progress": actual_download_progress,
                    "processing_progress": video.processing_progress or 0,
                    "processing_stage": video.processing_stage or "",
                    "processing_message": video.processing_message or "",
                    "tasks": []
                }
                
                # 添加详细的debug信息
                logger.info(f"🔍 [WebSocket] 发送进度更新 - video_id: {video_id}")
                logger.info(f"🔍 [WebSocket] 实际状态: {actual_status}")
                logger.info(f"🔍 [WebSocket] 实际下载进度: {actual_download_progress}")
                logger.info(f"🔍 [WebSocket] 处理进度: {video.processing_progress or 0}")
                logger.info(f"🔍 [WebSocket] 原始video状态: {video.status}")
                logger.info(f"🔍 [WebSocket] 原始video下载进度: {video.download_progress or 0}")
                if processing_status:
                    logger.info(f"🔍 [WebSocket] processing_status下载状态: {processing_status.download_status}")
                    logger.info(f"🔍 [WebSocket] processing_status下载进度: {processing_status.download_progress}")
                else:
                    logger.info(f"🔍 [WebSocket] processing_status: 无")
                logger.info(f"🔍 [WebSocket] 处理任务数量: {len(tasks)}")
                for i, task in enumerate(tasks):
                    logger.info(f"🔍 [WebSocket] 任务{i}: id={task.id}, type={task.task_type}, status={task.status}, progress={task.progress}")
                
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
            
        except Exception as transaction_error:
            logger.error(f"查询失败，使用降级模式: {str(transaction_error)}")
            
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
                
                # 获取处理状态，以获取更准确的下载状态
                stmt = select(ProcessingStatus).where(
                    ProcessingStatus.video_id == video_id
                )
                result = await db.execute(stmt)
                processing_status = result.scalar_one_or_none()
                
                # 确定实际的下载状态
                actual_download_progress = video.download_progress or 0
                actual_status = video.status
                
                # 检查所有任务是否都已完成，如果都完成了，将视频状态设置为completed
                all_tasks_completed = len(tasks) > 0 and all(task.status == 'success' for task in tasks)
                if all_tasks_completed and len(tasks) >= 2:  # 至少要有下载和音频提取任务
                    actual_status = 'completed'
                
                # 如果processing_status存在，使用更精确的状态信息
                if processing_status:
                    # 优先使用processing_status中的下载进度
                    if processing_status.download_progress > 0:
                        actual_download_progress = processing_status.download_progress
                    
                    # 状态判断逻辑：
                    # 1. 如果video.status是completed，保持completed
                    # 2. 如果所有任务都已完成，设置为completed
                    # 3. 如果video.status是processing，保持processing  
                    # 4. 如果video.status是pending或downloading，但processing_status.download_status是success，则设为downloaded
                    if actual_status == 'completed':
                        # 保持completed状态
                        pass
                    elif all_tasks_completed and len(tasks) >= 2:
                        actual_status = 'completed'
                    elif actual_status in ['pending', 'downloading'] and processing_status.download_status == 'success':
                        actual_status = 'downloaded'
                        actual_download_progress = 100.0
                    elif actual_status in ['pending', 'downloading'] and processing_status.download_progress > 0:
                        # 如果有下载进度但还没完成，保持原状态但更新进度
                        actual_download_progress = processing_status.download_progress
                
                progress_data = {
                    "type": "progress_update",
                    "video_id": video_id,
                    "video_title": video.title,
                    "video_status": actual_status,
                    "download_progress": actual_download_progress,
                    "processing_progress": video.processing_progress or 0,
                    "processing_stage": video.processing_stage or "",
                    "processing_message": video.processing_message or "",
                    "tasks": []
                }
                
                # 添加详细的debug信息（降级模式）
                logger.info(f"🔍 [WebSocket] 降级模式发送进度更新 - video_id: {video_id}")
                logger.info(f"🔍 [WebSocket] 降级模式实际状态: {actual_status}")
                logger.info(f"🔍 [WebSocket] 降级模式实际下载进度: {actual_download_progress}")
                logger.info(f"🔍 [WebSocket] 降级模式原始video状态: {video.status}")
                logger.info(f"🔍 [WebSocket] 降级模式原始video下载进度: {video.download_progress or 0}")
                if processing_status:
                    logger.info(f"🔍 [WebSocket] 降级模式processing_status下载状态: {processing_status.download_status}")
                    logger.info(f"🔍 [WebSocket] 降级模式processing_status下载进度: {processing_status.download_progress}")
                else:
                    logger.info(f"🔍 [WebSocket] 降级模式processing_status: 无")
                logger.info(f"🔍 [WebSocket] 降级模式处理任务数量: {len(tasks)}")
                for i, task in enumerate(tasks):
                    logger.info(f"🔍 [WebSocket] 降级模式任务{i}: id={task.id}, type={task.task_type}, status={task.status}, progress={task.progress}")
                
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
