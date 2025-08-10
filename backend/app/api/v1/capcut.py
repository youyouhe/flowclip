from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
import os
import requests
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.video_slice import VideoSlice, VideoSubSlice
from app.schemas.video_slice import VideoSlice as VideoSliceSchema
from app.core.config import settings

router = APIRouter(tags=["capcut"])

# CapCut API 服务器地址
CAPCUT_API_BASE_URL = "http://192.168.8.107:9002"

class CapCutService:
    def __init__(self):
        self.base_url = CAPCUT_API_BASE_URL
    
    async def get_resource_by_tag(self, tag_name: str, resource_type: str = "audio") -> Optional[str]:
        """根据标签获取资源URL"""
        try:
            # 这里可以调用资源管理API
            # 暂时返回一个默认的音频资源
            if tag_name == "水波纹":
                return f"{settings.MINIO_PUBLIC_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/global-resources/audio/bubble_sound.wav"
            return None
        except Exception as e:
            print(f"获取资源失败: {e}")
            return None
    
    async def create_draft(self, width: int = 1080, height: int = 1920) -> Dict[str, Any]:
        """创建草稿"""
        try:
            response = requests.post(
                f"{self.base_url}/create_draft",
                json={
                    "width": width,
                    "height": height
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建草稿失败: {str(e)}")
    
    async def add_effect(self, draft_id: str, effect_type: str, start: float, end: float, 
                        track_name: str, width: int = 1080, height: int = 1920) -> Dict[str, Any]:
        """添加特效"""
        try:
            response = requests.post(
                f"{self.base_url}/add_effect",
                json={
                    "draft_id": draft_id,
                    "effect_type": effect_type,
                    "start": start,
                    "end": end,
                    "track_name": track_name,
                    "width": width,
                    "height": height
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"添加特效失败: {str(e)}")
    
    async def add_audio(self, draft_id: str, audio_url: str, start: float, end: float,
                       track_name: str, volume: float = 0.5, target_start: float = 0,
                       width: int = 1080, height: int = 1920) -> Dict[str, Any]:
        """添加音频"""
        try:
            response = requests.post(
                f"{self.base_url}/add_audio",
                json={
                    "draft_id": draft_id,
                    "audio_url": audio_url,
                    "start": start,
                    "end": end,
                    "track_name": track_name,
                    "volume": volume,
                    "target_start": target_start,
                    "width": width,
                    "height": height
                },
                timeout=60
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"添加音频失败: {str(e)}")
    
    async def add_video(self, draft_id: str, video_url: str, start: float, end: float,
                       track_name: str, width: int = 1080, height: int = 1920,
                       target_start: float = 0) -> Dict[str, Any]:
        """添加视频"""
        try:
            response = requests.post(
                f"{self.base_url}/add_video",
                json={
                    "draft_id": draft_id,
                    "video_url": video_url,
                    "start": start,
                    "end": end,
                    "track_name": track_name,
                    "width": width,
                    "height": height,
                    "target_start": target_start
                },
                timeout=60
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"添加视频失败: {str(e)}")
    
    async def add_text(self, draft_id: str, text: str, start: float, end: float,
                      font: str = "挥墨体", font_color: str = "#ffde00", font_size: float = 12.0,
                      track_name: str = "text_track_1", transform_x: float = 0,
                      transform_y: float = 0.15, font_alpha: float = 1.0,
                      border_alpha: float = 1.0, border_color: str = "#000000",
                      border_width: float = 15.0, width: int = 1080, height: int = 1920) -> Dict[str, Any]:
        """添加文本"""
        try:
            response = requests.post(
                f"{self.base_url}/add_text",
                json={
                    "draft_id": draft_id,
                    "text": text,
                    "start": start,
                    "end": end,
                    "font": font,
                    "font_color": font_color,
                    "font_size": font_size,
                    "track_name": track_name,
                    "transform_x": transform_x,
                    "transform_y": transform_y,
                    "font_alpha": font_alpha,
                    "border_alpha": border_alpha,
                    "border_color": border_color,
                    "border_width": border_width,
                    "width": width,
                    "height": height
                },
                timeout=30
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"添加文本失败: {str(e)}")
    
    async def save_draft(self, draft_id: str, draft_folder: str) -> Dict[str, Any]:
        """保存草稿"""
        try:
            response = requests.post(
                f"{self.base_url}/save_draft",
                json={
                    "draft_id": draft_id,
                    "draft_folder": draft_folder
                },
                timeout=120
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存草稿失败: {str(e)}")

capcut_service = CapCutService()

@router.post("/export-slice/{slice_id}")
async def export_slice_to_capcut(
    slice_id: int,
    draft_folder: str,
    db: AsyncSession = Depends(get_db)
):
    """导出切片到CapCut"""
    try:
        # 获取切片信息
        slice_obj = await db.get(VideoSlice, slice_id)
        if not slice_obj:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        # 获取子切片
        sub_slices_result = await db.execute(
            select(VideoSubSlice).where(VideoSubSlice.slice_id == slice_id)
        )
        sub_slices = sub_slices_result.scalars().all()
        
        # 创建草稿
        draft_result = await capcut_service.create_draft()
        if not draft_result.get("success"):
            raise HTTPException(status_code=500, detail=f"创建草稿失败: {draft_result.get('error')}")
        
        draft_id = draft_result["output"]["draft_id"]
        
        # 按顺序处理子切片
        current_time = 0
        for i, sub_slice in enumerate(sub_slices):
            # 添加水波纹特效 (前3秒)
            effect_result = await capcut_service.add_effect(
                draft_id=draft_id,
                effect_type="水波纹",
                start=current_time,
                end=current_time + 3,
                track_name=f"effect_track_{i+1}"
            )
            
            # 获取水波纹音频资源
            audio_url = await capcut_service.get_resource_by_tag("水波纹", "audio")
            if not audio_url:
                # 如果获取失败，使用默认音频
                audio_url = "http://tmpfiles.org/dl/9816523/mixkit-liquid-bubble-3000.wav"
            
            audio_result = await capcut_service.add_audio(
                draft_id=draft_id,
                audio_url=audio_url,
                start=0,
                end=3,
                track_name=f"bubble_audio_track_{i+1}",
                volume=0.5,
                target_start=current_time
            )
            
            # 添加视频
            video_result = await capcut_service.add_video(
                draft_id=draft_id,
                video_url=f"{settings.MINIO_PUBLIC_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{sub_slice.sliced_file_path}",
                start=0,
                end=sub_slice.duration,
                track_name=f"video_track_{i+1}",
                target_start=current_time
            )
            
            current_time += sub_slice.duration
        
        # 添加覆盖文本
        text_result = await capcut_service.add_text(
            draft_id=draft_id,
            text=slice_obj.cover_title,
            start=0,
            end=current_time
        )
        
        # 保存草稿
        save_result = await capcut_service.save_draft(
            draft_id=draft_id,
            draft_folder=draft_folder
        )
        
        if not save_result.get("success"):
            raise HTTPException(status_code=500, detail=f"保存草稿失败: {save_result.get('error')}")
        
        return {
            "success": True,
            "message": "导出成功",
            "draft_url": save_result.get("output", {}).get("draft_url")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

@router.get("/status")
async def get_capcut_status():
    """获取CapCut服务状态"""
    try:
        # 测试创建草稿端点来判断服务是否在线
        response = requests.post(f"{CAPCUT_API_BASE_URL}/create_draft", 
                              json={"width": 1080, "height": 1920}, 
                              timeout=5)
        return {"status": "online" if response.status_code == 200 else "offline"}
    except:
        return {"status": "offline"}