"""
ASR时间戳计算工具模块
基于wav_to_srt_direct_updated.py的增强时间戳计算逻辑
"""

import wave
import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_wav_duration(file_path: str) -> Optional[float]:
    """获取WAV文件的时长（秒）"""
    try:
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            duration = frames / sample_rate
            return duration
    except Exception as e:
        logger.error(f"获取文件 {file_path} 时长失败: {e}")
        return None


def time_to_seconds(time_str: str) -> float:
    """将SRT时间格式转换为秒数"""
    h, m, rest = time_str.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def seconds_to_time(seconds: float) -> str:
    """将秒数转换为SRT时间格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_text(srt_text: str) -> List[Dict[str, Any]]:
    """解析SRT格式文本，提取字幕片段"""
    segments = []
    
    # 使用正则表达式提取SRT片段
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --\u003e (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\d+\n|$)'
    matches = re.findall(pattern, srt_text)
    
    for match in matches:
        idx, start_time_str, end_time_str, text = match
        start_seconds = time_to_seconds(start_time_str)
        end_seconds = time_to_seconds(end_time_str)
        
        segments.append({
            'start': start_seconds,
            'end': end_seconds,
            'text': text.strip()
        })
    
    return segments


def adjust_timestamps_with_duration(results: List[Dict[str, Any]], time_offset: float = 0.0) -> List[Dict[str, Any]]:
    """
    基于wav文件实际时长调整时间戳的增强版本
    
    Args:
        results: ASR处理结果列表，每个元素包含：
                - file_path: 音频文件路径
                - segments: 识别出的字幕片段
                - wav_duration: WAV文件实际时长（可选）
        time_offset: 时间偏移量（秒），用于调整所有时间戳
    
    Returns:
        调整后的字幕片段列表
    """
    all_segments = []
    current_offset = time_offset  # 使用传入的时间偏移量作为起始偏移
    
    for result in results:
        if 'error' in result:
            logger.warning(f"跳过有错误的文件: {result.get('file_path', 'unknown')}")
            continue
            
        # 获取当前文件的所有片段和实际时长
        segments = result.get('segments', [])
        file_path = result.get('file_path', '')
        
        # 优先使用wav_duration，如果没有则计算
        wav_duration = result.get('wav_duration')
        if wav_duration is None and file_path:
            wav_duration = get_wav_duration(file_path)
            
        # 调整时间戳并添加到结果中
        for segment in segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start'] += current_offset
            adjusted_segment['end'] += current_offset
            adjusted_segment['original_file'] = file_path
            all_segments.append(adjusted_segment)
        
        # 更新偏移量：优先使用wav文件的实际时长
        if wav_duration is not None:
            # 使用wav文件的实际时长，确保与视频时间轴对齐
            audio_length = wav_duration
            logger.info(f"使用文件实际时长: {audio_length:.2f}秒 - {file_path}")
        elif segments:
            # fallback到最后一个片段的结束时间
            audio_length = segments[-1]['end']
            logger.warning(f"使用最后片段结束时间: {audio_length:.2f}秒 - {file_path}（可能与视频不匹配）")
        else:
            # 没有片段也没有时长信息，使用默认值
            audio_length = 0
            logger.warning(f"无法确定音频长度，跳过此文件: {file_path}")
        
        current_offset += audio_length
    
    return all_segments


def create_srt_content(segments: List[Dict[str, Any]]) -> str:
    """创建SRT格式字幕内容，确保UTF-8编码"""
    content = []
    
    for i, segment in enumerate(segments):
        # 序号
        content.append(str(i + 1))
        
        # 时间戳
        start_time = seconds_to_time(segment['start'])
        end_time = seconds_to_time(segment['end'])
        content.append(f"{start_time} --> {end_time}")
        
        # 文本内容 - 确保正确处理中文
        text = segment['text'].strip()
        # 清理可能的编码问题
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        content.append(text)
        content.append("")  # 空行分隔
    
    return "\n".join(content)


def validate_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """验证和清理字幕片段"""
    validated_segments = []
    
    for i, segment in enumerate(segments):
        # 确保时间戳是有效的
        if segment['start'] < 0 or segment['end'] < 0:
            logger.warning(f"跳过无效时间戳: start={segment['start']}, end={segment['end']}")
            continue
            
        if segment['start'] >= segment['end']:
            logger.warning(f"跳过无效时间段: start={segment['start']}, end={segment['end']}")
            continue
            
        if not segment['text'].strip():
            logger.warning("跳过空文本片段")
            continue
            
        validated_segments.append(segment)
    
    # 确保时间戳连续性
    for i in range(1, len(validated_segments)):
        if validated_segments[i]['start'] < validated_segments[i-1]['end']:
            # 调整时间戳确保连续性
            validated_segments[i]['start'] = validated_segments[i-1]['end']
    
    return validated_segments