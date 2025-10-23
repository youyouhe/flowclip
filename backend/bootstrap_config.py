#!/usr/bin/env python3
"""
Bootstrap配置管理器
用于在应用启动前提供基础配置，打破循环依赖
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BootstrapConfig:
    """Bootstrap配置管理器"""

    def __init__(self, config_file: str = None):
        self.config_file = config_file or os.path.join(os.path.dirname(__file__), '.bootstrap_config.json')
        self.config = {}
        self.load_config()

    def load_config(self):
        """加载bootstrap配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded bootstrap config from {self.config_file}")
            else:
                logger.info("Bootstrap config file not found, using environment variables")
                self.config = self.get_env_config()
                self.save_config()
        except Exception as e:
            logger.error(f"Failed to load bootstrap config: {e}")
            self.config = self.get_env_config()

    def save_config(self):
        """保存bootstrap配置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved bootstrap config to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save bootstrap config: {e}")

    def get_env_config(self) -> Dict[str, Any]:
        """从环境变量和凭证文件获取基础配置"""
        config = {
            "mysql": {
                "host": os.environ.get('MYSQL_HOST', '127.0.0.1'),
                "port": int(os.environ.get('MYSQL_PORT', '3306')),
                "user": os.environ.get('MYSQL_USER', 'youtube_user'),
                "password": os.environ.get('MYSQL_PASSWORD', ''),  # 从部署脚本获取
                "database": os.environ.get('MYSQL_DATABASE', 'youtube_slicer'),
                "root_password": os.environ.get('MYSQL_ROOT_PASSWORD', '')
            },
            "redis": {
                "url": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')
            },
            "minio": {
                "endpoint": os.environ.get('MINIO_ENDPOINT', '127.0.0.1:9000'),
                "public_endpoint": os.environ.get('MINIO_PUBLIC_ENDPOINT', ''),
                "access_key": os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
                "secret_key": os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
                "bucket_name": os.environ.get('MINIO_BUCKET_NAME', 'youtube-videos')
            },
            "secret_key": os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production'),
            "initialized": False
        }

        # 尝试从凭证文件读取动态生成的密码
        credentials_file = os.path.expanduser("~/credentials.txt")
        if os.path.exists(credentials_file):
            try:
                with open(credentials_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('MYSQL_ROOT_PASSWORD='):
                            config["mysql"]["root_password"] = line.split('=', 1)[1]
                        elif line.startswith('MYSQL_APP_PASSWORD='):
                            config["mysql"]["password"] = line.split('=', 1)[1]
                        elif line.startswith('MINIO_ACCESS_KEY='):
                            config["minio"]["access_key"] = line.split('=', 1)[1]
                        elif line.startswith('MINIO_SECRET_KEY='):
                            config["minio"]["secret_key"] = line.split('=', 1)[1]
                        elif line.startswith('SECRET_KEY='):
                            config["secret_key"] = line.split('=', 1)[1]

                print(f"Loaded credentials from {credentials_file}")
            except Exception as e:
                print(f"Warning: Failed to read credentials file {credentials_file}: {e}")
        else:
            print(f"Credentials file not found: {credentials_file}, using environment variables")

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """设置配置项"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        mysql = self.get('mysql', {})
        host = mysql.get('host', '127.0.0.1')
        port = mysql.get('port', 3306)
        user = mysql.get('user', 'youtube_user')
        password = mysql.get('password', '')
        database = mysql.get('database', 'youtube_slicer')

        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

    def is_initialized(self) -> bool:
        """检查是否已经初始化"""
        return self.get('initialized', False)

    def mark_initialized(self):
        """标记为已初始化"""
        self.set('initialized', True)

    def update_from_env(self):
        """从环境变量更新配置"""
        # 优先使用环境变量中的动态密码
        env_config = self.get_env_config()

        # 从环境变量覆盖动态密码（如果存在）
        if os.environ.get('DYNAMIC_MYSQL_PASSWORD'):
            env_config["mysql"]["password"] = os.environ.get('DYNAMIC_MYSQL_PASSWORD')
        if os.environ.get('DYNAMIC_MYSQL_ROOT_PASSWORD'):
            env_config["mysql"]["root_password"] = os.environ.get('DYNAMIC_MYSQL_ROOT_PASSWORD')
        if os.environ.get('DYNAMIC_MINIO_ACCESS_KEY'):
            env_config["minio"]["access_key"] = os.environ.get('DYNAMIC_MINIO_ACCESS_KEY')
        if os.environ.get('DYNAMIC_MINIO_SECRET_KEY'):
            env_config["minio"]["secret_key"] = os.environ.get('DYNAMIC_MINIO_SECRET_KEY')
        if os.environ.get('DYNAMIC_SECRET_KEY'):
            env_config["secret_key"] = os.environ.get('DYNAMIC_SECRET_KEY')

        self.config.update(env_config)
        self.save_config()

# 全局bootstrap配置实例
bootstrap_config = BootstrapConfig()

def get_bootstrap_config() -> BootstrapConfig:
    """获取bootstrap配置实例"""
    return bootstrap_config

def init_bootstrap_from_deployment():
    """从部署脚本初始化bootstrap配置"""
    # 这个函数会被部署脚本调用来设置动态密码
    mysql_password = os.environ.get('DYNAMIC_MYSQL_PASSWORD')
    if mysql_password:
        bootstrap_config.set('mysql.password', mysql_password)
        print("Updated MySQL password from deployment script")

    mysql_root_password = os.environ.get('DYNAMIC_MYSQL_ROOT_PASSWORD')
    if mysql_root_password:
        bootstrap_config.set('mysql.root_password', mysql_root_password)
        print("Updated MySQL root password from deployment script")

    minio_access_key = os.environ.get('DYNAMIC_MINIO_ACCESS_KEY')
    if minio_access_key:
        bootstrap_config.set('minio.access_key', minio_access_key)
        print("Updated MinIO access key from deployment script")

    minio_secret_key = os.environ.get('DYNAMIC_MINIO_SECRET_KEY')
    if minio_secret_key:
        bootstrap_config.set('minio.secret_key', minio_secret_key)
        print("Updated MinIO secret key from deployment script")

    secret_key = os.environ.get('DYNAMIC_SECRET_KEY')
    if secret_key:
        bootstrap_config.set('secret_key', secret_key)
        print("Updated secret key from deployment script")

if __name__ == "__main__":
    # 测试代码
    config = get_bootstrap_config()
    print("Bootstrap config:")
    print(json.dumps(config.config, indent=2, ensure_ascii=False))
    print(f"Database URL: {config.get_database_url()}")
    print(f"Initialized: {config.is_initialized()}")