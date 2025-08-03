#!/usr/bin/env python3
"""
MinIO集成端到端测试脚本
验证从YouTube下载到MinIO存储的完整流程
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.minio_client import minio_service
from app.services.youtube_downloader_minio import downloader_minio
from app.core.config import settings


class MinioIntegrationTest:
    """MinIO集成测试类"""
    
    def __init__(self):
        self.test_user_id = 1
        self.test_project_id = 1
        self.test_results = []
    
    async def run_all_tests(self):
        """运行所有集成测试"""
        print("🚀 开始MinIO集成测试...")
        
        try:
            # 测试1: 连接测试
            await self.test_minio_connection()
            
            # 测试2: 桶操作
            await self.test_bucket_operations()
            
            # 测试3: 文件上传/下载
            await self.test_file_operations()
            
            # 测试4: YouTube下载集成
            await self.test_youtube_integration()
            
            # 测试5: 清理测试
            await self.test_cleanup()
            
            self.print_summary()
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return False
        
        return True
    
    async def test_minio_connection(self):
        """测试MinIO连接"""
        print("\n📡 测试MinIO连接...")
        
        try:
            # 测试客户端连接
            client = minio_service.client
            buckets = client.list_buckets()
            print(f"✅ MinIO连接成功，发现 {len(buckets)} 个桶")
            self.test_results.append(("MinIO连接", True, "成功"))
            
        except Exception as e:
            print(f"❌ MinIO连接失败: {e}")
            self.test_results.append(("MinIO连接", False, str(e)))
            raise
    
    async def test_bucket_operations(self):
        """测试桶操作"""
        print("\n🗂️  测试桶操作...")
        
        try:
            # 确保测试桶存在
            result = await minio_service.ensure_bucket_exists()
            if result:
                print(f"✅ 桶 '{settings.minio_bucket_name}' 已就绪")
                self.test_results.append(("桶操作", True, "桶已就绪"))
            else:
                raise Exception("无法创建或访问桶")
                
        except Exception as e:
            print(f"❌ 桶操作失败: {e}")
            self.test_results.append(("桶操作", False, str(e)))
            raise
    
    async def test_file_operations(self):
        """测试文件操作"""
        print("\n📁 测试文件操作...")
        
        test_filename = "test_integration.txt"
        test_content = b"Hello from MinIO integration test!"
        test_object = f"users/{self.test_user_id}/projects/{self.test_project_id}/test/{test_filename}"
        
        try:
            # 上传测试文件
            upload_result = await minio_service.upload_file_content(
                test_content, test_object, "text/plain"
            )
            
            if not upload_result:
                raise Exception("文件上传失败")
            
            print(f"✅ 文件上传成功: {upload_result}")
            
            # 检查文件存在
            exists = await minio_service.file_exists(test_object)
            if not exists:
                raise Exception("文件存在检查失败")
            
            print("✅ 文件存在检查通过")
            
            # 获取下载URL
            download_url = await minio_service.get_file_url(test_object, 60)
            if not download_url:
                raise Exception("获取下载URL失败")
            
            print(f"✅ 获取下载URL成功: {download_url[:50]}...")
            
            # 清理测试文件
            deleted = await minio_service.delete_file(test_object)
            if not deleted:
                raise Exception("文件删除失败")
            
            print("✅ 文件删除成功")
            self.test_results.append(("文件操作", True, "所有操作正常"))
            
        except Exception as e:
            print(f"❌ 文件操作失败: {e}")
            self.test_results.append(("文件操作", False, str(e)))
            raise
    
    async def test_youtube_integration(self):
        """测试YouTube下载集成"""
        print("\n🎥 测试YouTube下载集成...")
        
        # 使用一个公开的测试视频（Rick Astley - Never Gonna Give You Up）
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            print("正在获取视频信息...")
            video_info = await downloader_minio.get_video_info(test_url)
            
            print(f"✅ 视频信息获取成功: {video_info['title']}")
            
            # 注意：为了测试，我们使用worst质量来加快下载
            print("开始下载并上传到MinIO...")
            result = await downloader_minio.download_and_upload_video(
                url=test_url,
                project_id=self.test_project_id,
                user_id=self.test_user_id,
                format_id='worst'  # 使用最低质量以加快测试
            )
            
            if result['success']:
                print(f"✅ YouTube下载并上传成功")
                print(f"   视频ID: {result['video_id']}")
                print(f"   标题: {result['title']}")
                print(f"   MinIO路径: {result['minio_path']}")
                print(f"   文件大小: {result['filesize']} bytes")
                
                # 验证文件确实存在于MinIO
                object_name = result['minio_path'].replace(f"{settings.minio_bucket_name}/", "")
                exists = await minio_service.file_exists(object_name)
                
                if exists:
                    print("✅ 验证文件已存在于MinIO")
                    self.test_results.append(("YouTube集成", True, "下载和上传成功"))
                    
                    # 保存测试文件路径以便后续清理
                    self.cleanup_files = [object_name]
                    if result.get('thumbnail_url'):
                        thumb_obj = result['thumbnail_url'].replace(f"{settings.minio_bucket_name}/", "")
                        self.cleanup_files.append(thumb_obj)
                    
                else:
                    raise Exception("文件未成功上传到MinIO")
            else:
                raise Exception("下载或上传失败")
                
        except Exception as e:
            print(f"❌ YouTube集成测试失败: {e}")
            self.test_results.append(("YouTube集成", False, str(e)))
            # 不抛出异常，继续其他测试
    
    async def test_cleanup(self):
        """清理测试文件"""
        print("\n🧹 清理测试文件...")
        
        try:
            # 清理测试期间创建的文件
            test_patterns = [
                f"users/{self.test_user_id}/projects/{self.test_project_id}/test/",
                f"users/{self.test_user_id}/projects/{self.test_project_id}/videos/",
                f"users/{self.test_user_id}/projects/{self.test_project_id}/thumbnails/",
                f"users/{self.test_user_id}/projects/{self.test_project_id}/audio/"
            ]
            
            cleaned = 0
            for pattern in test_patterns:
                try:
                    # 列出并删除相关对象
                    objects = minio_service.client.list_objects(
                        settings.minio_bucket_name, 
                        prefix=pattern,
                        recursive=True
                    )
                    
                    for obj in objects:
                        minio_service.client.remove_object(
                            settings.minio_bucket_name, 
                            obj.object_name
                        )
                        cleaned += 1
                        
                except Exception as e:
                    print(f"清理 {pattern} 时出错: {e}")
            
            print(f"✅ 清理完成，删除了 {cleaned} 个测试文件")
            self.test_results.append(("清理测试", True, f"清理了 {cleaned} 个文件"))
            
        except Exception as e:
            print(f"⚠️  清理过程中出错: {e}")
            self.test_results.append(("清理测试", False, str(e)))
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*50)
        print("📊 测试结果总结")
        print("="*50)
        
        passed = 0
        total = len(self.test_results)
        
        for test_name, passed_test, message in self.test_results:
            status = "✅ 通过" if passed_test else "❌ 失败"
            print(f"{status} {test_name}: {message}")
            if passed_test:
                passed += 1
        
        print("-"*50)
        print(f"总计: {passed}/{total} 项测试通过")
        
        if passed == total:
            print("🎉 所有测试通过！MinIO集成正常")
        else:
            print("⚠️  部分测试失败，请检查配置和服务状态")


async def main():
    """主函数"""
    print("🎯 MinIO集成测试工具")
    print("="*50)
    print(f"MinIO端点: {settings.minio_endpoint}")
    print(f"MinIO桶名: {settings.minio_bucket_name}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    tester = MinioIntegrationTest()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎊 集成测试完成！")
    else:
        print("\n💥 集成测试遇到问题")
    
    return success


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💀 测试运行失败: {e}")
        sys.exit(1)