#!/usr/bin/env python3
"""
测试增强的进度跟踪功能
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.youtube_downloader_minio import downloader_minio
from app.services.progress_service import progress_service

class ProgressTest:
    """进度测试类"""
    
    def __init__(self):
        self.test_user_id = 999
        self.test_project_id = 999
        self.test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley
        self.progress_updates = []
    
    async def test_progress_parsing(self):
        """测试进度解析功能"""
        print("🧪 测试进度解析功能")
        
        # 测试用例
        test_lines = [
            "[youtube] dQw4w9WgXcQ: Downloading webpage",
            "[info] Downloading 1 format(s): 96",
            "[hlsnative] Downloading m3u8 manifest",
            "[hlsnative] Total fragments: 893",
            "[download] Destination: Rick Astley - Never Gonna Give You Up (Official Video) [dQw4w9WgXcQ].mp4",
            "[download]   2.8% of ~959.74MiB at    2.67MiB/s ETA 05:44 (frag 24/893)",
            "[download]  50.0% of ~959.74MiB at    3.21MiB/s ETA 02:30 (frag 446/893)",
            "[download] 100% of 959.74MiB in 03:21",
            "[ffmpeg] Merging formats into "Rick Astley - Never Gonna Give You Up (Official Video) [dQw4w9WgXcQ].mp4"",
            "[ffmpeg] Destination: Rick Astley - Never Gonna Give You Up (Official Video) [dQw4w9WgXcQ].mp4"
        ]
        
        for line in test_lines:
            result = downloader_minio._parse_download_progress(line)
            if result:
                print(f"✅ 解析成功: {line[:60]}...")
                print(f"   进度: {result['percentage']:.1f}%")
                print(f"   消息: {result['message']}")
                print(f"   阶段: {result.get('stage', 'unknown')}")
                print()
            else:
                print(f"⚠️  未解析: {line[:60]}...")
        
        print("✅ 进度解析测试完成")
    
    async def test_real_download(self):
        """测试真实下载进度"""
        print("🚀 开始真实下载进度测试")
        
        # 启动进度服务
        await progress_service.start()
        
        try:
            # 定义进度回调
            async def progress_callback(progress, message):
                self.progress_updates.append({
                    'progress': progress,
                    'message': message,
                    'timestamp': asyncio.get_event_loop().time()
                })
                print(f"📊 实时进度: {progress:.1f}% - {message}")
            
            # 获取视频信息
            print("📋 获取视频信息...")
            video_info = await downloader_minio.get_video_info(self.test_video_url)
            print(f"   标题: {video_info['title']}")
            print(f"   时长: {video_info['duration']}秒")
            
            # 开始下载（使用低质量以加快测试）
            print("\n📥 开始下载...")
            result = await downloader_minio.download_and_upload_video(
                url=self.test_video_url,
                project_id=self.test_project_id,
                user_id=self.test_user_id,
                quality='worst',  # 使用最低质量加快测试
                progress_callback=progress_callback
            )
            
            if result.get('success'):
                print(f"\n✅ 下载完成!")
                print(f"   文件名: {result['filename']}")
                print(f"   文件大小: {result['file_size']:,} bytes")
                print(f"   MinIO路径: {result['minio_path']}")
                print(f"   收到进度更新: {len(self.progress_updates)}次")
                
                # 显示进度更新摘要
                if self.progress_updates:
                    print("\n📈 进度更新摘要:")
                    for i, update in enumerate(self.progress_updates[:5]):  # 显示前5个
                        print(f"   {i+1}. {update['progress']:.1f}% - {update['message']}")
                    
                    if len(self.progress_updates) > 5:
                        print(f"   ... 共{len(self.progress_updates)}次更新")
                        
            else:
                print(f"❌ 下载失败: {result.get('error', '未知错误')}")
                
        finally:
            # 停止进度服务
            await progress_service.stop()
    
    async def run_tests(self):
        """运行所有测试"""
        print("🎯 开始进度跟踪测试")
        print("=" * 50)
        
        # 测试1: 进度解析
        await self.test_progress_parsing()
        
        print("\n" + "=" * 50)
        
        # 测试2: 真实下载（可选，需要实际网络连接）
        choice = input("\n是否运行真实下载测试？(y/n): ").lower().strip()
        if choice == 'y':
            await self.test_real_download()
        else:
            print("跳过真实下载测试")
        
        print("\n🎉 测试完成!")

async def main():
    """主函数"""
    tester = ProgressTest()
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())