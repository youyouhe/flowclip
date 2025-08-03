import pytest
import asyncio
import os
from typing import Generator
from pathlib import Path

# 设置测试环境变量
os.environ.setdefault('TESTING', 'true')
os.environ.setdefault('MINIO_ENDPOINT', 'localhost:9000')
os.environ.setdefault('MINIO_ACCESS_KEY', 'minioadmin')
os.environ.setdefault('MINIO_SECRET_KEY', 'minioadmin')
os.environ.setdefault('MINIO_BUCKET_NAME', 'test-youtube-videos')
os.environ.setdefault('MINIO_SECURE', 'false')

# 确保测试事件循环
@pytest.fixture(scope="session")
def event_loop():
    """创建测试用的事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_data_dir():
    """创建测试数据目录"""
    test_dir = Path(__file__).parent / "test_data"
    test_dir.mkdir(exist_ok=True)
    yield test_dir
    
    # 清理测试数据
    for file in test_dir.iterdir():
        if file.is_file():
            file.unlink()

@pytest.fixture
def sample_video_content():
    """创建示例视频内容"""
    return b"fake video content for testing"

@pytest.fixture
def sample_audio_content():
    """创建示例音频内容"""
    return b"fake audio content for testing"

@pytest.fixture
def sample_image_content():
    """创建示例图片内容"""
    return b"fake image content"

# 标记集成测试
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("event_loop")
]

def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )

def pytest_collection_modifyitems(config, items):
    """修改测试收集项"""
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.skipif(
                not os.getenv('INTEGRATION_TESTS'),
                reason="需要设置 INTEGRATION_TESTS=1 来运行集成测试"
            ))