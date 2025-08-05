from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import create_tables
from app.models import LLMAnalysis, VideoSlice, VideoSubSlice
from app.api.v1 import projects, videos, auth, processing, upload, llm, video_slice, status, websocket
import uvicorn
import logging
import asyncio
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
    title="video slice tools API",
    description="A comprehensive API for video processing and slicing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
# Get allowed origins from environment or use defaults
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "http://0.0.0.0:3000"
]

# Add frontend URL from environment if provided
frontend_url = settings.frontend_url
if frontend_url and frontend_url not in allowed_origins:
    allowed_origins.append(frontend_url)

# Also add the frontend URL with different formats if it's an IP
if frontend_url:
    import re
    # Extract host:port from URL
    match = re.match(r'https?://([^:/]+)(?::(\d+))?', frontend_url)
    if match:
        host, port = match.groups()
        port = port or "3000"
        
        # Add variations
        variants = [
            f"http://{host}:{port}",
            f"https://{host}:{port}",
            f"http://{host}:3000",
            f"https://{host}:3000"
        ]
        for variant in variants:
            if variant not in allowed_origins:
                allowed_origins.append(variant)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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

async def wait_for_database(max_retries=30, retry_interval=2):
    """等待数据库连接就绪"""
    from app.core.database import async_engine
    import sqlalchemy
    
    for attempt in range(max_retries):
        try:
            async with async_engine.connect() as conn:
                await conn.execute(sqlalchemy.text("SELECT 1"))
                logging.info(f"Database connection successful on attempt {attempt + 1}")
                return True
        except Exception as e:
            logging.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_interval)
            else:
                logging.error("Database connection failed after all retries")
                return False

async def wait_for_redis(max_retries=30, retry_interval=2):
    """等待Redis连接就绪"""
    import redis.asyncio as redis
    
    for attempt in range(max_retries):
        try:
            redis_client = redis.from_url(settings.redis_url)
            await redis_client.ping()
            await redis_client.close()
            logging.info(f"Redis connection successful on attempt {attempt + 1}")
            return True
        except Exception as e:
            logging.warning(f"Redis connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_interval)
            else:
                logging.error("Redis connection failed after all retries")
                return False

@app.on_event("startup")
async def startup_event():
    # 等待数据库和Redis就绪
    logging.info("Waiting for database connection...")
    if not await wait_for_database():
        logging.error("Failed to connect to database. Exiting.")
        return
    
    logging.info("Waiting for Redis connection...")
    if not await wait_for_redis():
        logging.error("Failed to connect to Redis. Exiting.")
        return
    
    # 数据库连接成功，创建表
    await create_tables()
    
    # 初始化MinIO桶
    await minio_service.ensure_bucket_exists()
    
    # 启动进度更新服务
    from app.services.progress_service import progress_service
    await progress_service.start()
    
    logging.info("Application startup completed successfully")

@app.get("/")
async def root():
    return {
        "message": "video slice tools API",
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