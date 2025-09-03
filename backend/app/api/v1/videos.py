from fastapi import APIRouter

# Import all the split modules
from .video_basic import router as video_basic_router
from .video_download import router as video_download_router
from .video_processing import router as video_processing_router
from .video_upload import router as video_upload_router
from .video_file_download import router as video_file_download_router

# Create the main router
router = APIRouter()

# Include all the sub-routers
router.include_router(video_basic_router)
router.include_router(video_download_router)
router.include_router(video_processing_router)
router.include_router(video_upload_router)
router.include_router(video_file_download_router)