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
        # LLM服务使用动态配置，不在初始化时固定配置值
        logger.info("初始化LLM服务")
        
    def _get_current_config(self):
        """获取当前最新的配置"""
        with get_sync_db_context() as db:
            SystemConfigService.update_settings_from_db_sync(db)

        base_url = getattr(settings, 'llm_base_url', 'https://openrouter.ai/api/v1')
        model = getattr(settings, 'llm_model_type', 'google/gemini-2.5-flash')
        default_system_prompt = settings.llm_system_prompt

        # 确保数值类型配置正确转换
        try:
            default_temperature = float(getattr(settings, 'llm_temperature', 0.7))
        except (ValueError, TypeError):
            default_temperature = 0.7

        try:
            default_max_tokens = int(getattr(settings, 'llm_max_tokens', 65535))
        except (ValueError, TypeError):
            default_max_tokens = 65535

        api_key = settings.openrouter_api_key

        return {
            'base_url': base_url,
            'model': model,
            'default_system_prompt': default_system_prompt,
            'default_temperature': default_temperature,
            'default_max_tokens': default_max_tokens,
            'api_key': api_key
        }
    
    async def get_available_models(self, filter_provider: Optional[str] = "google") -> List[Dict[str, Any]]:
        """
        从OpenRouter API获取可用模型列表
        
        Args:
            filter_provider: 筛选特定提供商的模型，默认为"google"
            
        Returns:
            包含模型信息的列表
        """
        # 动态获取最新的配置
        config = self._get_current_config()
        
        api_key = config['api_key']
        logger.info("开始获取OpenRouter可用模型列表")
        
        # 检查API密钥
        if not api_key or api_key == "your-key-here":
            logger.warning("OPENROUTER_API_KEY未设置或为占位符 - 无法获取模型列表")
            return []
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=60, connect=30)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(f"{self.base_url}/models") as response:
                    if response.status == 200:
                        result = await response.json()
                        # 提取模型数据
                        models = result.get("data", [])
                        logger.info(f"成功获取到 {len(models)} 个模型")
                        
                        # 如果指定了提供商筛选器，则筛选模型
                        if filter_provider:
                            filtered_models = [model for model in models if model.get("id", "").startswith(filter_provider)]
                            logger.info(f"筛选后得到 {len(filtered_models)} 个 {filter_provider} 模型")
                            return filtered_models
                        
                        return models
                    else:
                        error_text = await response.text()
                        logger.error(f"获取模型列表失败: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"获取模型列表时发生异常: {type(e).__name__}: {str(e)}")
            return []
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
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
        # 动态获取最新的配置
        config = self._get_current_config()
        
        api_key = config['api_key']
        logger.info(f"开始LLM对话请求 - 消息数量: {len(messages)}, 模型: {config['model']}")
        
        # 检查API密钥
        if not api_key or api_key == "your-key-here":
            logger.warning("OPENROUTER_API_KEY未设置或为占位符 - LLM服务不可用")
            raise Exception("OPENROUTER_API_KEY未设置或为占位符 - LLM服务不可用")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://youtube-slicer.local",  # 你的应用域名
            "X-Title": "Flowclip",  # 你的应用名称
        }
        
        # 构建消息列表
        api_messages = []
        
        # 添加系统提示词
        final_system_prompt = system_prompt or config['default_system_prompt']
        if final_system_prompt:
            api_messages.append({
                "role": "system",
                "content": final_system_prompt
            })
        
        # 添加用户消息
        api_messages.extend(messages)
        
        payload = {
            "model": config['model'],
            "messages": api_messages,
            "temperature": temperature if temperature is not None else config['default_temperature'],
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        else:
            payload["max_tokens"] = config['default_max_tokens']
        
        # 使用动态获取的基础URL
        base_url = config['base_url']
        
        logger.info(f"准备发送请求到: {base_url}/chat/completions")
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
            
            timeout = aiohttp.ClientTimeout(total=120, connect=60)
            
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
                            f"{base_url}/chat/completions",
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
                return await self._curl_fallback(payload, headers, base_url)
            except Exception as curl_error:
                logger.error(f"Curl备选方案也失败: {curl_error}")
                raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.error(f"LLM服务异常: {type(e).__name__}: {str(e)}")
            raise Exception(f"LLM服务异常: {str(e)}")
    
    async def _curl_fallback(self, payload: Dict, headers: Dict, base_url: str) -> Dict[str, Any]:
        """使用curl作为备选方案"""
        try:
            # 构建curl命令
            curl_cmd = [
                'curl', '-s', '-X', 'POST',
                f"{base_url}/chat/completions",
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
                                              capture_output=True, text=True, timeout=120)
            
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
            system_prompt=system_prompt
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
            system_prompt=system_prompt
        )

# 创建全局LLM服务实例
llm_service = LLMService()