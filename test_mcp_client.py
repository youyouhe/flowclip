#!/usr/bin/env python3
"""
MCP Client Test Script
Automates the MCP server testing process observed in the logs
"""

import json
import httpx
import asyncio
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.session_id = None
        self.authorization = None
        self.client = httpx.AsyncClient()
    
    async def initialize_session(self) -> str:
        """Initialize a new MCP session"""
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "sampling": {},
                    "roots": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "test-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json"
        }
        
        if self.authorization:
            headers["authorization"] = self.authorization
        
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract session ID from headers if available
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
        
        logger.debug(f"Session initialized: {self.session_id}")
        return self.session_id
    
    async def call_login_tool(self, username: str, password: str) -> Dict[str, Any]:
        """Call the login tool to authenticate"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "_meta": {"progressToken": 1},
                "name": "login_api_v1_auth_login_post",
                "arguments": {
                    "username": username,
                    "password": password
                }
            }
        }
        
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json"
        }
        
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        if self.authorization:
            headers["authorization"] = self.authorization
        
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Extract token from successful login
        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                login_data = content[0]
                # The login response is in the 'text' field as JSON string
                if "text" in login_data:
                    import json
                    try:
                        token_data = json.loads(login_data["text"])
                        if "access_token" in token_data:
                            self.authorization = f"Bearer {token_data['access_token']}"
                            logger.debug(f"Login successful, token: {self.authorization[:50]}...")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse login response JSON: {e}")
        
        return result
    
    async def call_get_projects_tool(self) -> Dict[str, Any]:
        """Call the get projects tool"""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "_meta": {"progressToken": 2},
                "name": "get_projects_api_v1_projects__get",
                "arguments": {}
            }
        }
        
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-session-id": self.session_id
        }
        
        if self.authorization:
            headers["authorization"] = self.authorization
            logger.debug(f"Adding authorization header for projects call: {self.authorization[:50]}...")
        else:
            logger.warning("No authorization header available for projects call")
        
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        result = response.json()
        return result
    
    async def send_initialized_notification(self):
        """Send initialized notification after successful login"""
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-session-id": self.session_id
        }
        
        if self.authorization:
            headers["authorization"] = self.authorization
        
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        logger.debug(f"Initialized notification sent, status: {response.status_code}")
        return response.status_code == 202
    
    async def terminate_session(self):
        """Terminate the current MCP session"""
        if not self.session_id:
            return
        
        headers = {
            "accept": "text/event-stream, application/json",
            "mcp-session-id": self.session_id
        }
        
        if self.authorization:
            headers["authorization"] = self.authorization
        
        response = await self.client.delete(
            f"{self.base_url}/mcp",
            headers=headers
        )
        
        logger.debug(f"Session terminated: {response.status_code}")
        self.session_id = None
        
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

async def test_mcp_workflow():
    """Test the complete MCP workflow observed in logs"""
    client = MCPClient()
    
    try:
        logger.info("=== Starting MCP Workflow Test ===")
        
        # Step 1: Initialize session (first connection)
        logger.info("1. Initializing MCP session...")
        session_id = await client.initialize_session()
        
        # Step 2: Send initialized notification (required before tool calls)
        logger.info("2. Sending initialized notification...")
        initialized_ok = await client.send_initialized_notification()
        
        # Step 3: Call login tool
        logger.info("3. Calling login tool...")
        login_result = await client.call_login_tool("hem", "123456")
        logger.debug(f"Login result: {json.dumps(login_result, indent=2)}")
        
        # Step 4: Test authenticated tool access - Get projects (in same session)
        logger.info("4. Testing authenticated tool access - Get projects...")
        projects_result = await client.call_get_projects_tool()
        logger.debug(f"Projects result: {json.dumps(projects_result, indent=2)}")
        
        # Check if we got projects data
        if "result" in projects_result and "content" in projects_result["result"]:
            content = projects_result["result"]["content"]
            if isinstance(content, list):
                logger.info(f"Successfully retrieved {len(content)} projects")
            else:
                logger.info("Successfully retrieved projects data")
        else:
            logger.warning("No projects data found in response")
        
        
        logger.info("=== MCP Workflow Test Completed Successfully ===")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    finally:
        await client.close()

if __name__ == "__main__":
    success = asyncio.run(test_mcp_workflow())
    exit(0 if success else 1)
