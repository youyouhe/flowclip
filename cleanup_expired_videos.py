#!/usr/bin/env python3
"""
清理超期视频脚本
删除超过48小时的已完成视频
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class VideoCleaner:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None

    def login(self, username: str = "hem", password: str = "123zxcZXC") -> bool:
        """登录系统获取token"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"username": username, "password": password}
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                print(f"✓ 登录成功，获取到token")
                return True
            else:
                print(f"✗ 登录失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 登录异常: {str(e)}")
            return False

    def get_videos(self) -> List[Dict]:
        """获取视频列表"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/videos/")

            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                print(f"✓ 获取到 {len(videos)} 个视频")
                return videos
            else:
                print(f"✗ 获取视频列表失败: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"✗ 获取视频列表异常: {str(e)}")
            return []

    def get_expired_videos(self, videos: List[Dict], hours_threshold: int = 48) -> List[Dict]:
        """获取超过指定时间的已完成视频"""
        expired_videos = []
        threshold_time = datetime.now() - timedelta(hours=hours_threshold)

        for video in videos:
            # 只处理已完成的视频
            if video.get("status") != "completed":
                continue

            # 解析创建时间
            created_at_str = video.get("created_at")
            if not created_at_str:
                continue

            try:
                # 处理ISO格式时间字符串
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                # 转换为本地时间进行比较
                if created_at.tzinfo is not None:
                    created_at = created_at.replace(tzinfo=None)

                if created_at < threshold_time:
                    video['hours_ago'] = (datetime.now() - created_at).total_seconds() / 3600
                    expired_videos.append(video)

            except Exception as e:
                print(f"✗ 解析视频 {video.get('id')} 时间失败: {str(e)}")
                continue

        return expired_videos

    def delete_video(self, video_id: int) -> bool:
        """删除指定视频"""
        try:
            response = self.session.delete(f"{self.base_url}/api/v1/videos/{video_id}")

            if response.status_code == 200:
                print(f"✓ 成功删除视频 {video_id}")
                return True
            else:
                print(f"✗ 删除视频 {video_id} 失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 删除视频 {video_id} 异常: {str(e)}")
            return False

    def clean_expired_videos(self, hours_threshold: int = 48, dry_run: bool = False) -> int:
        """清理超期视频的主函数"""
        print(f"{'='*60}")
        print(f"开始清理超期视频（超过 {hours_threshold} 小时）")
        print(f"模式: {'试运行（不会实际删除）' if dry_run else '正式删除'}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        # 1. 登录
        if not self.login():
            return 0

        # 2. 获取视频列表
        videos = self.get_videos()
        if not videos:
            print("没有找到视频，退出")
            return 0

        # 3. 筛选超期视频
        expired_videos = self.get_expired_videos(videos, hours_threshold)

        if not expired_videos:
            print(f"没有超过 {hours_threshold} 小时的已完成视频，退出")
            return 0

        print(f"\n找到 {len(expired_videos)} 个超期视频:")
        print("-" * 80)
        print(f"{'ID':<5} {'标题':<30} {'创建时间':<20} {'超时(小时)':<10}")
        print("-" * 80)

        for video in expired_videos:
            title = video.get('title', 'N/A')[:28] + '..' if len(video.get('title', '')) > 30 else video.get('title', 'N/A')
            created_at = video.get('created_at', 'N/A')[:19]
            hours_ago = f"{video.get('hours_ago', 0):.1f}"
            print(f"{video.get('id'):<5} {title:<30} {created_at:<20} {hours_ago:<10}")

        print("-" * 80)

        if dry_run:
            print(f"\n[试运行] 将删除 {len(expired_videos)} 个视频")
            return len(expired_videos)

        # 4. 删除超期视频
        deleted_count = 0
        print(f"\n开始删除超期视频...")

        for video in expired_videos:
            video_id = video.get('id')
            title = video.get('title', 'N/A')

            print(f"正在删除视频 {video_id}: {title[:50]}...")
            if self.delete_video(video_id):
                deleted_count += 1
            else:
                print(f"删除失败，跳过")

        print(f"\n{'='*60}")
        print(f"清理完成！")
        print(f"总计找到: {len(expired_videos)} 个超期视频")
        print(f"成功删除: {deleted_count} 个视频")
        print(f"失败: {len(expired_videos) - deleted_count} 个视频")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        return deleted_count

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='清理超期视频脚本')
    parser.add_argument('--hours', type=int, default=48, help='超时阈值（小时），默认48小时')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式，不实际删除')
    parser.add_argument('--base-url', type=str, default='http://localhost:8001', help='API基础URL')

    args = parser.parse_args()

    cleaner = VideoCleaner(args.base_url)
    deleted_count = cleaner.clean_expired_videos(args.hours, args.dry_run)

    # 如果是试运行模式，返回找到的视频数量
    if args.dry_run:
        sys.exit(0)  # 试运行总是返回成功
    else:
        # 如果删除失败的视频超过成功删除的视频，返回错误码
        total_expired = len(cleaner.get_expired_videos(cleaner.get_videos(), args.hours))
        if deleted_count == 0 and total_expired > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()