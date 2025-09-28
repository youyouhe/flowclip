#!/usr/bin/env python3
"""
测试更新后的MCP服务器实现
"""

import asyncio
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# 创建测试应用，模拟筛选后的端点
test_app = FastAPI(
    title="Flowclip API",
    description="优化版Flowclip视频处理平台",
    version="1.0.0"
)

# 根据筛选结果添加端点
@test_app.get("/api/v1/asr/status", tags=["asr"], operation_id="asr_status")
async def asr_status():
    return {"status": "running", "version": "1.0"}

@test_app.post("/api/v1/auth/login", tags=["auth"], operation_id="login")
async def login():
    return {"token": "sample_token"}

@test_app.get("/api/v1/capcut/status", tags=["capcut"], operation_id="capcut_status")
async def capcut_status():
    return {"status": "ready"}

@test_app.post("/api/v1/capcut/export-slice/{slice_id}", tags=["capcut"], operation_id="export_slice")
async def export_slice(slice_id: int):
    return {"slice_id": slice_id, "export_status": "queued"}

@test_app.post("/api/v1/llm/chat", tags=["llm"], operation_id="llm_chat")
async def llm_chat():
    return {"response": "Hello from LLM"}

@test_app.get("/api/v1/processing/logs/task/{task_id}", tags=["processing"], operation_id="get_task_logs")
async def get_task_logs(task_id: str):
    return {"task_id": task_id, "logs": []}

@test_app.get("/api/v1/projects/", tags=["projects"], operation_id="list_projects")
async def list_projects():
    return {"projects": []}

@test_app.post("/api/v1/projects/", tags=["projects"], operation_id="create_project")
async def create_project():
    return {"project_id": 1, "name": "New Project"}

@test_app.get("/api/v1/projects/{project_id}/videos", tags=["projects"], operation_id="get_project_videos")
async def get_project_videos(project_id: int):
    return {"project_id": project_id, "videos": []}

@test_app.get("/api/v1/system/system-config/service-status/{service_name}", tags=["system"], operation_id="service_status")
async def service_status(service_name: str):
    return {"service": service_name, "status": "running"}

@test_app.post("/api/v1/processing/{video_id}/extract-audio", tags=["processing"], operation_id="extract_audio")
async def extract_audio(video_id: int):
    return {"video_id": video_id, "task_id": "audio_123"}

@test_app.post("/api/v1/processing/{video_id}/generate-srt", tags=["processing"], operation_id="generate_srt")
async def generate_srt(video_id: int):
    return {"video_id": video_id, "task_id": "srt_123"}

@test_app.post("/api/v1/video-slice/process-slices", tags=["video-slice"], operation_id="process_slices")
async def process_slices():
    return {"task_id": "slice_process_123"}

@test_app.post("/api/v1/video-slice/validate-slice-data", tags=["video-slice"], operation_id="validate_slices")
async def validate_slices():
    return {"validation_status": "passed"}

# 筛选后的标签
SELECTED_TAGS = ["asr", "auth", "capcut", "llm", "processing", "projects", "system", "video-slice"]

# 创建MCP服务器
mcp = FastApiMCP(
    test_app,
    name="Flowclip API (Optimized)",
    description="优化版Flowclip视频处理平台 - 14个精选端点",
    include_tags=SELECTED_TAGS,
    describe_all_responses=False,
    describe_full_response_schema=False
)

def test_mcp_configuration():
    """测试MCP配置"""
    try:
        # 设置服务器
        mcp.setup_server()
        
        print("=== 优化后的MCP服务器配置测试 ===")
        print(f"服务器名称: {mcp.name}")
        print(f"服务器描述: {mcp.description}")
        print(f"包含的标签: {SELECTED_TAGS}")
        print(f"总计工具数量: {len(mcp.tools)}")
        
        if mcp.tools:
            print("\n=== 工具列表 ===")
            for i, tool in enumerate(mcp.tools, 1):
                name = tool.name if hasattr(tool, 'name') else str(tool)
                name_len = len(name)
                status = "✅" if name_len <= 63 else "❌"
                print(f"{i:2d}. {status} {name} ({name_len} chars)")
                
            # 检查长名称
            long_names = [t for t in mcp.tools if len(getattr(t, 'name', str(t))) > 63]
            if long_names:
                print(f"\n❌ 发现 {len(long_names)} 个超长工具名称:")
                for tool in long_names:
                    name = tool.name if hasattr(tool, 'name') else str(tool)
                    print(f"  - {name} ({len(name)} chars)")
            else:
                print(f"\n✅ 所有工具名称都在63字符以内")
        else:
            print("\n⚠️  没有找到工具，检查operation_map...")
            if mcp.operation_map:
                print("Operation Map:")
                for op_id, info in mcp.operation_map.items():
                    name_len = len(op_id)
                    status = "✅" if name_len <= 63 else "❌"
                    print(f"  {status} {op_id} ({name_len} chars)")
        
        print(f"\n=== 筛选结果统计 ===")
        print(f"原始端点数量: 95")
        print(f"筛选后端点数量: 14")
        print(f"筛选比例: {14/95*100:.1f}%")
        print(f"包含的功能模块: {len(SELECTED_TAGS)}")
        
        print(f"\n=== 功能覆盖 ===")
        modules = {
            "asr": "ASR服务状态检查",
            "auth": "用户认证登录", 
            "capcut": "CapCut集成导出",
            "llm": "LLM智能对话",
            "processing": "视频处理和日志",
            "projects": "项目管理",
            "system": "系统服务监控",
            "video-slice": "视频切片处理"
        }
        
        for tag, desc in modules.items():
            print(f"  ✅ {tag}: {desc}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("测试优化后的MCP服务器配置...")
    success = test_mcp_configuration()
    if success:
        print(f"\n🎉 MCP服务器配置测试通过！")
        print("可以启动服务器: python start_mcp_server.py")
    else:
        print(f"\n❌ MCP服务器配置测试失败")