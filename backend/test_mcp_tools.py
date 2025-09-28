#!/usr/bin/env python3
"""
Test MCP tools and naming
"""

import asyncio
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Create test app with operation_ids to control naming
test_app = FastAPI(
    title="Flowclip API",
    description="A comprehensive API for video processing and slicing",
    version="1.0.0"
)

# Add routes with explicit operation_id to control MCP tool names
@test_app.post("/api/v1/auth/login", tags=["auth"], operation_id="login")
async def login_endpoint():
    return {"message": "login"}

@test_app.post("/api/v1/auth/register", tags=["auth"], operation_id="register") 
async def register_endpoint():
    return {"message": "register"}

@test_app.get("/api/v1/projects", tags=["projects"], operation_id="list_projects")
async def list_projects_endpoint():
    return {"projects": []}

@test_app.post("/api/v1/projects", tags=["projects"], operation_id="create_project")
async def create_project_endpoint():
    return {"message": "create_project"}

@test_app.get("/api/v1/videos", tags=["videos"], operation_id="list_videos")
async def list_videos_endpoint():
    return {"videos": []}

@test_app.post("/api/v1/videos/download", tags=["videos"], operation_id="download_video")
async def download_video_endpoint():
    return {"message": "download_video"}

@test_app.post("/api/v1/processing/extract-audio/{video_id}", tags=["processing"], operation_id="extract_audio")
async def extract_audio_endpoint(video_id: int):
    return {"message": f"extract_audio for video {video_id}"}

@test_app.post("/api/v1/processing/generate-transcript/{video_id}", tags=["processing"], operation_id="generate_transcript")
async def generate_transcript_endpoint(video_id: int):
    return {"message": f"generate_transcript for video {video_id}"}

@test_app.post("/api/v1/processing/analyze-with-llm/{video_id}", tags=["processing"], operation_id="analyze_video")
async def analyze_video_endpoint(video_id: int):
    return {"message": f"analyze_video for video {video_id}"}

@test_app.get("/api/v1/status/task/{task_id}", tags=["status"], operation_id="get_task_status")
async def get_task_status_endpoint(task_id: str):
    return {"message": f"task status for {task_id}"}

# Excluded routes
@test_app.post("/api/v1/upload/file", tags=["upload"], operation_id="upload_file")
async def upload_file_endpoint():
    return {"message": "upload_file"}

# Core tags
CORE_TAGS = ["auth", "projects", "videos", "processing", "status"]

# Create MCP server
mcp = FastApiMCP(
    test_app,
    name="Flowclip API",
    description="Flowclip视频处理平台",
    include_tags=CORE_TAGS,
    describe_all_responses=False,
    describe_full_response_schema=False
)

def test_mcp_tools():
    """Test MCP tools"""
    try:
        # Setup the server to populate tools
        mcp.setup_server()
        
        print("=== MCP Tools Analysis ===")
        print(f"Total tools: {len(mcp.tools)}")
        print(f"Operation map: {len(mcp.operation_map)} operations")
        
        if mcp.tools:
            for tool in mcp.tools:
                name = tool.name if hasattr(tool, 'name') else str(tool)
                name_len = len(name)
                status = "✅" if name_len <= 63 else "❌"
                print(f"{status} {name} ({name_len} chars)")
                if name_len > 63:
                    print(f"    Tool object: {tool}")
        else:
            print("No tools found. Checking operation_map...")
            for op_id, info in mcp.operation_map.items():
                name_len = len(op_id)
                status = "✅" if name_len <= 63 else "❌"
                print(f"{status} {op_id} ({name_len} chars) -> {info}")
        
        return mcp.tools
        
    except Exception as e:
        print(f"Error testing MCP tools: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    print("Testing MCP tool names...")
    tools = test_mcp_tools()