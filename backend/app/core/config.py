from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./youtube_slicer.db"
    
    # MySQL Configuration
    mysql_host: str = "localhost"
    mysql_port: int = 3307
    mysql_user: str = "youtube_user"
    mysql_password: str = "youtube_password"
    mysql_database: str = "youtube_slicer"
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: Optional[str] = None
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "youtube-videos"
    minio_secure: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # Security
    secret_key: str = "your-secret-key-here-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # OpenAI
    openai_api_key: Optional[str] = None
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # YouTube API
    youtube_api_key: Optional[str] = None
    youtube_cookies_file: Optional[str] = "/home/cat/github/slice-youtube/youtube_cookies.txt"
    
    # ASR Service Configuration
    asr_service_url: str = "http://192.168.8.107:5001/asr"
    
    # LLM Configuration
    openrouter_api_key: Optional[str] = None
    llm_system_prompt: str = '''你作为一名优秀的视频切片剪辑师，附件是视频附带的SRT内容， \
                    你首先分析对话内容，根据内容提取出对话的一个或多个主题，\ 
                    每个主题涵盖的内容的时长不能低于5分钟 \
                    比如：（"start": "00:00:00,000", "end": "00:03:00,389"）,这样的主题少于5分钟，就舍弃吧， \
                    然后分析每个主题的内容，如果能提取出若个子主题，我们也将其子主题提取出来。  \
                    输出内容格式参考如下：
                        [
                            {
                                "cover_title": "XXX",
                                "title": "XXX",
                                "desc": "XXX",
                                "tags": ["xxx", "xxx", ],
                                "start": "xx:xx:xx,xxx",
                                "end": "xx:xx:xx,xxx"
                                "subtitles":[
                                    {
                                        "cover_title": "XXX",
                                        "start": "xx:xx:xx,xxx",
                                        "end": "xx:xx:xx,xxx"
                                    }，
                                    {
                                        "cover_title": "XXX",
                                        "start": "xx:xx:xx,xxx",
                                        "end": "xx:xx:xx,xxx"
                                    }
                                ]
                            }
                        ]                    
                    '''
    
    # Application
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    sqlalchemy_echo: bool = False
    api_base_url: str = "http://localhost:8000"
    frontend_url: Optional[str] = None
    
    # Temporary directory
    temp_dir: Optional[str] = "/tmp"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()