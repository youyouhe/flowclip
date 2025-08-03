from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/youtube/{slice_id}")
async def upload_to_youtube(
    slice_id: int,
    title: str,
    description: str,
    tags: list = None,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Upload slice {slice_id} to YouTube",
        "title": title,
        "description": description,
        "tags": tags,
        "user_id": current_user.id
    }

@router.get("/youtube/auth-url")
async def get_youtube_auth_url(current_user: User = Depends(get_current_user)):
    return {
        "message": "Get YouTube OAuth URL",
        "user_id": current_user.id
    }

@router.post("/youtube/callback")
async def handle_youtube_callback(
    code: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": "Handle YouTube OAuth callback",
        "code": code,
        "user_id": current_user.id
    }

@router.get("/status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user)
):
    return {
        "message": f"Get upload status for {upload_id}",
        "user_id": current_user.id
    }