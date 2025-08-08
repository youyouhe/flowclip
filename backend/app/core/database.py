from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.core.config import settings

class Base(DeclarativeBase):
    pass

# MySQL specific configuration
if "mysql" in settings.database_url.lower():
    # Async engine for FastAPI
    async_engine = create_async_engine(
        settings.database_url,
        echo=settings.sqlalchemy_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
        isolation_level="READ COMMITTED",  # Allow reading committed changes for real-time updates
        connect_args={
            "charset": "utf8mb4",
            "autocommit": False,  # Disable autocommit for better consistency
        }
    )
    
    # Sync engine for Celery tasks
    sync_database_url = settings.database_url.replace("+aiomysql", "")
    sync_database_url = sync_database_url.replace("mysql://", "mysql+pymysql://")
    sync_engine = create_engine(
        sync_database_url,
        echo=settings.sqlalchemy_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
        isolation_level="READ COMMITTED",  # Allow reading committed changes for real-time updates
        connect_args={
            "charset": "utf8mb4",
            "autocommit": False,  # Disable autocommit for better consistency
        }
    )
else:
    # SQLite configuration
    async_engine = create_async_engine(
        settings.database_url,
        echo=settings.sqlalchemy_echo,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    
    # Sync engine for Celery tasks
    sync_database_url = settings.database_url.replace("+aiosqlite", "")
    sync_engine = create_engine(
        sync_database_url,
        echo=settings.sqlalchemy_echo,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

# Async session for FastAPI
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync session for Celery tasks
SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_sync_db():
    """Get synchronous database session for Celery tasks"""
    return SyncSessionLocal()

class SyncDBContext:
    """上下文管理器用于同步数据库会话"""
    def __enter__(self):
        self.db = SyncSessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

def get_sync_db_context():
    """获取同步数据库会话上下文管理器"""
    return SyncDBContext()

async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def create_sync_tables():
    """Create tables using sync engine"""
    Base.metadata.create_all(bind=sync_engine)