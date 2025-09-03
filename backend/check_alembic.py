#!/usr/bin/env python3
"""
检查alembic迁移状态
"""
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from alembic import command
from alembic.config import Config
from app.core.config import Settings

def check_alembic_status():
    """检查alembic状态"""
    
    # 创建alembic配置
    # 使用相对路径而不是硬编码绝对路径，提高移植性
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_ini_path = os.path.join(script_dir, "alembic.ini")
    alembic_cfg = Config(alembic_ini_path)
    
    # 设置数据库URL
    settings = Settings()
    db_url = settings.database_url.replace('mysql+aiomysql://', 'mysql+pymysql://')
    
    # 如果是在宿主机上，调整连接参数
    if not os.path.exists('/.dockerenv'):
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        if parsed.hostname == 'mysql':
            db_url = db_url.replace('mysql://', 'mysql+pymysql://')
            db_url = db_url.replace(f"{parsed.hostname}:{parsed.port}", "localhost:3307")
    
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    try:
        print("=== 当前alembic版本 ===")
        command.current(alembic_cfg, verbose=True)
        
        print("\n=== alembic历史 ===")
        command.history(alembic_cfg, verbose=True)
        
        print("\n=== 检查迁移状态 ===")
        command.check(alembic_cfg, verbose=True)
        
    except Exception as e:
        print(f"检查alembic状态失败: {e}")

if __name__ == "__main__":
    check_alembic_status()