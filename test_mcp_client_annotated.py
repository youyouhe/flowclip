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

# 配置日志级别为DEBUG，输出详细调试信息
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MCPClient:
    """MCP客户端类，用于测试MCP服务器功能"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        """
        初始化MCP客户端
        Args:
            base_url: MCP服务器基础URL，默认为本地8002端口
        """
        self.base_url = base_url
        self.session_id = None  # 存储MCP会话ID
        self.authorization = None  # 存储认证令牌
        self.client = httpx.AsyncClient()  # 异步HTTP客户端
    
    async def initialize_session(self) -> str:
        """
        初始化MCP会话
        发送initialize请求建立新的MCP会话，获取会话ID
        Returns:
            str: 会话ID
        """
        # 构造initialize请求的JSON-RPC负载
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
        
        # 设置请求头
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json"
        }
        
        # 如果已有认证令牌，则添加到请求头
        if self.authorization:
            headers["authorization"] = self.authorization
        
        # 发送POST请求到MCP端点
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        # 检查HTTP响应状态码
        response.raise_for_status()
        result = response.json()
        
        # 从响应头中提取会话ID
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
        
        logger.debug(f"Session initialized: {self.session_id}")
        return self.session_id
    
    async def call_login_tool(self, username: str, password: str) -> Dict[str, Any]:
        """
        调用登录工具进行用户认证
        Args:
            username: 用户名
            password: 密码
        Returns:
            Dict[str, Any]: 登录响应结果
        """
        # 构造工具调用的JSON-RPC负载
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
        
        # 设置请求头
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json"
        }
        
        # 添加会话ID和认证令牌到请求头
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        if self.authorization:
            headers["authorization"] = self.authorization
        
        # 发送工具调用请求
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 从登录响应中提取JWT令牌
        if "result" in result and "content" in result["result"]:
            content = result["result"]["content"]
            if isinstance(content, list) and len(content) > 0:
                login_data = content[0]
                # 登录响应在text字段中作为JSON字符串
                if "text" in login_data:
                    import json
                    try:
                        token_data = json.loads(login_data["text"])
                        if "access_token" in token_data:
                            # 保存Bearer令牌用于后续认证
                            self.authorization = f"Bearer {token_data['access_token']}"
                            logger.debug(f"Login successful, token: {self.authorization[:50]}...")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse login response JSON: {e}")
        
        return result
    
    async def call_get_projects_tool(self) -> Dict[str, Any]:
        """
        调用获取项目列表工具
        Returns:
            Dict[str, Any]: 项目列表响应结果
        """
        # 构造获取项目工具调用的JSON-RPC负载
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
        
        # 设置请求头，必须包含会话ID
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-session-id": self.session_id
        }
        
        # 如果有认证令牌则添加到请求头
        if self.authorization:
            headers["authorization"] = self.authorization
            logger.debug(f"Adding authorization header for projects call: {self.authorization[:50]}...")
        else:
            logger.warning("No authorization header available for projects call")
        
        # 发送工具调用请求
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        response.raise_for_status()
        result = response.json()
        return result
    
    async def send_initialized_notification(self):
        """
        发送初始化完成通知
        在会话初始化后必须发送此通知，才能进行工具调用
        Returns:
            bool: 是否发送成功
        """
        # 构造初始化通知的JSON-RPC负载
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        # 设置请求头
        headers = {
            "accept": "application/json, text/event-stream",
            "content-type": "application/json",
            "mcp-session-id": self.session_id
        }
        
        # 添加认证令牌到请求头
        if self.authorization:
            headers["authorization"] = self.authorization
        
        # 发送初始化通知
        response = await self.client.post(
            f"{self.base_url}/mcp",
            json=payload,
            headers=headers
        )
        
        logger.debug(f"Initialized notification sent, status: {response.status_code}")
        return response.status_code == 202
    
    async def terminate_session(self):
        """
        终止当前MCP会话
        发送DELETE请求结束会话
        """
        # 如果没有会话ID则直接返回
        if not self.session_id:
            return
        
        # 设置请求头
        headers = {
            "accept": "text/event-stream, application/json",
            "mcp-session-id": self.session_id
        }
        
        # 添加认证令牌到请求头
        if self.authorization:
            headers["authorization"] = self.authorization
        
        # 发送DELETE请求终止会话
        response = await self.client.delete(
            f"{self.base_url}/mcp",
            headers=headers
        )
        
        logger.debug(f"Session terminated: {response.status_code}")
        self.session_id = None  # 清空会话ID
        
    async def close(self):
        """
        关闭HTTP客户端连接
        """
        await self.client.aclose()

async def test_mcp_workflow():
    """
    测试完整的MCP工作流程
    按照标准MCP协议顺序执行：初始化→通知→工具调用
    """
    client = MCPClient()
    
    try:
        logger.info("=== Starting MCP Workflow Test ===")
        
        # 步骤1: 初始化MCP会话
        logger.info("1. Initializing MCP session...")
        session_id = await client.initialize_session()
        
        # 步骤2: 发送初始化完成通知（工具调用前必需）
        logger.info("2. Sending initialized notification...")
        initialized_ok = await client.send_initialized_notification()
        
        # 步骤3: 调用登录工具进行认证
        logger.info("3. Calling login tool...")
        login_result = await client.call_login_tool("hem", "123456")
        logger.debug(f"Login result: {json.dumps(login_result, indent=2)}")
        
        # 步骤4: 调用需要认证的工具 - 获取项目列表
        logger.info("4. Testing authenticated tool access - Get projects...")
        projects_result = await client.call_get_projects_tool()
        logger.debug(f"Projects result: {json.dumps(projects_result, indent=2)}")
        
        # 检查项目数据是否成功获取
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
    # 运行异步测试函数并根据结果退出
    success = asyncio.run(test_mcp_workflow())
    exit(0 if success else 1)
