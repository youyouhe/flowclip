#!/usr/bin/env python3
"""
Test script to call the health check endpoint via MCP
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fastmcp.client import Client

async def test_health_check():
    """Test the health check endpoint"""
    # Connect to the MCP server running on port 8002
    async with Client("http://localhost:8002/sse") as client:
        print("Connected to MCP server")
        
        # List available resources to confirm health check is there
        resources = await client.list_resources()
        health_resources = [r for r in resources if 'health' in r.name.lower()]
        print(f"Health-related resources: {[r.name for r in health_resources]}")
        
        # Print full resource info for debugging
        for r in health_resources:
            print(f"Resource: {r.name}, URI: {r.uri}")
        
        # Try to read the health check resource using its URI
        try:
            result = await client.read_resource("resource://health_check_health_get")
            print(f"Health check result: {result}")
        except Exception as e:
            print(f"Error reading health check resource: {e}")
            
        # Also check the root resource
        root_resources = [r for r in resources if r.name == 'root']
        if root_resources:
            for r in root_resources:
                print(f"Root resource: {r.name}, URI: {r.uri}")
            try:
                result = await client.read_resource("resource://root")
                print(f"Root endpoint result: {result}")
            except Exception as e:
                print(f"Error reading root resource: {e}")

if __name__ == "__main__":
    asyncio.run(test_health_check())