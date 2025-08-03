#!/usr/bin/env python3
"""
简化的音频分割器，仅使用ffmpeg，不依赖pydub
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

def split_audio_simple(
    input_file: str,
    output_dir: str,
    max_segment_len: int = 45000,
    min_segment_len: int = 10000,
    silence_thresh: int = -35,
    min_silence_len: int = 500
) -> List[str]:
    """
    使用ffmpeg进行简单的音频分割
    
    由于不依赖pydub，使用基于时长的简单分割策略
    
    Args:
        input_file: 输入音频文件路径
        output_dir: 输出目录
        max_segment_len: 最大片段长度（毫秒）
        min_segment_len: 最小片段长度（毫秒）
        silence_thresh: 静音阈值（dB，仅用于兼容性）
        min_silence_len: 最小静音长度（毫秒，仅用于兼容性）
    
    Returns:
        分割后的文件路径列表
    """
    
    logger.info(f"开始简单音频分割: {input_file}")
    
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取音频时长
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"获取音频时长失败: {result.stderr}")
        
        duration = float(result.stdout.strip())
        logger.info(f"音频时长: {duration:.2f}秒")
        
        # 计算分割点
        segment_duration = min(max_segment_len / 1000, 30)  # 30秒或用户指定的最大值
        num_segments = max(1, int(duration // segment_duration))
        
        # 如果音频很短，直接返回原文件
        if duration * 1000 < min_segment_len:
            logger.warning(f"音频太短 ({duration:.2f}s)，无法分割")
            output_file = os.path.join(output_dir, "segment_001.wav")
            
            # 复制文件
            cmd = ['cp', input_file, output_file]
            subprocess.run(cmd, check=True)
            
            return [output_file]
        
        output_files = []
        
        # 生成分割点
        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, duration)
            
            # 确保最后一段不小于最小长度
            if end_time - start_time < min_segment_len / 1000 and i > 0:
                # 合并到最后一段
                break
            
            output_file = os.path.join(output_dir, f"segment_{i+1:03d}.wav")
            
            # 使用ffmpeg分割
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(end_time - start_time),
                '-c', 'copy',
                '-y',
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"ffmpeg分割失败: {result.stderr}")
                raise Exception(f"音频分割失败: {result.stderr}")
            
            output_files.append(output_file)
            logger.info(f"生成分段 {i+1}: {start_time:.2f}s - {end_time:.2f}s")
        
        logger.info(f"音频分割完成，生成 {len(output_files)} 个片段")
        return output_files if output_files else []
        
    except Exception as e:
        logger.error(f"音频分割失败: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="简单音频分割器")
    parser.add_argument("input_file", help="输入音频文件")
    parser.add_argument("-o", "--output-dir", help="输出目录", default="splits")
    parser.add_argument("-m", "--max-length", type=int, default=45000, 
                       help="最大片段长度（毫秒）")
    parser.add_argument("--min-length", type=int, default=10000,
                       help="最小片段长度（毫秒）")
    
    args = parser.parse_args()
    
    try:
        files = split_audio_simple(
            args.input_file,
            args.output_dir,
            max_segment_len=args.max_length,
            min_segment_len=args.min_length
        )
        print(f"成功生成 {len(files)} 个文件:")
        for f in files:
            print(f"  {f}")
    except Exception as e:
        print(f"错误: {e}")
        exit(1)