from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/extract-audio/{video_id}")
async def extract_audio(
    video_id: int,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Extract audio from video {video_id}",
        "user_id": current_user.id
    }

@router.post("/asr/{video_id}")
async def perform_asr(
    video_id: int,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Perform ASR on video {video_id}",
        "user_id": current_user.id
    }

@router.post("/analyze/{video_id}")
async def analyze_content(
    video_id: int,
    prompt: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Analyze content with LLM for video {video_id}",
        "prompt": prompt,
        "user_id": current_user.id
    }

@router.post("/slice/{video_id}")
async def slice_video(
    video_id: int,
    slices: list,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Slice video {video_id}",
        "slices": slices,
        "user_id": current_user.id
    }

@router.get("/status/{task_id}")
async def get_processing_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Get processing status for task {task_id}",
        "user_id": current_user.id
    }