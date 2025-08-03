from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import create_tables
from app.models import LLMAnalysis, VideoSlice, VideoSubSlice
from app.api.v1 import projects, videos, auth, processing, upload, llm, video_slice, status, websocket
import uvicorn
import logging
from app.core.config import settings
from app.services.minio_client import minio_service

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 过滤掉SQLAlchemy和aiosqlite的DEBUG信息
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

app = FastAPI(
    title="YouTube Slicer API",
    description="A comprehensive API for YouTube video processing and slicing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://192.168.8.107:3000",
        "http://0.0.0.0:3000"
    ],  # Allow specific frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["videos"])
app.include_router(processing.router, prefix="/api/v1/processing", tags=["processing"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["llm"])
app.include_router(video_slice.router, prefix="/api/v1/video-slice", tags=["video-slice"])
app.include_router(status.router, prefix="/api/v1/status", tags=["status"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])

@app.on_event("startup")
async def startup_event():
    await create_tables()
    # 初始化MinIO桶
    await minio_service.ensure_bucket_exists()
    
    # 启动进度更新服务
    from app.services.progress_service import progress_service
    await progress_service.start()

@app.get("/")
async def root():
    return {
        "message": "YouTube Slicer API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("shutdown")
async def shutdown_event():
    # 停止进度更新服务
    from app.services.progress_service import progress_service
    await progress_service.stop()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )