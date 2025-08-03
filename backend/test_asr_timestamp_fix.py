#!/usr/bin/env python3
"""
测试ASR时间戳计算修复
验证基于wav文件实际时长的增强时间戳调整逻辑
"""

import os
import tempfile
import json
import re
from pathlib import Path
from app.services.asr_timestamp_utils import (
    get_wav_duration, 
    adjust_timestamps_with_duration, 
    create_srt_content,
    validate_segments
)


def create_test_wav(duration_seconds: float, sample_rate: int = 16000) -> str:
    """创建测试WAV文件"""
    import wave
    import numpy as np
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        # 生成简单的正弦波
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        
        with wave.open(f.name, 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        return f.name


def test_wav_duration_calculation():
    """测试WAV时长计算"""
    print("🧪 测试WAV时长计算...")
    
    # 创建不同时长的测试文件
    test_cases = [1.5, 5.0, 30.5, 120.75]
    
    for expected_duration in test_cases:
        wav_path = create_test_wav(expected_duration)
        actual_duration = get_wav_duration(wav_path)
        
        print(f"期望时长: {expected_duration}s, 实际计算: {actual_duration}s")
        assert abs(actual_duration - expected_duration) < 0.01, f"时长计算错误: {actual_duration} vs {expected_duration}"
        
        # 清理测试文件
        os.unlink(wav_path)
    
    print("✅ WAV时长计算测试通过")


def test_timestamp_adjustment():
    """测试时间戳调整"""
    print("🧪 测试时间戳调整...")
    
    # 创建测试数据
    test_files = ["segment_001.wav", "segment_002.wav", "segment_003.wav"]
    test_durations = [10.5, 15.2, 8.3]  # 实际时长
    
    # 模拟ASR结果
    results = []
    for i, (filename, duration) in enumerate(zip(test_files, test_durations)):
        # 模拟ASR识别的片段（相对于文件开始时间）
        segments = [
            {'start': 0.0, 'end': 3.5, 'text': '第一段文本'},
            {'start': 4.0, 'end': 8.2, 'text': '第二段文本'},
            {'start': 8.5, 'end': 9.8, 'text': '第三段文本'}
        ]
        
        results.append({
            'index': i + 1,
            'file_path': filename,
            'segments': segments,
            'wav_duration': duration,
            'processing_duration': 2.5  # 模拟处理耗时
        })
    
    # 测试时间戳调整
    adjusted_segments = adjust_timestamps_with_duration(results)
    
    # 验证结果
    expected_total_duration = sum(test_durations)
    actual_total_duration = adjusted_segments[-1]['end'] if adjusted_segments else 0
    
    print(f"期望总时长: {expected_total_duration}s")
    print(f"实际总时长: {actual_total_duration}s")
    
    # 验证时间戳连续性
    for i in range(1, len(adjusted_segments)):
        prev_end = adjusted_segments[i-1]['end']
        curr_start = adjusted_segments[i]['start']
        assert curr_start >= prev_end, f"时间戳不连续: {curr_start} < {prev_end}"
    
    # 验证每个片段的时间戳
    offset = 0
    for result in results:
        for original_segment in result['segments']:
            expected_start = original_segment['start'] + offset
            expected_end = original_segment['end'] + offset
            
            found = False
            for segment in adjusted_segments:
                if abs(segment['start'] - expected_start) < 0.01 and abs(segment['end'] - expected_end) < 0.01:
                    found = True
                    break
            
            assert found, f"找不到期望的时间戳: {expected_start} - {expected_end}"
        
        offset += result['wav_duration']
    
    print("✅ 时间戳调整测试通过")
    return adjusted_segments


def test_srt_generation():
    """测试SRT文件生成"""
    print("🧪 测试SRT文件生成...")
    
    # 测试数据
    segments = [
        {'start': 0.0, 'end': 3.5, 'text': 'Hello world'},
        {'start': 4.0, 'end': 7.2, 'text': 'This is a test'},
        {'start': 8.0, 'end': 10.5, 'text': 'Goodbye'}
    ]
    
    srt_content = create_srt_content(segments)
    
    # 打印调试信息
    print(f"SRT内容: {repr(srt_content)}")
    lines = srt_content.strip().split('\n')
    print(f"行数: {len(lines)}, 内容: {lines}")
    
    # 验证SRT格式 - 3个片段，每个片段4行：序号、时间戳、文本、空行
    # 但实际上最后一个片段后面没有空行，所以是11行
    expected_lines = 11  # 3个片段 * 3行（序号、时间戳、文本） + 2个空行（前两个片段后）
    assert len(lines) == expected_lines, f"期望{expected_lines}行，实际{len(lines)}行"
    
    # 验证时间戳格式 - 检查所有时间戳行
    time_pattern = r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}'
    time_lines = [lines[i] for i in range(1, len(lines), 4) if i < len(lines)]
    for time_line in time_lines:
        assert re.match(time_pattern, time_line), f"时间戳格式错误: {time_line}"
    
    print("✅ SRT文件生成测试通过")


def test_segment_validation():
    """测试片段验证"""
    print("🧪 测试片段验证...")
    
    # 测试数据包含无效片段
    segments = [
        {'start': 0.0, 'end': 3.5, 'text': 'Valid segment'},
        {'start': -1.0, 'end': 2.0, 'text': 'Invalid start time'},  # 应该被移除
        {'start': 4.0, 'end': 4.0, 'text': 'Invalid duration'},  # 应该被移除
        {'start': 5.0, 'end': 3.0, 'text': 'Invalid order'},  # 应该被移除
        {'start': 6.0, 'end': 8.0, 'text': ''},  # 空文本，应该被移除
        {'start': 6.5, 'end': 9.0, 'text': 'Overlapping segment'}  # 应该被调整
    ]
    
    validated_segments = validate_segments(segments)
    
    # 验证结果
    assert len(validated_segments) == 2, f"期望2个有效片段，实际{len(validated_segments)}"
    assert validated_segments[0]['start'] == 0.0 and validated_segments[0]['end'] == 3.5
    assert validated_segments[1]['start'] == 6.5 and validated_segments[1]['end'] == 9.0
    
    # 验证时间戳连续性
    assert validated_segments[1]['start'] >= validated_segments[0]['end']
    
    print("✅ 片段验证测试通过")


def run_all_tests():
    """运行所有测试"""
    print("🚀 开始ASR时间戳计算修复测试...\n")
    
    try:
        test_wav_duration_calculation()
        adjusted_segments = test_timestamp_adjustment()
        test_srt_generation()
        test_segment_validation()
        
        print("\n🎉 所有测试通过！ASR时间戳计算修复已验证成功")
        print(f"总共生成了 {len(adjusted_segments)} 个调整后的字幕片段")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()