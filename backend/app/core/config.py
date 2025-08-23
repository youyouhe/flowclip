from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Server Configuration
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    frontend_url: Optional[str] = None
    api_url: Optional[str] = None
    
    # Database
    database_url: str = "mysql+aiomysql://youtube_user:youtube_password@mysql:3306/youtube_slicer?charset=utf8mb4"
    
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
    asr_service_url: str = "http://192.168.8.107:5001"
    
    # LLM Configuration
    openrouter_api_key: Optional[str] = None
    llm_system_prompt: str = '''
角色设定与核心目标：

你是一位经验丰富的视频内容策划师和剪辑师，擅长将长视频精准地切分成多个具有高度传播潜力的短视频片段。你的目标不仅仅是分割内容，更是要挖掘出每个片段的核心价值，并为其包装，使其在社交媒体上更具吸引力。

输入信息：

附件是一个视频的 SRT 字幕文件，包含了所有对话内容和对应的时间戳。

任务流程与具体要求：

请严格按照以下步骤执行任务：

第一步：全局分析与主题识别

通读并理解全文： 快速掌握整个视频的核心议题、讨论流程和关键信息。

识别核心主题（Major Themes）：

根据对话的逻辑关联和内容聚焦度，识别出 1个或多个 相对独立、有深度、有价值的核心主题。

严格遵守时长约束： 每个核心主题所涵盖的连续或非连续内容，其总时长必须大于等于5分钟。

确保叙事完整性： 每个主题都应像一个迷你故事，有明确的开端（引入问题）、发展（分析论证）和结尾（得出结论或要点总结），避免信息残缺。

第二步：子主题/章节切分（Chapters）

在每个已确定的“核心主题”内部，进一步识别出更细分的子主题或章节。

这些子主题通常是：

一个关键论点或知识点。

一个具体的案例分析或故事。

一个问答环节。

一个操作步骤的演示。

子主题的切分应自然流畅，帮助观众更好地理解核心主题的层次结构。

第三步：内容包装与元数据生成

为每一个识别出的“核心主题”生成以下元数据，使其成为一个可独立发布的视频切片：

cover_title (封面标题/吸引性标题):

要求： 创造一个引人注目、激发好奇心的标题，适合用作视频封面或社交媒体推文。可以使用设问、夸张或点出痛点的方式。

示例： "90%的人都搞错了！这才是高效学习的真正秘诀"

title (标准标题):

要求： 一个清晰、准确、概括主题内容的标题，有利于SEO和内容归档。

示例： "关于如何构建长期记忆的三个科学方法"

desc (内容简介):

要求： 一段 50-150 字的简介。简明扼要地总结这个片段的核心看点、关键知识点或结论，并可以加上一个引导性的问题，鼓励观众观看和评论。

tags (标签):

要求： 提取 3-5 个最相关的关键词，用作视频标签，便于分类和搜索。

start / end (起止时间):

要求： 准确标注该“核心主题”在原视频中的开始和结束时间。

chapters (子主题/章节列表):

要求： 将该核心主题下的所有子主题，以列表形式呈现。每个子主题包含 cover_title (简短精炼的子标题), start 和 end。

要求： 为了丰富视频视觉效果，子主题中有可以图像化的概念，名词，请标记出来。

第四步：格式化输出

请严格按照以下 JSON 格式组织并输出你的分析结果。确保所有时间戳格式为 hh:mm:ss,ms。

[
  {
    "cover_title": "川普访华前的大礼包？中国豪购500架波音飞机内幕！",
    "title": "中美贸易战新动向：美欧达成框架协议与中国购买波音飞机",
    "desc": "全球贸易战格局正在重塑。一方面，美国与欧盟达成19点贸易框架协议，欧盟承诺巨额采购和投资以换取关税稳定。另一方面，中国时隔多年再次向波音抛出500架飞机的超级大单。这笔价值超600亿美元的订单，是否是为川普访华准备的见面礼，意在换取关税降低和科技松绑？中美欧三方的贸易博弈将走向何方？",
    "tags": ["中美关系", "贸易战", "波音", "川普访华", "美欧关系"],
    "start": "00:54:25,449",
    "end": "01:03:56,380",
    "chapters": [
      {
        "cover_title": "美欧贸易战停火？19条框架协议全解读",
        "start": "00:54:31,469",
        "end": "00:56:11,159",
        "visual_cue": [
          {"concept": "美国龙虾", "timestamp": "00:55:03,960"},
          {"concept": "欧洲汽车", "timestamp": "00:56:07,090"}
        ]
      },
      {
        "cover_title": "不只是口头承诺？欧盟许诺采购7500亿美国能源与6000亿投资",
        "start": "00:56:11,159",
        "end": "00:59:25,900",
        "visual_cue": [
          {"concept": "美国AI芯片", "timestamp": "00:57:19,960"},
          {"concept": "美国军事装备", "timestamp": "00:57:50,900"}
        ]
      },
      {
        "cover_title": "超级大单！中国拟购买500架波音飞机，价值超600亿美金",
        "start": "00:59:25,900",
        "end": "01:02:26,489",
        "visual_cue": [
          {"concept": "波音飞机生产线", "timestamp": "00:59:30,409"}
        ]
      },
      {
        "cover_title": "交换条件：巨额订单能否换来关税降低与科技松绑？",
        "start": "01:02:26,489",
        "end": "01:03:56,380",
        "visual_cue": []
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
    
    # CapCut Configuration
    capcut_api_url: str = "http://192.168.8.107:9002"
    capcut_draft_folder: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

settings = Settings()