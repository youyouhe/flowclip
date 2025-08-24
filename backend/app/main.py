from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import create_tables
from app.models import LLMAnalysis, VideoSlice, VideoSubSlice
from app.api.v1 import api_router
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
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)

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
    "http://0.0.0.0:3000",
    "http://192.168.8.107:3000",  # 局域网访问
    "http://frontend:3000"  # Docker内部访问
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
app.include_router(api_router, prefix="/api/v1")

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
    
    # 从数据库加载系统配置
    from app.services.system_config_service import SystemConfigService
    from app.core.database import get_sync_db
    try:
        db = get_sync_db()
        # 使用同步版本的函数，避免在异步上下文中使用asyncio.run()
        SystemConfigService.update_settings_from_db_sync(db)
        db.close()
        logging.info("System configurations loaded from database")
    except Exception as e:
        logging.warning(f"Failed to load system configurations from database: {e}")
    
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