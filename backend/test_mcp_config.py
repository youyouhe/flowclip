#!/usr/bin/env python3
"""
Test MCP configuration without full app dependencies
"""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Create a simple test app
test_app = FastAPI(
    title="Flowclip API",
    description="A comprehensive API for video processing and slicing",
    version="1.0.0"
)

# Add some test routes with the same tags as the real app
@test_app.post("/api/v1/auth/login", tags=["auth"])
async def login():
    return {"message": "login"}

@test_app.post("/api/v1/auth/register", tags=["auth"]) 
async def register():
    return {"message": "register"}

@test_app.get("/api/v1/projects", tags=["projects"])
async def list_projects():
    return {"message": "list_projects"}

@test_app.post("/api/v1/projects", tags=["projects"])
async def create_project():
    return {"message": "create_project"}

@test_app.get("/api/v1/videos", tags=["videos"])
async def list_videos():
    return {"message": "list_videos"}

@test_app.post("/api/v1/videos/download", tags=["videos"])
async def download_video():
    return {"message": "download_video"}

@test_app.post("/api/v1/processing/extract-audio/{video_id}", tags=["processing"])
async def extract_audio(video_id: int):
    return {"message": f"extract_audio for video {video_id}"}

@test_app.post("/api/v1/processing/generate-transcript/{video_id}", tags=["processing"])
async def generate_transcript(video_id: int):
    return {"message": f"generate_transcript for video {video_id}"}

@test_app.get("/api/v1/status/task/{task_id}", tags=["status"])
async def get_task_status(task_id: str):
    return {"message": f"task status for {task_id}"}

# Add some excluded routes
@test_app.post("/api/v1/upload/file", tags=["upload"])
async def upload_file():
    return {"message": "upload_file"}

@test_app.get("/api/v1/minio/buckets", tags=["minio"])
async def list_buckets():
    return {"message": "list_buckets"}

# Core tags to include
CORE_TAGS = [
    "auth", 
    "projects",
    "videos", 
    "processing",
    "status"
]

# Create MCP server
mcp = FastApiMCP(
    test_app,
    name="Flowclip API",
    description="Flowclip视频处理平台 - 提供视频下载、处理、分析和切片功能",
    include_tags=CORE_TAGS,
    describe_all_responses=False,
    describe_full_response_schema=False
)

if __name__ == "__main__":
    print("=== MCP Server Configuration Test ===")
    print(f"Name: {mcp.name}")
    print(f"Description: {mcp.description}")
    print(f"Include tags: {CORE_TAGS}")
    
    # Get all endpoints from the app
    all_routes = []
    for route in test_app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            for method in route.methods:
                if method != 'HEAD':  # Skip HEAD methods
                    tags = getattr(route, 'tags', [])
                    all_routes.append({
                        'method': method,
                        'path': route.path,
                        'tags': tags,
                        'included': bool(set(tags) & set(CORE_TAGS))
                    })
    
    print(f"\n=== 路由分析 (总计 {len(all_routes)} 个端点) ===")
    included_count = 0
    excluded_count = 0
    
    for route in all_routes:
        status = "✅ 包含" if route['included'] else "❌ 排除"
        if route['included']:
            included_count += 1
        else:
            excluded_count += 1
            
        print(f"{status} {route['method']:6} {route['path']:50} tags: {route['tags']}")
    
    print(f"\n=== 总结 ===")
    print(f"包含的端点: {included_count}")
    print(f"排除的端点: {excluded_count}")
    print(f"这样可以大大减少MCP工具数量，避免名称过长的问题")
    
    # Test tool name generation (这需要更深入的API访问)
    print(f"\n=== 工具名称测试 ===")
    print("MCP工具将基于FastAPI的operation_id或路径自动生成名称")
    print("通过标签过滤，我们只保留核心功能，避免长名称问题")