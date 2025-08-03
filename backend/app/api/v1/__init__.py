from fastapi import APIRouter
from .auth import router as auth_router
from .projects import router as projects_router
from .videos import router as videos_router
from .processing import router as processing_router
from .upload import router as upload_router
from .status import router as status_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(processing_router, prefix="/processing", tags=["processing"])
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
api_router.include_router(status_router, prefix="/status", tags=["status"])