from fastapi import APIRouter
from .auth import router as auth_router
from .projects import router as projects_router
from .videos import router as videos_router
from .processing import router as processing_router
from .upload import router as upload_router
from .status import router as status_router
from .capcut import router as capcut_router
from .jianying import router as jianying_router
from .resource import router as resource_router
from .llm import router as llm_router
from .video_slice import router as video_slice_router
from .websocket import router as websocket_router
from .asr import router as asr_router
from .system_config import router as system_config_router
from .minio_resources import router as minio_resources_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(processing_router, prefix="/processing", tags=["processing"])
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
api_router.include_router(status_router, prefix="/status", tags=["status"])
api_router.include_router(capcut_router, prefix="/capcut", tags=["capcut"])
api_router.include_router(jianying_router, prefix="/jianying", tags=["jianying"])
api_router.include_router(resource_router, prefix="/resources", tags=["resources"])
api_router.include_router(llm_router, prefix="/llm", tags=["llm"])
api_router.include_router(video_slice_router, prefix="/video-slice", tags=["video-slice"])
api_router.include_router(websocket_router, prefix="/ws", tags=["websocket"])
api_router.include_router(asr_router, prefix="/asr", tags=["asr"])
api_router.include_router(system_config_router, prefix="/system", tags=["system"])
api_router.include_router(minio_resources_router, prefix="/minio", tags=["minio"])