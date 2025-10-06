"""
独立回调服务器客户端
用于与独立的回调服务器进行通信
"""

import asyncio
import pickle
import time
import logging
import redis
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class StandaloneCallbackClient:
    """独立回调服务器客户端"""

    def __init__(self):
        self.redis_url = None
        self.redis_key_prefix = "tus_callback:"
        self.result_key_prefix = "tus_result:"
        self.stats_key = "tus_callback_stats"
        self._redis_client = None

        self._init_redis()

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            from app.core.config import settings
            self.redis_url = settings.redis_url

            # 创建Redis客户端
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # 测试连接
            self._redis_client.ping()
            logger.info(f"独立回调客户端Redis连接成功: {self.redis_url}")

        except Exception as e:
            logger.error(f"独立回调客户端Redis连接失败: {e}")
            raise

    def _get_task_key(self, task_id: str) -> str:
        """获取任务在Redis中的键名"""
        return f"{self.redis_key_prefix}{task_id}"

    def _get_result_key(self, task_id: str) -> str:
        """获取结果在Redis中的键名"""
        return f"{self.result_key_prefix}{task_id}"

    def register_task(self, task_id: str, celery_task_id: str = None) -> bool:
        """注册任务到独立回调服务器"""
        try:
            task_data = {
                'task_id': task_id,
                'status': 'pending',
                'created_at': time.time(),
                'client_type': 'standalone_callback_client'
            }

            # 如果提供了Celery任务ID，保存关联关系
            if celery_task_id:
                task_data['celery_task_id'] = celery_task_id
                logger.info(f"🔗 保存TUS任务ID与Celery任务ID关联: {task_id} -> {celery_task_id}")

                # 额外保存一个映射关系，便于快速查找
                mapping_key = f"tus_celery_mapping:{celery_task_id}"
                self._redis_client.setex(
                    mapping_key,
                    3600,  # 1小时过期
                    task_id
                )

            task_key = self._get_task_key(task_id)
            self._redis_client.setex(
                task_key,
                3600,  # 1小时过期
                pickle.dumps(task_data)
            )

            logger.info(f"✅ 任务 {task_id} 已注册到独立回调服务器")
            return True

        except Exception as e:
            logger.error(f"❌ 任务注册失败: {e}")
            return False

    async def wait_for_result(self, task_id: str, timeout: int = 1800) -> Optional[Dict[str, Any]]:
        """等待任务结果"""
        try:
            start_time = time.time()
            result_key = self._get_result_key(task_id)

            logger.info(f"⏳ 开始等待任务 {task_id} 的结果，超时: {timeout}秒")

            while time.time() - start_time < timeout:
                # 检查结果是否已存在
                result_data = self._redis_client.get(result_key)
                if result_data:
                    data = pickle.loads(result_data)
                    logger.info(f"✅ 任务 {task_id} 结果已获取")
                    return data.get('result')

                # 每隔5秒检查一次
                await asyncio.sleep(5)

            # 超时
            logger.warning(f"⏰ 任务 {task_id} 等待超时 ({timeout}秒)")
            return None

        except Exception as e:
            logger.error(f"❌ 等待任务结果失败: {e}")
            return None

    def cleanup_task(self, task_id: str):
        """清理任务相关的资源"""
        try:
            task_key = self._get_task_key(task_id)
            result_key = self._get_result_key(task_id)

            deleted_count = 0
            if self._redis_client.exists(task_key):
                self._redis_client.delete(task_key)
                deleted_count += 1

            if self._redis_client.exists(result_key):
                self._redis_client.delete(result_key)
                deleted_count += 1

            if deleted_count > 0:
                logger.info(f"✅ 任务 {task_id} 资源清理完成，删除了 {deleted_count} 个键")

        except Exception as e:
            logger.error(f"❌ 清理任务资源失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            stats_data = self._redis_client.hgetall(self.stats_key)
            stats = {}
            for key, value in stats_data.items():
                stats[key.decode('utf-8')] = int(value.decode('utf-8'))

            # 获取待处理任务数
            pending_keys = self._redis_client.keys(f"{self.redis_key_prefix}*")
            stats['pending_tasks'] = len(pending_keys)

            # 获取缓存结果数
            result_keys = self._redis_client.keys(f"{self.result_key_prefix}*")
            stats['cached_results'] = len(result_keys)

            return stats
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {'error': str(e)}

# 全局实例
standalone_callback_client = StandaloneCallbackClient()