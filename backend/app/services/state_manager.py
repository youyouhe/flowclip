"""状态管理服务，统一管理Celery任务状态和数据库状态"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.constants import (
    ProcessingTaskStatus, ProcessingTaskType, ProcessingStage,
    CELERY_TO_DB_STATUS_MAP
)
from app.models.processing_task import ProcessingTask, ProcessingTaskLog, ProcessingStatus
from app.models.video import Video

logger = logging.getLogger(__name__)

class StateManager:
    """状态管理服务"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_processing_task(
        self,
        video_id: int,
        task_type: str,
        task_name: str,
        celery_task_id: str,
        input_data: Dict[str, Any] = None,
        max_retries: int = 3
    ) -> ProcessingTask:
        """创建处理任务记录"""
        task = ProcessingTask(
            video_id=video_id,
            task_type=task_type,
            task_name=task_name,
            celery_task_id=celery_task_id,
            input_data=input_data or {},
            max_retries=max_retries,
            started_at=datetime.utcnow()
        )
        
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        
        # 创建初始状态日志
        await self._create_task_log(task.id, None, ProcessingTaskStatus.PENDING, "任务创建")
        
        return task
    
    async def update_task_status(
        self,
        task_id: int,
        status: str,
        progress: float = None,
        message: str = None,
        error_message: str = None,
        output_data: Dict[str, Any] = None,
        stage: str = None
    ) -> ProcessingTask:
        """更新任务状态"""
        stmt = select(ProcessingTask).where(ProcessingTask.id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        old_status = task.status
        
        # 更新状态
        task.status = status
        if progress is not None:
            task.progress = progress
        if message is not None:
            task.message = message
        if error_message is not None:
            task.error_message = error_message
        if output_data is not None:
            task.output_data = output_data
        if stage is not None:
            task.stage = stage
        
        # 如果任务完成，更新完成时间
        if status in [ProcessingTaskStatus.SUCCESS, ProcessingTaskStatus.FAILURE]:
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
        
        await self.db.commit()
        
        # 创建状态变化日志
        await self._create_task_log(task.id, old_status, status, message or f"状态更新为: {status}")
        
        # 更新视频状态
        await self._update_video_status(task.video_id, task.task_type, status, progress, stage)
        
        return task
    
    async def update_celery_task_status(
        self,
        celery_task_id: str,
        celery_status: str,
        meta: Dict[str, Any] = None
    ) -> ProcessingTask:
        """根据Celery状态更新任务状态"""
        stmt = select(ProcessingTask).where(ProcessingTask.celery_task_id == celery_task_id)
        result = await self.db.execute(stmt)
        task = result.scalar_one_or_none()
        
        if not task:
            raise ValueError(f"Task with celery_task_id {celery_task_id} not found")
        
        # 直接使用传入的状态值（已经是ProcessingTaskStatus枚举）
        db_status = celery_status
        
        # 提取进度和消息
        progress = meta.get('progress', task.progress) if meta else task.progress
        message = meta.get('message', task.message) if meta else task.message
        stage = meta.get('stage', task.stage) if meta else task.stage
        error = meta.get('error', None) if meta else None
        
        return await self.update_task_status(
            task.id,
            db_status,
            progress=progress,
            message=message,
            error_message=error,
            stage=stage
        )
    
    def update_celery_task_status_sync(
        self,
        celery_task_id: str,
        celery_status: str,
        meta: Dict[str, Any] = None
    ) -> ProcessingTask:
        """同步版本：根据Celery状态更新任务状态"""
        task = self.db.query(ProcessingTask).filter(
            ProcessingTask.celery_task_id == celery_task_id
        ).first()
        
        if not task:
            raise ValueError(f"Task with celery_task_id {celery_task_id} not found")
        
        # 直接使用传入的状态值（已经是ProcessingTaskStatus枚举）
        db_status = celery_status
        
        # 提取进度和消息
        progress = meta.get('progress', task.progress) if meta else task.progress
        message = meta.get('message', task.message) if meta else task.message
        stage = meta.get('stage', task.stage) if meta else task.stage
        error = meta.get('error', None) if meta else None
        
        return self.update_task_status_sync(
            task.id,
            db_status,
            progress=progress,
            message=message,
            error_message=error,
            stage=stage
        )
    
    async def get_task_by_celery_id(self, celery_task_id: str) -> Optional[ProcessingTask]:
        """通过Celery任务ID获取任务"""
        stmt = select(ProcessingTask).where(ProcessingTask.celery_task_id == celery_task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_video_tasks(self, video_id: int) -> List[ProcessingTask]:
        """获取视频的所有处理任务"""
        stmt = select(ProcessingTask).where(ProcessingTask.video_id == video_id).order_by(ProcessingTask.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_video_status(self, video_id: int) -> Dict[str, Any]:
        """获取视频的整体状态"""
        stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
        result = await self.db.execute(stmt)
        status = result.scalar_one_or_none()
        
        if not status:
            return {}
        
        return {
            "overall_status": status.overall_status,
            "overall_progress": status.overall_progress,
            "current_stage": status.current_stage,
            "download": {
                "status": status.download_status,
                "progress": status.download_progress
            },
            "extract_audio": {
                "status": status.extract_audio_status,
                "progress": status.extract_audio_progress
            },
            "split_audio": {
                "status": status.split_audio_status,
                "progress": status.split_audio_progress
            },
            "generate_srt": {
                "status": status.generate_srt_status,
                "progress": status.generate_srt_progress
            },
            "error_count": status.error_count,
            "last_error": status.last_error
        }
    
    async def _create_task_log(
        self,
        task_id: int,
        old_status: str,
        new_status: str,
        message: str,
        details: Dict[str, Any] = None
    ):
        """创建任务状态变化日志"""
        log = ProcessingTaskLog(
            task_id=task_id,
            old_status=old_status,
            new_status=new_status,
            message=message,
            details=details or {}
        )
        
        self.db.add(log)
        await self.db.commit()
    
    async def _update_video_status(
        self,
        video_id: int,
        task_type: str,
        status: str,
        progress: float,
        stage: str = None
    ):
        """更新视频状态汇总"""
        stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
        result = await self.db.execute(stmt)
        status_record = result.scalar_one_or_none()
        
        if not status_record:
            status_record = ProcessingStatus(video_id=video_id)
            self.db.add(status_record)
        
        # 根据任务类型更新对应字段
        if task_type == ProcessingTaskType.DOWNLOAD:
            status_record.download_status = status
            status_record.download_progress = progress
        elif task_type == ProcessingTaskType.EXTRACT_AUDIO:
            status_record.extract_audio_status = status
            status_record.extract_audio_progress = progress
        elif task_type == ProcessingTaskType.SPLIT_AUDIO:
            status_record.split_audio_status = status
            status_record.split_audio_progress = progress
        elif task_type == ProcessingTaskType.GENERATE_SRT:
            status_record.generate_srt_status = status
            status_record.generate_srt_progress = progress
        
        # 更新整体状态
        if status == ProcessingTaskStatus.FAILURE:
            status_record.error_count += 1
            
        # 计算整体进度
        progresses = [
            status_record.download_progress or 0,
            status_record.extract_audio_progress or 0,
            status_record.split_audio_progress or 0,
            status_record.generate_srt_progress or 0
        ]
        status_record.overall_progress = sum(progresses) / len(progresses)
        
        # 更新当前阶段
        if stage:
            status_record.current_stage = stage
        
        await self.db.commit()
    
    async def initialize_video_status(self, video_id: int) -> ProcessingStatus:
        """初始化视频状态记录"""
        stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
        result = await self.db.execute(stmt)
        status = result.scalar_one_or_none()
        
        if not status:
            status = ProcessingStatus(video_id=video_id)
            self.db.add(status)
            await self.db.commit()
            await self.db.refresh(status)
        
        return status
    
    async def reset_video_status(self, video_id: int):
        """重置视频状态"""
        stmt = select(ProcessingStatus).where(ProcessingStatus.video_id == video_id)
        result = await self.db.execute(stmt)
        status = result.scalar_one_or_none()
        
        if status:
            status.overall_status = ProcessingTaskStatus.PENDING
            status.overall_progress = 0.0
            status.download_status = ProcessingTaskStatus.PENDING
            status.download_progress = 0.0
            status.extract_audio_status = ProcessingTaskStatus.PENDING
            status.extract_audio_progress = 0.0
            status.split_audio_status = ProcessingTaskStatus.PENDING
            status.split_audio_progress = 0.0
            status.generate_srt_status = ProcessingTaskStatus.PENDING
            status.generate_srt_progress = 0.0
            status.error_count = 0
            status.last_error = ""
            
            await self.db.commit()

    def update_task_status_sync(
        self,
        task_id: int,
        status: str,
        progress: float = None,
        message: str = None,
        error_message: str = None,
        output_data: Dict[str, Any] = None,
        stage: str = None
    ) -> ProcessingTask:
        """同步版本：更新任务状态"""
        task = self.db.query(ProcessingTask).filter(
            ProcessingTask.id == task_id
        ).first()
        
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        old_status = task.status
        
        # 更新状态
        task.status = status
        if progress is not None:
            task.progress = progress
        if message is not None:
            task.message = message
        if error_message is not None:
            task.error_message = error_message
        if output_data is not None:
            task.output_data = output_data
        if stage is not None:
            task.stage = stage
        
        # 如果任务完成，更新完成时间
        if status in [ProcessingTaskStatus.SUCCESS, ProcessingTaskStatus.FAILURE]:
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
        
        self.db.commit()
        
        # 创建状态变化日志
        self._create_task_log_sync(task.id, old_status, status, message or f"状态更新为: {status}")
        
        # 更新视频状态
        self._update_video_status_sync(task.video_id, task.task_type, status, progress, stage)
        
        return task

    def _create_task_log_sync(
        self,
        task_id: int,
        old_status: str,
        new_status: str,
        message: str,
        details: Dict[str, Any] = None
    ):
        """同步版本：创建任务状态变化日志"""
        log = ProcessingTaskLog(
            task_id=task_id,
            old_status=old_status,
            new_status=new_status,
            message=message,
            details=details or {}
        )
        
        self.db.add(log)
        self.db.commit()

    def _update_video_status_sync(
        self,
        video_id: int,
        task_type: str,
        status: str,
        progress: float,
        stage: str = None
    ):
        """同步版本：更新视频状态汇总"""
        status_record = self.db.query(ProcessingStatus).filter(
            ProcessingStatus.video_id == video_id
        ).first()
        
        if not status_record:
            status_record = ProcessingStatus(video_id=video_id)
            self.db.add(status_record)
        
        # 根据任务类型更新对应字段
        if task_type == ProcessingTaskType.DOWNLOAD:
            status_record.download_status = status
            status_record.download_progress = progress
        elif task_type == ProcessingTaskType.EXTRACT_AUDIO:
            status_record.extract_audio_status = status
            status_record.extract_audio_progress = progress
        elif task_type == ProcessingTaskType.SPLIT_AUDIO:
            status_record.split_audio_status = status
            status_record.split_audio_progress = progress
        elif task_type == ProcessingTaskType.GENERATE_SRT:
            status_record.generate_srt_status = status
            status_record.generate_srt_progress = progress
        
        # 更新整体状态
        if status == ProcessingTaskStatus.FAILURE:
            status_record.error_count += 1
            
        # 计算整体进度
        progresses = [
            status_record.download_progress or 0,
            status_record.extract_audio_progress or 0,
            status_record.split_audio_progress or 0,
            status_record.generate_srt_progress or 0
        ]
        status_record.overall_progress = sum(progresses) / len(progresses)
        
        # 更新当前阶段
        if stage:
            status_record.current_stage = stage
        
        self.db.commit()

# 全局状态管理器实例
state_manager = None

def get_state_manager(db):
    """获取状态管理器实例 - 支持AsyncSession和Session"""
    return StateManager(db)