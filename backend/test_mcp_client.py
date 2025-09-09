#!/usr/bin/env python3
"""
Test script for MCP client to interact with the YouTube Slicer MCP server
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fastmcp.client import Client

async def demo():
    """Demonstrate MCP client functionality by connecting to the running MCP server"""
    # Connect to the MCP server running on port 8002
    async with Client("http://localhost:8002/mcp") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools count: {len(tools)}")
        print(f"First 5 tools: {[t.name for t in tools[:5]]}")
        
        # List available resources
        resources = await client.list_resources()
        print(f"Available resources count: {len(resources)}")
        print(f"All resources: {[r.name for r in resources]}")
        
        # Try to list resource templates
        try:
            resource_templates = await client.list_resource_templates()
            print(f"Available resource templates count: {len(resource_templates)}")
            print(f"All resource templates: {[rt.name for rt in resource_templates]}")
        except Exception as e:
            print(f"Could not list resource templates: {e}")
        
        # Get API information resource
        try:
            result = await client.read_resource("http://youtube-slicer/api/info")
            print(f"API Info: {result}")
        except Exception as e:
            print(f"Could not read API info resource: {e}")
        
        print("MCP client test completed successfully!")

if __name__ == "__main__":
    asyncio.run(demo())