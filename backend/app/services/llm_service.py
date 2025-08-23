"""
LLM服务模块 - 集成OpenRouter API访问Google Gemini模型
"""
import aiohttp
import asyncio
import json
import subprocess
import logging
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.services.system_config_service import SystemConfigService
from app.core.database import get_sync_db_context

# 设置日志
logger = logging.getLogger(__name__)

class LLMService:
    """LLM服务类"""
    
    def __init__(self):
        self.base_url = "https://openrouter.ai/api/v1"
        #self.model = "google/gemini-2.5-flash-lite"
        self.model = "google/gemini-2.5-flash"
        self.default_system_prompt = settings.llm_system_prompt
        
        logger.info(f"初始化LLM服务 - 模型: {self.model}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        调用LLM进行对话补全
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            system_prompt: 系统提示词，如果为None则使用默认提示词
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成令牌数
            
        Returns:
            LLM响应结果
        """
        # 动态获取最新的API密钥
        with get_sync_db_context() as db:
            await SystemConfigService.update_settings_from_db(db)
        
        api_key = settings.openrouter_api_key
        logger.info(f"开始LLM对话请求 - 消息数量: {len(messages)}, 模型: {self.model}")
        
        # 检查API密钥
        if not api_key or api_key == "your-key-here":
            logger.warning("OPENROUTER_API_KEY未设置或为占位符 - LLM服务不可用")
            raise Exception("OPENROUTER_API_KEY未设置或为占位符 - LLM服务不可用")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://youtube-slicer.local",  # 你的应用域名
            "X-Title": "video slice tools",  # 你的应用名称
        }
        
        # 构建消息列表
        api_messages = []
        
        # 添加系统提示词
        final_system_prompt = system_prompt or self.default_system_prompt
        if final_system_prompt:
            api_messages.append({
                "role": "system",
                "content": final_system_prompt
            })
        
        # 添加用户消息
        api_messages.extend(messages)
        
        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        logger.info(f"准备发送请求到: {self.base_url}/chat/completions")
        logger.info(f"请求头: {headers}")
        logger.info(f"请求负载: {payload}")
        
        try:
            # 尝试不同的连接配置
            connector_configs = [
                aiohttp.TCPConnector(ssl=True, force_close=True),
                aiohttp.TCPConnector(ssl=False, force_close=True),
                aiohttp.TCPConnector(ssl=True, force_close=False),
                aiohttp.TCPConnector(ssl=False, force_close=False),
            ]
            
            timeout = aiohttp.ClientTimeout(total=60, connect=30)
            
            for i, connector in enumerate(connector_configs):
                try:
                    ssl_enabled = hasattr(connector, '_ssl') and connector._ssl is not None
                    logger.info(f"尝试连接器配置 {i+1}: ssl={ssl_enabled}, force_close={connector.force_close}")
                    
                    async with aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers=headers
                    ) as session:
                        logger.info("创建HTTP会话成功，开始发送请求...")
                        
                        async with session.post(
                            f"{self.base_url}/chat/completions",
                            json=payload
                        ) as response:
                            logger.info(f"收到响应 - 状态码: {response.status}")
                            logger.info(f"响应头: {dict(response.headers)}")
                            
                            if response.status != 200:
                                response_text = await response.text()
                                logger.error(f"响应内容: {response_text}")
                            
                            response.raise_for_status()
                            result = await response.json()
                            logger.info(f"LLM请求成功 - 响应: {result}")
                            return result
                            
                except Exception as config_error:
                    logger.error(f"连接器配置 {i+1} 失败: {type(config_error).__name__}: {config_error}")
                    if i == len(connector_configs) - 1:
                        # 最后一个配置也失败了，抛出异常
                        raise
                    await asyncio.sleep(1)  # 短暂延迟后重试
                    continue
                
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP响应错误: {e.status}")
            try:
                response_text = await e.response.text()
                logger.error(f"响应内容: {response_text}")
                error_detail = response_text.get('error', {}).get('message', str(e))
            except:
                error_detail = str(e)
            raise Exception(f"LLM API请求失败: {error_detail}")
        except aiohttp.ClientError as e:
            logger.error(f"网络请求错误: {type(e).__name__}: {str(e)}")
            # 尝试使用curl作为备选方案
            logger.info("尝试使用curl作为备选方案...")
            try:
                return await self._curl_fallback(payload, headers)
            except Exception as curl_error:
                logger.error(f"Curl备选方案也失败: {curl_error}")
                raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"LLM服务异常: {type(e).__name__}: {str(e)}")
            raise Exception(f"LLM服务异常: {str(e)}")
    
    async def _curl_fallback(self, payload: Dict, headers: Dict) -> Dict[str, Any]:
        """使用curl作为备选方案"""
        try:
            # 构建curl命令
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                f"{self.base_url}/chat/completions",
                '-H', 'Content-Type: application/json',
                '-H', f"Authorization: {headers['Authorization']}",
                '-H', f"HTTP-Referer: {headers['HTTP-Referer']}",
                '-H', f"X-Title: {headers['X-Title']}",
                '-d', json.dumps(payload)
            ]
            
            logger.info(f"执行curl命令: {' '.join(curl_cmd)}")
            
            # 在事件循环中执行curl
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, subprocess.run, curl_cmd, 
                                              capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                logger.error(f"Curl执行失败: {result.stderr}")
                raise Exception(f"Curl执行失败: {result.stderr}")
            
            logger.info(f"Curl响应: {result.stdout}")
            response = json.loads(result.stdout)
            return response
            
        except subprocess.TimeoutExpired:
            logger.error("Curl请求超时")
            raise Exception("Curl请求超时")
        except json.JSONDecodeError as e:
            logger.error(f"解析curl响应失败: {e}")
            raise Exception(f"解析curl响应失败: {e}")
        except Exception as e:
            logger.error(f"Curl备选方案异常: {type(e).__name__}: {str(e)}")
            raise Exception(f"Curl备选方案异常: {str(e)}")
    
    async def analyze_video_content(
        self,
        srt_content: str,
        user_question: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析视频内容
        
        Args:
            srt_content: SRT字幕内容
            user_question: 用户问题
            system_prompt: 自定义系统提示词
            
        Returns:
            分析结果
        """
        # 构建包含SRT内容的用户消息
        user_message = f"""请基于以下视频字幕内容来回答我的问题：

视频字幕内容：
{srt_content}

我的问题是：
{user_question}

请基于字幕内容提供详细的分析和回答。"""
        
        messages = [
            {
                "role": "user",
                "content": user_message
            }
        ]
        
        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,  # 分析任务使用较低温度以获得更稳定的结果
            max_tokens=2000
        )
    
    async def simple_chat(self, message: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        简单对话
        
        Args:
            message: 用户消息
            system_prompt: 自定义系统提示词
            
        Returns:
            对话结果
        """
        messages = [
            {
                "role": "user", 
                "content": message
            }
        ]
        
        return await self.chat_completion(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1000
        )

# 创建全局LLM服务实例
llm_service = LLMService()