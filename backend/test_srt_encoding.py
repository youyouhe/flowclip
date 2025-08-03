#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试SRT文件编码的脚本
用于验证SRT文件是否正确生成UTF-8编码内容
"""

import tempfile
import os
from pathlib import Path

def test_srt_encoding():
    """测试SRT文件是否能正确生成UTF-8编码"""
    
    # 测试中文内容
    test_segments = [
        {
            'start': 0.0,
            'end': 3.5,
            'text': '大家好，欢迎来到这个视频'
        },
        {
            'start': 4.0,
            'end': 7.8,
            'text': '今天我们来讨论一下这个重要的话题'
        },
        {
            'start': 8.0,
            'end': 12.3,
            'text': '首先，让我来介绍一下背景知识'
        }
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        srt_file = temp_path / "test_chinese.srt"
        
        # 使用UTF-8-sig编码（带BOM）
        with open(srt_file, 'w', encoding='utf-8-sig') as f:
            for i, segment in enumerate(test_segments):
                # 序号
                f.write(f"{i+1}\n")
                
                # 时间戳
                start_time = f"{int(segment['start']//3600):02d}:{int((segment['start']%3600)//60):02d}:{int(segment['start']%60):02d},{int((segment['start']%1)*1000):03d}"
                end_time = f"{int(segment['end']//3600):02d}:{int((segment['end']%3600)//60):02d}:{int(segment['end']%60):02d},{int((segment['end']%1)*1000):03d}"
                f.write(f"{start_time} --> {end_time}\n")
                
                # 文本内容
                f.write(f"{segment['text']}\n\n")
        
        # 验证文件内容
        print(f"测试文件已创建: {srt_file}")
        
        # 检查文件编码
        with open(srt_file, 'rb') as f:
            content = f.read()
            
        # 检查BOM
        has_bom = content.startswith(b'\xef\xbb\xbf')
        print(f"文件包含UTF-8 BOM: {has_bom}")
        
        # 检查文件内容
        with open(srt_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        print("文件内容:")
        print(content)
        
        # 验证中文显示
        if "大家好" in content:
            print("✅ 中文内容正确保存")
        else:
            print("❌ 中文内容可能有问题")
        
        return True

if __name__ == "__main__":
    print("开始测试SRT文件编码...")
    test_srt_encoding()
    print("测试完成！")