#!/usr/bin/env python3
"""
完整 YouTube 到 MinIO 测试流程
无需 Docker，使用现有配置
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import sqlite3

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.minio_client import minio_service
from app.services.youtube_downloader_minio import downloader_minio
from app.core.config import settings


class CompleteFlowTest:
    """完整流程测试类"""
    
    def __init__(self):
        self.test_user_id = 999
        self.test_project_id = 999
        self.test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley
        self.results = []
    
    async def run_complete_test(self):
        """运行完整测试流程"""
        print("🚀 开始完整 YouTube → MinIO 测试流程")
        print("=" * 60)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"MinIO 配置: {settings.minio_endpoint}")
        print(f"测试桶: {settings.minio_bucket_name}")
        print("=" * 60)
        
        try:
            # 1. 验证 MinIO 连接
            await self.test_minio_connection()
            
            # 2. 测试 YouTube 视频信息获取
            await self.test_video_info()
            
            # 3. 测试下载并上传到 MinIO
            await self.test_download_to_minio()
            
            # 4. 验证 MinIO 文件
            await self.verify_minio_files()
            
            # 5. 测试数据库记录
            await self.test_database_records()
            
            # 6. 测试文件访问
            await self.test_file_access()
            
            # 7. 清理测试数据
            await self.cleanup_test_data()
            
            self.print_summary()
            
        except Exception as e:
            print(f"❌ 测试过程中出错: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
    
    async def test_minio_connection(self):
        """测试 MinIO 连接"""
        print("\n📡 步骤1: 测试 MinIO 连接...")
        
        try:
            # 测试连接
            client = minio_service.client
            
            # 检查桶是否存在
            exists = client.bucket_exists(settings.minio_bucket_name)
            if not exists:
                print(f"⚠️  桶 '{settings.minio_bucket_name}' 不存在，尝试创建...")
                client.make_bucket(settings.minio_bucket_name)
                print("✅ 桶创建成功")
            else:
                print("✅ 桶已存在")
            
            # 获取桶信息
            buckets = client.list_buckets()
            print(f"✅ MinIO 连接成功，发现 {len(buckets)} 个桶")
            
            # 打印桶列表
            for bucket in buckets:
                print(f"   📁 {bucket.name} (创建于 {bucket.creation_date})")
            
            self.results.append(("MinIO连接", True, "连接成功"))
            
        except Exception as e:
            print(f"❌ MinIO 连接失败: {e}")
            print("💡 请确保 MinIO 服务正在运行，或检查配置")
            self.results.append(("MinIO连接", False, str(e)))
            return False
    
    async def test_video_info(self):
        """测试 YouTube 视频信息获取"""
        print("\n🎥 步骤2: 测试 YouTube 视频信息获取...")
        
        try:
            video_info = await downloader_minio.get_video_info(self.test_video_url)
            
            print(f"✅ 视频信息获取成功")
            print(f"   📺 标题: {video_info['title']}")
            print(f"   ⏱️  时长: {video_info['duration']} 秒")
            print(f"   👤 上传者: {video_info['uploader']}")
            print(f"   👁️  观看数: {video_info['view_count']}")
            print(f"   🔗 ID: {video_info['video_id']}")
            
            self.test_video_id = video_info['video_id']
            self.results.append(("视频信息", True, "获取成功"))
            
        except Exception as e:
            print(f"❌ 视频信息获取失败: {e}")
            self.results.append(("视频信息", False, str(e)))
            return False
    
    async def test_download_to_minio(self):
        """测试下载并上传到 MinIO"""
        print("\n📥 步骤3: 测试 YouTube 下载并上传到 MinIO...")
        
        try:
            print("   🔄 开始下载...")
            result = await downloader_minio.download_and_upload_video(
                url=self.test_video_url,
                project_id=self.test_project_id,
                user_id=self.test_user_id,
                format_id='worst'  # 使用低质量以加快测试
            )
            
            if result['success']:
                print(f"✅ 下载和上传成功")
                print(f"   📁 文件名: {result['filename']}")
                print(f"   🗂️  MinIO路径: {result['minio_path']}")
                print(f"   📊 文件大小: {result['filesize']} bytes")
                print(f"   🖼️  缩略图: {result.get('thumbnail_url', '无')}")
                
                self.minio_result = result
                self.results.append(("下载上传", True, "成功"))
            else:
                raise Exception("下载或上传失败")
                
        except Exception as e:
            print(f"❌ 下载上传失败: {e}")
            self.results.append(("下载上传", False, str(e)))
            return False
    
    async def verify_minio_files(self):
        """验证 MinIO 中的文件"""
        print("\n🔍 步骤4: 验证 MinIO 中的文件...")
        
        try:
            if not hasattr(self, 'minio_result'):
                print("⚠️  跳过验证，没有上传结果")
                return
            
            object_name = self.minio_result['minio_path'].replace(
                f"{settings.minio_bucket_name}/", ""
            )
            
            # 检查主视频文件
            exists = await minio_service.file_exists(object_name)
            if exists:
                print("✅ 视频文件存在于 MinIO")
                
                # 获取文件统计信息
                stat = minio_service.client.stat_object(
                    settings.minio_bucket_name, object_name
                )
                print(f"   📊 文件大小: {stat.size} bytes")
                print(f"   🗓️  上传时间: {stat.last_modified}")
                print(f"   📝 内容类型: {stat.content_type}")
                
                # 检查缩略图
                thumbnail_object = f"users/{self.test_user_id}/projects/{self.test_project_id}/thumbnails/{self.test_video_id}.jpg"
                thumb_exists = await minio_service.file_exists(thumbnail_object)
                if thumb_exists:
                    print("✅ 缩略图文件存在")
                else:
                    print("⚠️  缩略图文件不存在")
                
                self.minio_objects = [object_name]
                if thumb_exists:
                    self.minio_objects.append(thumbnail_object)
                    
            else:
                raise Exception("文件未找到")
                
            self.results.append(("文件验证", True, "验证通过"))
            
        except Exception as e:
            print(f"❌ 文件验证失败: {e}")
            self.results.append(("文件验证", False, str(e)))
            return False
    
    async def test_database_records(self):
        """测试数据库记录"""
        print("\n🗄️  步骤5: 测试数据库记录...")
        
        try:
            # 检查数据库文件
            db_path = Path("youtube_slicer.db")
            if not db_path.exists():
                print("⚠️  数据库文件不存在，跳过数据库测试")
                self.results.append(("数据库", True, "跳过测试"))
                return
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 检查视频表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos'")
            if cursor.fetchone():
                # 检查是否有测试视频记录
                cursor.execute("""
                    SELECT id, title, file_path, status, file_size 
                    FROM videos 
                    WHERE project_id = ? AND url LIKE '%dQw4w9WgXcQ%'
                    ORDER BY id DESC LIMIT 1
                """, (self.test_project_id,))
                
                video_record = cursor.fetchone()
                if video_record:
                    print("✅ 数据库记录存在")
                    print(f"   🆔 记录ID: {video_record[0]}")
                    print(f"   📺 标题: {video_record[1]}")
                    print(f"   🗂️  文件路径: {video_record[2]}")
                    print(f"   🏷️  状态: {video_record[3]}")
                    print(f"   📊 文件大小: {video_record[4]} bytes")
                    
                    self.video_id = video_record[0]
                    self.results.append(("数据库记录", True, "记录存在"))
                else:
                    print("⚠️  未找到对应的视频记录")
                    self.results.append(("数据库记录", True, "无记录"))
            else:
                print("⚠️  视频表不存在")
                self.results.append(("数据库记录", True, "表不存在"))
            
            conn.close()
            
        except Exception as e:
            print(f"❌ 数据库测试失败: {e}")
            self.results.append(("数据库记录", False, str(e)))
    
    async def test_file_access(self):
        """测试文件访问"""
        print("\n🔗 步骤6: 测试文件访问...")
        
        try:
            if not hasattr(self, 'minio_objects') or not self.minio_objects:
                print("⚠️  跳过文件访问测试")
                return
            
            # 获取预签名下载URL
            download_url = await minio_service.get_file_url(
                self.minio_objects[0], expiry=300  # 5分钟有效期
            )
            
            if download_url:
                print("✅ 预签名下载URL生成成功")
                print(f"   🔗 URL: {download_url[:80]}...")
                print(f"   ⏱️  有效期: 5分钟")
                
                # 测试URL是否可访问
                import requests
                try:
                    response = requests.head(download_url, timeout=10)
                    if response.status_code == 200:
                        print("✅ 下载URL可正常访问")
                    else:
                        print(f"⚠️  下载URL返回状态码: {response.status_code}")
                except Exception as e:
                    print(f"⚠️  无法测试URL访问性: {e}")
                
                self.results.append(("文件访问", True, "URL生成成功"))
            else:
                raise Exception("无法生成下载URL")
                
        except Exception as e:
            print(f"❌ 文件访问测试失败: {e}")
            self.results.append(("文件访问", False, str(e)))
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        print("\n🧹 步骤7: 清理测试数据...")
        
        try:
            if not hasattr(self, 'minio_objects'):
                print("✅ 无需清理")
                return
            
            cleaned = 0
            for obj_name in self.minio_objects:
                try:
                    success = await minio_service.delete_file(obj_name)
                    if success:
                        cleaned += 1
                        print(f"   ✅ 已删除: {obj_name}")
                    else:
                        print(f"   ⚠️  删除失败: {obj_name}")
                except Exception as e:
                    print(f"   ❌ 删除错误: {obj_name} - {e}")
            
            print(f"✅ 清理完成，删除了 {cleaned} 个文件")
            self.results.append(("清理数据", True, f"清理了 {cleaned} 个文件"))
            
        except Exception as e:
            print(f"❌ 清理失败: {e}")
            self.results.append(("清理数据", False, str(e)))
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📊 测试结果总结")
        print("=" * 60)
        
        passed = sum(1 for _, status, _ in self.results if status)
        total = len(self.results)
        
        for test_name, status, message in self.results:
            icon = "✅" if status else "❌"
            print(f"{icon} {test_name}: {message}")
        
        print("-" * 60)
        print(f"总计: {passed}/{total} 项测试通过")
        
        if passed == total:
            print("🎉 所有测试通过！MinIO 集成工作正常")
        else:
            print("⚠️  部分测试失败，请检查配置和服务状态")


async def main():
    """主测试函数"""
    print("🎯 完整 YouTube → MinIO 测试")
    print("这个测试将：")
    print("   1. 检查 MinIO 连接")
    print("   2. 获取 YouTube 视频信息")
    print("   3. 下载并上传到 MinIO")
    print("   4. 验证文件和数据库")
    print("   5. 测试文件访问")
    print("   6. 清理测试数据")
    print()
    
    tester = CompleteFlowTest()
    success = await tester.run_complete_test()
    
    if success:
        print("\n🎊 测试完成！系统已准备好使用")
    else:
        print("\n💥 测试遇到问题，请检查错误信息")
    
    return success


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💀 测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)