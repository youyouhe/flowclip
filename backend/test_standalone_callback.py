#!/usr/bin/env python3
"""
独立回调服务器测试脚本
用于验证独立回调服务器的功能
"""

import asyncio
import json
import time
import logging
import aiohttp
from app.services.standalone_callback_client import standalone_callback_client

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_callback_server():
    """测试独立回调服务器"""
    logger.info("🧪 开始测试独立回调服务器")

    # 1. 测试健康检查
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('http://localhost:9090/health') as response:
                if response.status == 200:
                    health_data = await response.json()
                    logger.info(f"✅ 健康检查通过: {health_data}")
                else:
                    logger.error(f"❌ 健康检查失败: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ 健康检查异常: {e}")
            return False

    # 2. 测试统计信息
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('http://localhost:9090/stats') as response:
                if response.status == 200:
                    stats = await response.json()
                    logger.info(f"📊 当前统计: {stats}")
                else:
                    logger.error(f"❌ 获取统计失败: {response.status}")
        except Exception as e:
            logger.error(f"❌ 获取统计异常: {e}")

    # 3. 测试任务注册和等待
    test_task_id = f"test_task_{int(time.time())}"
    logger.info(f"📝 测试任务ID: {test_task_id}")

    # 注册任务
    if standalone_callback_client.register_task(test_task_id):
        logger.info("✅ 任务注册成功")

        # 模拟回调请求
        callback_payload = {
            "task_id": test_task_id,
            "status": "completed",
            "srt_url": f"/api/v1/tasks/{test_task_id}/download",
            "filename": "test.wav"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    'http://localhost:9090/callback',
                    json=callback_payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        logger.info("✅ 回调请求发送成功")
                        result = await response.text()
                        logger.info(f"📄 回调响应: {result}")
                    else:
                        logger.error(f"❌ 回调请求失败: {response.status}")
                        return False
            except Exception as e:
                logger.error(f"❌ 回调请求异常: {e}")
                return False

        # 等待结果
        logger.info("⏳ 等待任务结果...")
        result_data = await standalone_callback_client.wait_for_result(test_task_id, timeout=30)

        if result_data:
            logger.info(f"✅ 任务结果获取成功: {result_data}")
        else:
            logger.error("❌ 任务结果获取失败")
            return False

        # 清理任务
        standalone_callback_client.cleanup_task(test_task_id)
        logger.info("🧹 任务清理完成")

        return True
    else:
        logger.error("❌ 任务注册失败")
        return False

async def test_multiple_tasks():
    """测试并发任务处理"""
    logger.info("🔄 开始并发任务测试")

    async def process_task(task_id: int):
        """处理单个任务"""
        test_task_id = f"concurrent_task_{task_id}_{int(time.time())}"

        # 注册任务
        if not standalone_callback_client.register_task(test_task_id):
            logger.error(f"❌ 任务 {test_task_id} 注册失败")
            return False

        # 模拟回调
        callback_payload = {
            "task_id": test_task_id,
            "status": "completed",
            "srt_url": f"/api/v1/tasks/{test_task_id}/download",
            "filename": f"test_{task_id}.wav"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    'http://localhost:9090/callback',
                    json=callback_payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status != 200:
                        logger.error(f"❌ 任务 {test_task_id} 回调失败: {response.status}")
                        return False
            except Exception as e:
                logger.error(f"❌ 任务 {test_task_id} 回调异常: {e}")
                return False

        # 等待结果
        result_data = await standalone_callback_client.wait_for_result(test_task_id, timeout=30)

        if result_data:
            logger.info(f"✅ 任务 {task_id} 处理成功")
            # 清理任务
            standalone_callback_client.cleanup_task(test_task_id)
            return True
        else:
            logger.error(f"❌ 任务 {task_id} 结果获取失败")
            return False

    # 并发处理5个任务
    tasks = [process_task(i) for i in range(5)]
    results = await asyncio.gather(*tasks)

    success_count = sum(results)
    logger.info(f"📊 并发测试结果: {success_count}/5 成功")

    return success_count == 5

async def main():
    """主测试函数"""
    logger.info("🚀 开始独立回调服务器测试")

    # 等待服务器启动
    logger.info("⏳ 等待服务器启动...")
    await asyncio.sleep(5)

    test_results = []

    # 测试1: 基本功能
    logger.info("\n" + "="*50)
    logger.info("测试1: 基本功能")
    logger.info("="*50)
    result1 = await test_callback_server()
    test_results.append(("基本功能", result1))

    # 测试2: 并发处理
    logger.info("\n" + "="*50)
    logger.info("测试2: 并发处理")
    logger.info("="*50)
    result2 = await test_multiple_tasks()
    test_results.append(("并发处理", result2))

    # 输出测试结果
    logger.info("\n" + "="*50)
    logger.info("测试结果汇总")
    logger.info("="*50)

    all_passed = True
    for test_name, passed in test_results:
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False

    logger.info("\n" + "="*50)
    if all_passed:
        logger.info("🎉 所有测试通过！独立回调服务器运行正常。")
    else:
        logger.error("💥 部分测试失败，请检查配置和日志。")
    logger.info("="*50)

    return all_passed

if __name__ == "__main__":
    asyncio.run(main())