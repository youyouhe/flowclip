from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.project import Project
from app.models import LLMAnalysis, VideoSlice, VideoSubSlice
from app.schemas.video_slice import (
    LLMAnalysisCreate, LLMAnalysisUpdate, LLMAnalysis as LLMAnalysisSchema,
    VideoSliceCreate, VideoSliceUpdate, VideoSlice as VideoSliceSchema,
    VideoSubSliceCreate, VideoSubSliceUpdate, VideoSubSlice as VideoSubSliceSchema,
    SliceValidationRequest, SliceValidationResponse,
    SliceProcessRequest, SliceProcessResponse
)
from app.services.minio_client import minio_service
from app.services.video_slicing_service import video_slicing_service
from app.core.config import settings
import json
import logging
import os
import aiofiles

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/validate-slice-data", response_model=SliceValidationResponse)
async def validate_slice_data(
    request: SliceValidationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """验证切片数据"""
    
    try:
        # 详细日志记录
        logger.debug(f"开始验证切片数据 - 用户ID: {current_user.id}")
        logger.debug(f"请求数据 - video_id: {request.video_id}, cover_title: {request.cover_title}")
        logger.debug(f"分析数据类型: {type(request.analysis_data)}, 长度: {len(request.analysis_data) if isinstance(request.analysis_data, list) else 'N/A'}")
        logger.debug(f"完整请求数据: {request.model_dump()}")
        
        # 验证视频是否存在且属于当前用户
        stmt = select(Video).join(Project).where(
            Video.id == request.video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        logger.info(f"视频查询结果: {video is not None}")
        
        if not video:
            logger.warning(f"视频不存在或无权限访问 - video_id: {request.video_id}, user_id: {current_user.id}")
            return SliceValidationResponse(
                is_valid=False,
                message="视频不存在或无权限访问",
                errors=["视频不存在或无权限访问"]
            )
        
        # 验证JSON格式
        if not isinstance(request.analysis_data, list):
            logger.warning(f"分析数据格式错误 - 期望list, 实际: {type(request.analysis_data)}")
            return SliceValidationResponse(
                is_valid=False,
                message="分析数据格式错误",
                errors=["分析数据必须是数组格式"]
            )
        
        errors = []
        
        # 验证每个切片项
        for i, slice_item in enumerate(request.analysis_data):
            logger.info(f"验证切片 {i+1}: {slice_item.get('cover_title', 'N/A')}")
            
            # 检查必需字段
            required_fields = ['cover_title', 'title', 'start', 'end']
            for field in required_fields:
                if field not in slice_item:
                    error_msg = f"切片 {i+1}: 缺少必需字段 '{field}'"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            
            # 验证时间格式
            try:
                start_time = video_slicing_service._parse_time_str(slice_item.get('start', '00:00:00,000'))
                end_time = video_slicing_service._parse_time_str(slice_item.get('end', '00:00:00,000'))
                
                logger.info(f"切片 {i+1} 时间解析 - start: {slice_item.get('start')}, end: {slice_item.get('end')}")
                logger.info(f"解析后时间 - start: {start_time}, end: {end_time}")
                
                if start_time is None or end_time is None:
                    error_msg = f"切片 {i+1}: 时间格式错误"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                elif start_time >= end_time:
                    error_msg = f"切片 {i+1}: 开始时间必须小于结束时间"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                elif end_time - start_time < 5:  # 至少5秒
                    error_msg = f"切片 {i+1}: 持续时间太短，至少需要5秒"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                
            except Exception as e:
                error_msg = f"切片 {i+1}: 时间解析错误 - {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            # 验证子切片
            for j, sub_slice in enumerate(slice_item.get('subtitles', [])):
                logger.info(f"验证子切片 {i+1}-{j+1}: {sub_slice.get('cover_title', 'N/A')}")
                
                sub_required_fields = ['cover_title', 'start', 'end']
                for field in sub_required_fields:
                    if field not in sub_slice:
                        error_msg = f"切片 {i+1} 子切片 {j+1}: 缺少必需字段 '{field}'"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                
                try:
                    sub_start = video_slicing_service._parse_time_str(sub_slice.get('start', '00:00:00,000'))
                    sub_end = video_slicing_service._parse_time_str(sub_slice.get('end', '00:00:00,000'))
                    
                    logger.info(f"子切片 {i+1}-{j+1} 时间解析 - start: {sub_slice.get('start')}, end: {sub_slice.get('end')}")
                    logger.info(f"解析后时间 - start: {sub_start}, end: {sub_end}")
                    
                    if sub_start is None or sub_end is None:
                        error_msg = f"切片 {i+1} 子切片 {j+1}: 时间格式错误"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                    elif sub_start >= sub_end:
                        error_msg = f"切片 {i+1} 子切片 {j+1}: 开始时间必须小于结束时间"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                    elif sub_end - sub_start < 2:  # 至少2秒
                        error_msg = f"切片 {i+1} 子切片 {j+1}: 持续时间太短，至少需要2秒"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                    
                except Exception as e:
                    error_msg = f"切片 {i+1} 子切片 {j+1}: 时间解析错误 - {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        logger.info(f"验证完成 - 错误数量: {len(errors)}")
        
        if errors:
            logger.warning(f"数据验证失败，错误列表: {errors}")
            return SliceValidationResponse(
                is_valid=False,
                message="数据验证失败",
                errors=errors
            )
        
        # 保存验证通过的数据
        logger.info("开始保存验证通过的数据")
        analysis = LLMAnalysis(
            video_id=request.video_id,
            analysis_data=request.analysis_data,
            cover_title=request.cover_title,
            status="validated",
            is_validated=True
        )
        
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        
        logger.info(f"切片数据验证成功 - analysis_id: {analysis.id}")
        
        return SliceValidationResponse(
            is_valid=True,
            message="数据验证成功",
            analysis_id=analysis.id
        )
        
    except Exception as e:
        logger.error(f"验证切片数据失败: {str(e)}")
        logger.error(f"异常详情: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证失败: {str(e)}"
        )

@router.post("/process-slices", response_model=SliceProcessResponse)
async def process_slices(
    request: SliceProcessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """处理视频切片"""
    
    try:
        # 获取分析数据
        stmt = select(LLMAnalysis).where(LLMAnalysis.id == request.analysis_id)
        result = await db.execute(stmt)
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析数据不存在"
            )
        
        # 验证视频权限
        stmt = select(Video).join(Project).where(
            Video.id == analysis.video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问此视频"
            )
        
        # 启动Celery任务处理视频切片
        from app.tasks.video_tasks import process_video_slices
        
        task = process_video_slices.delay(
            analysis_id=request.analysis_id,
            video_id=video.id,
            project_id=video.project_id,
            user_id=current_user.id,
            slice_items=request.slice_items
        )
        
        logger.info(f"启动视频切片Celery任务 - task_id: {task.id}, analysis_id: {request.analysis_id}")
        
        return SliceProcessResponse(
            message="切片处理任务已启动",
            task_id=task.id,
            total_slices=len(request.slice_items),
            processed_slices=0
        )
        
    except Exception as e:
        logger.error(f"启动视频切片任务失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动任务失败: {str(e)}"
        )

@router.get("/video-analyses/{video_id}", response_model=List[LLMAnalysisSchema])
async def get_video_analyses(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的分析数据列表"""
    
    try:
        # 验证视频权限
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="视频不存在或无权限访问"
            )
        
        # 获取分析数据
        stmt = select(LLMAnalysis).where(LLMAnalysis.video_id == video_id).order_by(LLMAnalysis.created_at.desc())
        result = await db.execute(stmt)
        analyses = result.scalars().all()
        
        return analyses
        
    except Exception as e:
        logger.error(f"获取视频分析数据失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.get("/video-slices/{video_id}", response_model=List[VideoSliceSchema])
async def get_video_slices(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取视频的切片列表"""
    
    try:
        # 验证视频权限
        stmt = select(Video).join(Project).where(
            Video.id == video_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="视频不存在或无权限访问"
            )
        
        # 获取切片数据，包含子切片
        stmt = select(VideoSlice).where(VideoSlice.video_id == video_id).order_by(VideoSlice.start_time)
        result = await db.execute(stmt)
        slices = result.scalars().all()
        
        return slices
        
    except Exception as e:
        logger.error(f"获取视频切片失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.get("/slice-detail/{slice_id}", response_model=VideoSliceSchema)
async def get_slice_detail(
    slice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取切片详情"""
    
    try:
        # 获取切片数据
        stmt = select(VideoSlice).join(Video).join(Project).where(
            VideoSlice.id == slice_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        slice_data = result.scalar_one_or_none()
        
        if not slice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="切片不存在或无权限访问"
            )
        
        return slice_data
        
    except Exception as e:
        logger.error(f"获取切片详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.get("/slice-download-url/{slice_id}")
async def get_slice_download_url(
    slice_id: int,
    expiry: int = 3600,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取切片文件的下载URL"""
    
    try:
        # 获取切片数据
        stmt = select(VideoSlice).join(Video).join(Project).where(
            VideoSlice.id == slice_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        slice_data = result.scalar_one_or_none()
        
        if not slice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="切片不存在或无权限访问"
            )
        
        if not slice_data.sliced_file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="切片文件不存在"
            )
        
        # 生成预签名URL
        url = await minio_service.get_file_url(slice_data.sliced_file_path, expiry)
        
        if not url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法生成下载URL"
            )
        
        return {"url": url}
        
    except Exception as e:
        logger.error(f"获取切片下载URL失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.get("/slice-sub-slices/{slice_id}", response_model=List[VideoSubSliceSchema])
async def get_slice_sub_slices(
    slice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取主切片的子切片列表"""
    
    try:
        # 验证切片权限
        stmt = select(VideoSlice).join(Video).join(Project).where(
            VideoSlice.id == slice_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        slice_data = result.scalar_one_or_none()
        
        if not slice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="切片不存在或无权限访问"
            )
        
        # 获取子切片数据
        stmt = select(VideoSubSlice).where(VideoSubSlice.slice_id == slice_id).order_by(VideoSubSlice.start_time)
        result = await db.execute(stmt)
        sub_slices = result.scalars().all()
        
        return sub_slices
        
    except Exception as e:
        logger.error(f"获取子切片失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.delete("/analysis/{analysis_id}")
async def delete_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除分析数据"""
    
    try:
        # 验证分析数据权限
        stmt = select(LLMAnalysis).join(Video).join(Project).where(
            LLMAnalysis.id == analysis_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析数据不存在或无权限访问"
            )
        
        # 删除分析数据
        await db.delete(analysis)
        await db.commit()
        
        return {"message": "分析数据删除成功"}
        
    except Exception as e:
        logger.error(f"删除分析数据失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

@router.delete("/slice/{slice_id}")
async def delete_slice(
    slice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除切片及其子切片"""
    
    try:
        # 验证切片权限
        stmt = select(VideoSlice).join(Video).join(Project).where(
            VideoSlice.id == slice_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        slice_data = result.scalar_one_or_none()
        
        if not slice_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="切片不存在或无权限访问"
            )
        
        # 删除切片（级联删除子切片）
        await db.delete(slice_data)
        await db.commit()
        
        return {"message": "切片删除成功"}
        
    except Exception as e:
        logger.error(f"删除切片失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

@router.delete("/sub-slice/{sub_slice_id}")
async def delete_sub_slice(
    sub_slice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除子切片"""
    
    try:
        # 验证子切片权限
        stmt = select(VideoSubSlice).join(VideoSlice).join(Video).join(Project).where(
            VideoSubSlice.id == sub_slice_id,
            Project.user_id == current_user.id
        )
        result = await db.execute(stmt)
        sub_slice = result.scalar_one_or_none()
        
        if not sub_slice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="子切片不存在或无权限访问"
            )
        
        # 删除子切片
        await db.delete(sub_slice)
        await db.commit()
        
        return {"message": "子切片删除成功"}
        
    except Exception as e:
        logger.error(f"删除子切片失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )