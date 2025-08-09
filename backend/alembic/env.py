from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import database configuration
from app.core.config import Settings
from app.core.database import Base
from app.models import User, Project, Video, Slice, SubSlice, AudioTrack, Transcript, AnalysisResult, ProcessingTask, ProcessingTaskLog, ProcessingStatus

# Get settings
settings = Settings()

# Convert async database URL to sync for alembic
def get_sync_database_url():
    """Convert async database URL to sync for alembic migrations"""
    url = settings.database_url
    
    # 如果是MySQL URL，需要处理Docker环境下的访问
    if url.startswith('mysql+aiomysql://'):
        # 从异步URL转为同步URL
        sync_url = url.replace('mysql+aiomysql://', 'mysql+pymysql://')
        
        # 检查是否需要为alembic（在宿主机运行）调整主机地址
        # Docker中的MySQL服务可以通过宿主机端口访问
        import os
        # 检查是否在Docker环境中运行
        if not os.path.exists('/.dockerenv'):
            # 在宿主机上运行，需要调整连接参数
            # 从 mysql://user:pass@host:port/db 格式解析
            import re
            from urllib.parse import urlparse
            
            parsed = urlparse(sync_url)
            hostname = parsed.hostname
            port = parsed.port
            
            # 如果hostname是容器服务名（如'mysql'），则改为localhost并使用映射端口
            if hostname == 'mysql':
                # 使用宿主机的localhost和映射端口3307
                new_hostname = 'localhost'
                new_port = 3307  # docker-compose.yml中的映射端口
                
                # 重建URL
                netloc = f"{parsed.username}:{parsed.password}@{new_hostname}:{new_port}"
                sync_url = f"{parsed.scheme}://{netloc}{parsed.path}"
                if parsed.query:
                    sync_url += f"?{parsed.query}"
                
        return sync_url
    elif url.startswith('sqlite+aiosqlite://'):
        return url.replace('sqlite+aiosqlite://', 'sqlite://')
    return url

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Use the sync database URL for alembic
    url = get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use the sync database URL for alembic instead of alembic.ini
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_sync_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
