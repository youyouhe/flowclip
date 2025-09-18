#!/usr/bin/env python3
"""
TUS集成测试用例
验证文件大小检测、TUS客户端和标准ASR接口的正确性
"""

import os
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TusIntegrationTester:
    """TUS集成测试器"""

    def __init__(self):
        self.test_results = []
        self.temp_files = []

    async def setup_test_environment(self):
        """设置测试环境"""
        logger.info("设置测试环境...")

        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        logger.info(f"临时目录: {self.temp_dir}")

    async def cleanup_test_environment(self):
        """清理测试环境"""
        logger.info("清理测试环境...")

        # 清理临时文件
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"已删除临时文件: {temp_file}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {e}")

        # 清理临时目录
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"已删除临时目录: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"删除临时目录失败: {e}")

    def create_test_audio_files(self):
        """创建测试音频文件"""
        logger.info("创建测试音频文件...")

        # 创建小于10MB的测试文件 (5MB)
        small_file_path = self.temp_path / "small_audio.wav"
        self._create_wav_file(small_file_path, 5 * 1024 * 1024)  # 5MB

        # 创建大于10MB的测试文件 (15MB)
        large_file_path = self.temp_path / "large_audio.wav"
        self._create_wav_file(large_file_path, 15 * 1024 * 1024)  # 15MB

        # 创建边界测试文件 (正好10MB)
        boundary_file_path = self.temp_path / "boundary_audio.wav"
        self._create_wav_file(boundary_file_path, 10 * 1024 * 1024)  # 10MB

        self.temp_files.extend([
            str(small_file_path),
            str(large_file_path),
            str(boundary_file_path)
        ])

        return {
            'small_file': str(small_file_path),
            'large_file': str(large_file_path),
            'boundary_file': str(boundary_file_path)
        }

    def _create_wav_file(self, file_path: Path, size_bytes: int):
        """创建指定大小的WAV文件"""
        # 创建简单的WAV文件头
        import struct

        # WAV文件头 (44 bytes)
        # RIFF header
        riff_header = b'RIFF'
        file_size_minus_8 = size_bytes - 8
        riff_header += struct.pack('<I', file_size_minus_8)
        riff_header += b'WAVE'

        # fmt chunk
        fmt_header = b'fmt '
        fmt_header += struct.pack('<I', 16)  # fmt chunk size
        fmt_header += struct.pack('<H', 1)   # PCM format
        fmt_header += struct.pack('<H', 1)   # mono
        fmt_header += struct.pack('<I', 16000)  # sample rate
        fmt_header += struct.pack('<I', 32000)  # byte rate
        fmt_header += struct.pack('<H', 2)   # block align
        fmt_header += struct.pack('<H', 16)  # bits per sample

        # data chunk
        data_header = b'data'
        data_size = size_bytes - 44  # 减去头部大小
        data_header += struct.pack('<I', data_size)

        # 生成音频数据 (静音)
        audio_data = b'\x00' * data_size

        # 写入文件
        with open(file_path, 'wb') as f:
            f.write(riff_header)
            f.write(fmt_header)
            f.write(data_header)
            f.write(audio_data)

        logger.info(f"创建测试文件: {file_path} ({size_bytes} bytes)")

    async def test_file_size_detection(self, test_files: Dict[str, str]):
        """测试文件大小检测功能"""
        logger.info("=== 测试文件大小检测功能 ===")

        from app.services.file_size_detector import file_size_detector

        test_cases = [
            ('small_file', '应该使用标准ASR', False),
            ('large_file', '应该使用TUS', True),
            ('boundary_file', '边界情况 (10MB)', True)  # 10MB及以上使用TUS
        ]

        for file_name, expected_desc, expected_use_tus in test_cases:
            file_path = test_files[file_name]

            try:
                result = file_size_detector.detect_file_size(file_path)

                logger.info(f"测试 {file_name}:")
                logger.info(f"  文件大小: {result['file_size_mb']:.2f}MB")
                logger.info(f"  阈值: {result['threshold_mb']}MB")
                logger.info(f"  使用TUS: {result['use_tus']}")
                logger.info(f"  策略: {result['strategy']}")

                # 验证结果
                success = result['use_tus'] == expected_use_tus
                test_result = {
                    'test_name': f'file_size_detection_{file_name}',
                    'description': expected_desc,
                    'success': success,
                    'details': result,
                    'expected_use_tus': expected_use_tus,
                    'actual_use_tus': result['use_tus']
                }

                if success:
                    logger.info(f"  ✅ 测试通过: {expected_desc}")
                else:
                    logger.error(f"  ❌ 测试失败: 期望 {expected_use_tus}, 实际 {result['use_tus']}")

                self.test_results.append(test_result)

            except Exception as e:
                logger.error(f"  ❌ 测试异常: {e}")
                self.test_results.append({
                    'test_name': f'file_size_detection_{file_name}',
                    'description': expected_desc,
                    'success': False,
                    'error': str(e)
                })

    async def test_strategy_selector(self, test_files: Dict[str, str]):
        """测试策略选择器"""
        logger.info("=== 测试策略选择器 ===")

        from app.services.file_size_detector import asr_strategy_selector

        test_cases = [
            ('small_file', '标准ASR策略', 'standard'),
            ('large_file', 'TUS策略', 'tus'),
            ('boundary_file', 'TUS策略', 'tus')
        ]

        for file_name, expected_desc, expected_strategy in test_cases:
            file_path = test_files[file_name]

            try:
                # 这里只测试策略选择，不执行实际ASR处理
                # 使用should_use_tus方法
                use_tus = asr_strategy_selector.detector.should_use_tus(file_path)
                strategy = asr_strategy_selector.detector.get_asr_strategy(file_path)

                logger.info(f"测试 {file_name}:")
                logger.info(f"  使用TUS: {use_tus}")
                logger.info(f"  策略: {strategy.value}")

                # 验证结果
                success = strategy.value == expected_strategy
                test_result = {
                    'test_name': f'strategy_selector_{file_name}',
                    'description': expected_desc,
                    'success': success,
                    'details': {
                        'use_tus': use_tus,
                        'strategy': strategy.value
                    },
                    'expected_strategy': expected_strategy,
                    'actual_strategy': strategy.value
                }

                if success:
                    logger.info(f"  ✅ 测试通过: {expected_desc}")
                else:
                    logger.error(f"  ❌ 测试失败: 期望 {expected_strategy}, 实际 {strategy.value}")

                self.test_results.append(test_result)

            except Exception as e:
                logger.error(f"  ❌ 测试异常: {e}")
                self.test_results.append({
                    'test_name': f'strategy_selector_{file_name}',
                    'description': expected_desc,
                    'success': False,
                    'error': str(e)
                })

    async def test_configuration_loading(self):
        """测试配置加载"""
        logger.info("=== 测试配置加载 ===")

        try:
            from app.core.config import settings

            # 测试TUS相关配置
            config_tests = [
                ('tus_api_url', settings.tus_api_url),
                ('tus_upload_url', settings.tus_upload_url),
                ('tus_callback_port', settings.tus_callback_port),
                ('tus_callback_host', settings.tus_callback_host),
                ('tus_file_size_threshold_mb', settings.tus_file_size_threshold_mb),
                ('tus_enable_routing', settings.tus_enable_routing),
                ('tus_max_retries', settings.tus_max_retries),
                ('tus_timeout_seconds', settings.tus_timeout_seconds),
            ]

            for config_name, config_value in config_tests:
                logger.info(f"配置 {config_name}: {config_value}")

                test_result = {
                    'test_name': f'config_{config_name}',
                    'description': f'配置项 {config_name} 可用',
                    'success': config_value is not None,
                    'details': {
                        'config_name': config_name,
                        'config_value': config_value
                    }
                }

                if config_value is not None:
                    logger.info(f"  ✅ 配置 {config_name} 加载成功")
                else:
                    logger.error(f"  ❌ 配置 {config_name} 加载失败")

                self.test_results.append(test_result)

        except Exception as e:
            logger.error(f"配置测试异常: {e}")
            self.test_results.append({
                'test_name': 'configuration_loading',
                'description': '配置加载测试',
                'success': False,
                'error': str(e)
            })

    async def test_error_handling(self, test_files: Dict[str, str]):
        """测试错误处理"""
        logger.info("=== 测试错误处理 ===")

        from app.services.file_size_detector import file_size_detector

        error_tests = [
            {
                'name': 'non_existent_file',
                'file_path': '/path/to/nonexistent/file.wav',
                'expected_error': 'FileNotFoundError'
            },
            {
                'name': 'directory_path',
                'file_path': '/tmp',  # 目录而不是文件
                'expected_error': 'ValueError'
            }
        ]

        for test in error_tests:
            try:
                # 应该抛出异常
                result = file_size_detector.detect_file_size(test['file_path'])

                # 如果没有抛出异常，测试失败
                logger.error(f"  ❌ 测试失败: 期望抛出 {test['expected_error']}, 但没有异常")
                self.test_results.append({
                    'test_name': f'error_handling_{test["name"]}',
                    'description': f'应该抛出 {test["expected_error"]}',
                    'success': False,
                    'details': result
                })

            except Exception as e:
                error_type = type(e).__name__
                if error_type == test['expected_error'] or test['expected_error'] in str(type(e)):
                    logger.info(f"  ✅ 测试通过: 正确抛出 {error_type}")
                    self.test_results.append({
                        'test_name': f'error_handling_{test["name"]}',
                        'description': f'正确抛出 {test["expected_error"]}',
                        'success': True,
                        'error_type': error_type
                    })
                else:
                    logger.error(f"  ❌ 测试失败: 期望 {test['expected_error']}, 实际 {error_type}")
                    self.test_results.append({
                        'test_name': f'error_handling_{test["name"]}',
                        'description': f'期望抛出 {test["expected_error"]}',
                        'success': False,
                        'expected_error': test['expected_error'],
                        'actual_error': error_type
                    })

    def generate_test_report(self):
        """生成测试报告"""
        logger.info("=== 生成测试报告 ===")

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests

        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {failed_tests}")
        logger.info(f"成功率: {passed_tests/total_tests*100:.1f}%")

        # 生成详细报告
        report = {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': f"{passed_tests/total_tests*100:.1f}%"
            },
            'test_results': self.test_results,
            'generated_at': str(asyncio.get_event_loop().time())
        }

        # 保存报告到文件
        report_path = self.temp_path / "test_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"测试报告已保存到: {report_path}")

        # 打印失败的测试
        failed_results = [r for r in self.test_results if not r['success']]
        if failed_results:
            logger.error("失败的测试:")
            for result in failed_results:
                logger.error(f"  - {result['test_name']}: {result.get('error', 'Unknown error')}")

        return report

    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始TUS集成测试...")

        try:
            # 设置测试环境
            await self.setup_test_environment()

            # 创建测试文件
            test_files = self.create_test_audio_files()

            # 运行测试
            await self.test_configuration_loading()
            await self.test_file_size_detection(test_files)
            await self.test_strategy_selector(test_files)
            await self.test_error_handling(test_files)

            # 生成报告
            report = self.generate_test_report()

            logger.info("TUS集成测试完成!")
            return report

        except Exception as e:
            logger.error(f"测试运行失败: {e}", exc_info=True)
            raise
        finally:
            # 清理测试环境
            await self.cleanup_test_environment()


async def main():
    """主函数"""
    tester = TusIntegrationTester()
    report = await tester.run_all_tests()

    # 根据测试结果返回相应的退出码
    success_rate = float(report['summary']['success_rate'].rstrip('%'))
    if success_rate >= 100:
        return 0  # 全部通过
    elif success_rate >= 80:
        return 1  # 基本通过
    else:
        return 2  # 多数失败


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)