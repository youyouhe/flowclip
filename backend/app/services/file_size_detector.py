"""
文件大小检测和ASR策略选择器
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ASRStrategy(Enum):
    """ASR处理策略枚举"""
    STANDARD = "standard"  # 标准ASR接口 (< 10MB)
    TUS = "tus"           # TUS协议接口 (>= 10MB)

class FileSizeDetector:
    """文件大小检测器和ASR策略选择器"""

    def __init__(self, threshold_mb: int = None):
        """
        初始化文件大小检测器

        Args:
            threshold_mb: 文件大小阈值(MB)，默认从配置读取
        """
        from app.core.config import settings

        self._fixed_threshold_mb = threshold_mb  # 保存固定的阈值（如果提供）
        self._settings = settings  # 保存settings引用以支持动态读取

        # 如果没有提供固定的阈值，则使用配置中的值
        if threshold_mb is None:
            threshold_mb = self._get_current_threshold()
        else:
            # 确保 threshold_mb 是整数类型
            try:
                threshold_mb = int(threshold_mb)
            except (ValueError, TypeError):
                logger.warning(f"无效的阈值配置：{threshold_mb}，使用默认值10")
                threshold_mb = 10

        self.threshold_bytes = threshold_mb * 1024 * 1024
        self.threshold_mb = threshold_mb

    def _get_current_threshold(self) -> int:
        """获取当前的阈值配置"""
        from app.core.config import settings
        # 优先使用固定阈值，否则从配置读取
        if self._fixed_threshold_mb is not None:
            return self._fixed_threshold_mb

        # 从配置读取阈值
        threshold_mb = getattr(settings, 'tus_file_size_threshold_mb', 10)

        # 确保 threshold_mb 是整数类型
        try:
            threshold_mb = int(threshold_mb)
        except (ValueError, TypeError):
            logger.warning(f"无效的阈值配置：{threshold_mb}，使用默认值10")
            threshold_mb = 10

        return threshold_mb

    def detect_file_size(self, file_path: str) -> Dict[str, Any]:
        """
        检测文件大小并返回详细信息

        Args:
            file_path: 文件路径

        Returns:
            Dict: 包含文件大小信息和策略选择的字典
        """
        try:
            path = Path(file_path)

            # 验证文件存在性
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            if not path.is_file():
                raise ValueError(f"路径不是文件: {file_path}")

            # 获取文件大小
            file_size = path.stat().st_size

            # 动态获取当前阈值（支持运行时配置更新）
            current_threshold_mb = self._get_current_threshold()
            current_threshold_bytes = current_threshold_mb * 1024 * 1024

            # 判断策略
            use_tus = file_size >= current_threshold_bytes
            strategy = ASRStrategy.TUS if use_tus else ASRStrategy.STANDARD

            result = {
                'file_path': file_path,
                'file_size': file_size,
                'file_size_mb': file_size / (1024 * 1024),
                'threshold_bytes': current_threshold_bytes,
                'threshold_mb': current_threshold_mb,
                'use_tus': use_tus,
                'strategy': strategy.value,
                'size_category': self._get_size_category(file_size, current_threshold_mb),
                'recommended_action': self._get_recommended_action(strategy)
            }

            logger.info(f"文件大小检测结果: {result['file_size_mb']:.2f}MB, "
                       f"策略: {strategy.value}, "
                       f"阈值: {current_threshold_mb}MB")

            return result

        except Exception as e:
            logger.error(f"文件大小检测失败: {e}", exc_info=True)
            # 提供详细的错误信息
            error_info = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'file_path': file_path,
                'timestamp': time.time()
            }
            logger.error(f"文件大小检测失败详情: {json.dumps(error_info, indent=2)}")
            # 即使检测失败，也返回默认策略（标准ASR）以确保系统继续工作
            return {
                'file_path': file_path,
                'file_size': 0,
                'file_size_mb': 0,
                'threshold_bytes': self.threshold_bytes,
                'threshold_mb': self.threshold_mb,
                'use_tus': False,
                'strategy': ASRStrategy.STANDARD.value,
                'size_category': 'unknown',
                'recommended_action': '使用标准ASR接口处理',
                'error': str(e)
            }

    def should_use_tus(self, file_path: str) -> bool:
        """
        判断是否应该使用TUS协议

        Args:
            file_path: 文件路径

        Returns:
            bool: True表示使用TUS，False表示使用标准ASR
        """
        result = self.detect_file_size(file_path)
        return result['use_tus']

    def get_asr_strategy(self, file_path: str) -> ASRStrategy:
        """
        获取ASR处理策略

        Args:
            file_path: 文件路径

        Returns:
            ASRStrategy: ASR处理策略
        """
        result = self.detect_file_size(file_path)
        return ASRStrategy(result['strategy'])

    def _get_size_category(self, file_size: int, threshold_mb: int = None) -> str:
        """获取文件大小分类"""
        # 如果没有提供阈值，则使用实例的阈值
        if threshold_mb is None:
            threshold_mb = self.threshold_mb

        mb = file_size / (1024 * 1024)

        if mb < 1:
            return "small"
        elif mb < threshold_mb:
            return "medium"
        elif mb < 50:
            return "large"
        else:
            return "very_large"

    def _get_recommended_action(self, strategy: ASRStrategy) -> str:
        """获取推荐操作"""
        if strategy == ASRStrategy.STANDARD:
            return "使用标准ASR接口处理"
        else:
            return "使用TUS协议进行大文件上传和处理"


class ASRStrategySelector:
    """ASR策略选择器，集成到现有音频处理流程"""

    def __init__(self, threshold_mb: int = None):
        """
        初始化ASR策略选择器

        Args:
            threshold_mb: 文件大小阈值(MB)，默认从配置读取
        """
        self.detector = FileSizeDetector(threshold_mb)
        self._fixed_threshold_mb = threshold_mb  # 保存固定的阈值（如果提供）

    def update_threshold(self, threshold_mb: int = None):
        """
        更新文件大小阈值配置

        Args:
            threshold_mb: 新的文件大小阈值(MB)，如果为None则从配置中重新读取
        """
        # 重新创建detector实例以应用新的阈值
        self.detector = FileSizeDetector(threshold_mb)
        self._fixed_threshold_mb = threshold_mb

    async def select_and_execute_asr(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        根据文件大小选择ASR策略并执行

        Args:
            file_path: 音频文件路径
            metadata: ASR元数据

        Returns:
            Dict: ASR处理结果
        """
        try:
            # 检测文件大小
            size_info = self.detector.detect_file_size(file_path)
            strategy = size_info['strategy']

            logger.info(f"选择ASR策略: {strategy}")

            if strategy == ASRStrategy.STANDARD.value:
                return await self._execute_standard_asr(file_path, metadata)
            else:
                return await self._execute_tus_asr(file_path, metadata)

        except Exception as e:
            logger.error(f"ASR策略选择和执行失败: {e}", exc_info=True)
            # 提供详细的错误信息
            error_info = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'file_path': file_path,
                'metadata': metadata,
                'timestamp': time.time()
            }
            logger.error(f"ASR策略选择和执行失败详情: {json.dumps(error_info, indent=2)}")
            raise RuntimeError(f"ASR策略选择和执行失败: {str(e)}") from e

    async def _execute_standard_asr(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行标准ASR处理"""
        try:
            logger.info(f"执行标准ASR处理: {file_path}")

            # 导入现有的ASR服务
            from app.services.audio_processor import AudioProcessor
            audio_processor = AudioProcessor()

            # 使用现有的generate_srt_from_audio方法
            # 注意：这里需要正确的参数
            result = await audio_processor.generate_srt_from_audio(
                audio_path=file_path,
                video_id=metadata.get('video_id', 'unknown'),
                project_id=metadata.get('project_id', 1),
                user_id=metadata.get('user_id', 1),
                lang=metadata.get('language', 'auto'),
                asr_model_type=metadata.get('model', 'whisper')
            )

            return {
                'strategy': 'standard',
                'status': 'completed',
                'srt_content': result.get('srt_content', ''),
                'file_path': file_path,
                'metadata': metadata,
                'processing_info': result
            }

        except Exception as e:
            logger.error(f"标准ASR处理失败: {e}")
            raise

    async def _execute_tus_asr(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行TUS ASR处理"""
        try:
            logger.info(f"执行TUS ASR处理: {file_path}")

            # 导入TUS客户端
            from app.services.tus_asr_client import tus_asr_client

            # 使用TUS客户端处理音频文件
            result = await tus_asr_client.process_audio_file(
                audio_file_path=file_path,
                metadata=metadata or {}
            )

            # 如果是子切片处理，更新子切片记录
            sub_slice_id = metadata.get('sub_slice_id') if metadata else None
            if sub_slice_id:
                try:
                    from app.core.database import get_sync_db
                    from app.models import VideoSubSlice

                    with get_sync_db() as db:
                        sub_slice_record = db.query(VideoSubSlice).filter(VideoSubSlice.id == sub_slice_id).first()
                        if sub_slice_record:
                            # 更新子切片的srt_url和其他相关信息
                            srt_url = result.get('minio_path', result.get('srt_url'))
                            if srt_url:
                                sub_slice_record.srt_url = srt_url
                                sub_slice_record.srt_processing_status = "completed"
                                db.commit()
                                logger.info(f"已更新子切片记录: sub_slice_id={sub_slice_id}, srt_url={srt_url}")
                        else:
                            logger.warning(f"未找到子切片记录: sub_slice_id={sub_slice_id}")
                except Exception as update_error:
                    logger.error(f"更新子切片记录失败: {update_error}")

            return {
                'strategy': 'tus',
                'status': 'completed' if result.get('success') else 'failed',
                'srt_content': result.get('srt_content', ''),
                'task_id': result.get('task_id'),
                'file_path': file_path,
                'metadata': metadata,
                'processing_info': result
            }

        except Exception as e:
            logger.error(f"TUS ASR处理失败: {e}")
            raise


# 全局实例，供其他模块使用
file_size_detector = FileSizeDetector()
asr_strategy_selector = ASRStrategySelector()


def update_global_threshold(threshold_mb: int = None):
    """
    更新全局实例的文件大小阈值配置

    Args:
        threshold_mb: 新的文件大小阈值(MB)，如果为None则从配置中重新读取
    """
    global file_size_detector, asr_strategy_selector
    file_size_detector = FileSizeDetector(threshold_mb)
    asr_strategy_selector.update_threshold(threshold_mb)