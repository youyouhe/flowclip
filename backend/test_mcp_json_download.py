#!/usr/bin/env python3
"""
测试新的JSON格式视频下载MCP工具
"""

import asyncio
import aiohttp
import json
import base64
import os

# MCP服务器配置
MCP_SERVER_URL = "http://localhost:8002"
API_BASE_URL = "http://localhost:8001"

async def test_mcp_tools():
    """测试MCP工具列表和新的JSON下载工具"""
    
    async with aiohttp.ClientSession() as session:
        try:
            # 1. 获取MCP工具列表
            print("🔍 获取MCP工具列表...")
            async with session.get(f"{MCP_SERVER_URL}/tools") as response:
                if response.status == 200:
                    tools = await response.json()
                    print(f"✅ 成功获取 {len(tools)} 个工具")
                    
                    # 查找我们的新工具
                    download_tools = [tool for tool in tools if 'download' in tool.get('name', '').lower()]
                    print(f"📥 找到 {len(download_tools)} 个下载相关工具:")
                    for tool in download_tools:
                        print(f"  - {tool.get('name')}: {tool.get('description', 'N/A')}")
                    
                    # 检查是否包含新的JSON下载工具
                    json_download_tool = next((tool for tool in tools if tool.get('name') == 'download_video_json'), None)
                    if json_download_tool:
                        print(f"🎉 找到新的JSON下载工具: {json_download_tool['name']}")
                        print(f"   描述: {json_download_tool.get('description', 'N/A')}")
                        
                        # 显示输入参数schema
                        input_schema = json_download_tool.get('inputSchema', {})
                        properties = input_schema.get('properties', {})
                        print(f"   输入参数: {list(properties.keys())}")
                        
                        return True
                    else:
                        print("❌ 未找到 download_video_json 工具")
                        return False
                else:
                    print(f"❌ 获取工具列表失败: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return False

async def test_json_payload():
    """测试JSON负载格式"""
    
    print("\n🧪 测试JSON负载格式...")
    
    # 创建测试cookies
    test_cookies = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tFALSE\t0\ttest\tvalue"
    encoded_cookies = base64.b64encode(test_cookies.encode()).decode()
    
    # 创建JSON负载
    json_payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "project_id": 1,
        "quality": "720p",
        "cookies_file": encoded_cookies
    }
    
    print(f"✅ JSON负载创建成功:")
    print(f"   URL: {json_payload['url']}")
    print(f"   项目ID: {json_payload['project_id']}")
    print(f"   质量: {json_payload['quality']}")
    print(f"   Cookies长度: {len(json_payload['cookies_file'])} 字符")
    
    # 验证base64解码
    decoded_cookies = base64.b64decode(encoded_cookies).decode()
    assert decoded_cookies == test_cookies
    print("✅ Base64编码/解码验证成功")
    
    return json_payload

async def main():
    """主测试函数"""
    print("🚀 测试新的JSON格式视频下载MCP工具")
    print("=" * 60)
    
    # 测试MCP工具列表
    mcp_success = await test_mcp_tools()
    
    # 测试JSON负载
    json_payload = await test_json_payload()
    
    print("\n" + "=" * 60)
    if mcp_success and json_payload:
        print("🎉 所有测试通过！")
        print("\n📋 使用说明:")
        print("1. 启动MCP服务器: python app/mcp_server_complete.py")
        print("2. 使用新的JSON端点: POST /api/v1/videos/download-json")
        print("3. JSON格式请求体包含: url, project_id, quality, cookies_file(base64)")
        print("4. MCP工具名称: download_video_json")
        
        return True
    else:
        print("💥 部分测试失败！")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        exit(1)