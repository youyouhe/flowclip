#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import requests
import concurrent.futures
import argparse
import re
import wave
from datetime import datetime
from tqdm import tqdm

def parse_srt_text(srt_text):
    """解析SRT格式文本，提取字幕片段"""
    segments = []
    
    # 使用正则表达式提取SRT片段
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\d+\n|$)'
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

def time_to_seconds(time_str):
    """将SRT时间格式转换为秒数"""
    h, m, rest = time_str.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def seconds_to_time(seconds):
    """将秒数转换为SRT时间格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def get_wav_duration(file_path):
    """获取WAV文件的时长（秒）"""
    try:
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            duration = frames / sample_rate
            return duration
    except Exception as e:
        print(f"获取文件 {file_path} 时长失败: {e}")
        return None

def process_audio_file(file_path, api_url, index, lang="auto", retry_count=3, retry_delay=2, model_type="whisper"):
    """处理单个音频文件，调用ASR API获取识别结果 - 优化版本"""
    print(f"处理文件 {index}: {file_path}")
    start_time = time.time()

    # 检查文件是否存在和大小
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 {file_path}")
        return {
            'index': index,
            'file_path': file_path,
            'error': '文件不存在'
        }

    file_size = os.path.getsize(file_path)
    print(f"文件大小: {file_size} bytes ({file_size/1024/1024:.2f}MB)")

    # 如果文件太小，可能是空文件
    if file_size < 100:
        print(f"警告: 文件可能为空，大小: {file_size} bytes")
        # 直接抛出异常，避免将空文件提交给ASR服务
        raise Exception(f'文件太小，可能是空文件，大小: {file_size} bytes')

    # 创建优化的requests session
    session = requests.Session()

    # 设置重试策略 - 针对大文件上传优化
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,  # 总重试次数
        backoff_factor=2,  # 指数退避
        status_forcelist=[429, 500, 502, 503, 504],  # 重试的HTTP状态码
        allowed_methods=["POST"]  # 允许重试POST请求
    )

    # 设置连接池优化
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,  # 连接池大小
        pool_maxsize=20,     # 最大连接数
        pool_block=False     # 不阻塞获取连接
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # 根据文件大小动态调整超时时间
    # 连接超时30秒，读取超时根据文件大小计算
    base_read_timeout = 1800  # 30分钟基础读取超时
    size_multiplier = file_size / (1024 * 1024) * 60  # 每MB额外60秒
    read_timeout = max(base_read_timeout + int(size_multiplier), 7200)  # 最长2小时读取超时
    timeout_config = (30, read_timeout)  # (连接超时, 读取超时)

    print(f"优化配置: 连接超时=30秒, 读取超时={read_timeout}秒, 重试次数=3")

    for attempt in range(retry_count):
        try:
            # 使用优化后的session和chunked上传
            with open(file_path, 'rb') as audio_file:
                # 根据模型类型构建不同的请求参数
                files = {"file": (os.path.basename(file_path), audio_file, 'audio/wav')}

                if model_type == "whisper":
                    # Whisper模型请求参数
                    data = {
                        "response_format": "srt",
                        "language": lang
                    }
                    # Whisper模型使用/inference路径
                    if not api_url.endswith("/inference"):
                        final_api_url = api_url.rstrip('/') + "/inference"
                    else:
                        final_api_url = api_url
                else:  # sense模型
                    # Sense模型请求参数
                    data = {
                        "lang": lang
                    }
                    # Sense模型使用/asr路径
                    if not api_url.endswith("/asr"):
                        final_api_url = api_url.rstrip('/') + "/asr"
                    else:
                        final_api_url = api_url

                print(f"使用模型类型: {model_type}, 请求URL: {final_api_url}")
                print(f"开始上传 (尝试 {attempt+1}/{retry_count})...")

                # 使用优化的session发送请求，启用chunked传输
                response = session.post(
                    final_api_url,
                    files=files,
                    data=data,
                    timeout=timeout_config,
                    stream=False  # 关闭streaming，避免内存问题
                )
                response.raise_for_status()

                # 记录上传时间和速度
                upload_time = time.time() - start_time
                upload_speed_mb = file_size / (upload_time * 1024 * 1024) if upload_time > 0 else 0
                print(f"✅ 上传完成！耗时: {upload_time:.2f}秒，平均速度: {upload_speed_mb:.2f}MB/s")

                # 处理不同模型的响应格式
                # 两种模型都返回JSON格式，需要解析data字段
                result = response.json()
                # 检查API返回是否成功
                if result['code'] != 0:
                    raise Exception(f"API返回错误: {result['msg']}")
                # 解析返回的SRT文本
                srt_text = result['data']

                segments = parse_srt_text(srt_text)

                # 获取wav文件的实际时长
                wav_duration = get_wav_duration(file_path)

                total_duration = time.time() - start_time
                if wav_duration:
                    print(f"🎉 文件 {index} 处理完成！总耗时: {total_duration:.2f}秒，识别了 {len(segments)} 个片段，文件时长: {wav_duration:.2f}秒")
                    print(f"📊 性能统计: 上传={upload_time:.2f}s, 处理={total_duration-upload_time:.2f}s, 速度={upload_speed_mb:.2f}MB/s")
                else:
                    print(f"🎉 文件 {index} 处理完成！总耗时: {total_duration:.2f}秒，识别了 {len(segments)} 个片段，无法获取文件时长")
                    print(f"📊 性能统计: 上传={upload_time:.2f}s, 处理={total_duration-upload_time:.2f}s, 速度={upload_speed_mb:.2f}MB/s")

                return {
                    'index': index,
                    'file_path': file_path,
                    'segments': segments,
                    'processing_duration': total_duration,
                    'wav_duration': wav_duration,
                    'upload_speed_mbps': upload_speed_mb,
                    'upload_duration': upload_time
                }
        except requests.exceptions.Timeout as e:
            error_msg = f"请求超时: {str(e)}"
            print(f"❌ 处理文件 {file_path} 尝试 {attempt+1}/{retry_count} 超时失败: {error_msg}")
            if attempt < retry_count - 1:
                sleep_time = retry_delay * (2 ** attempt)
                print(f"⏰ 等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
            else:
                print(f"💀 达到最大重试次数，放弃文件: {file_path}")
                return {
                    'index': index,
                    'file_path': file_path,
                    'error': error_msg
                }
        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接错误: {str(e)}"
            print(f"❌ 处理文件 {file_path} 尝试 {attempt+1}/{retry_count} 连接失败: {error_msg}")
            if attempt < retry_count - 1:
                sleep_time = retry_delay * (2 ** attempt)
                print(f"⏰ 等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
            else:
                print(f"💀 达到最大重试次数，放弃文件: {file_path}")
                return {
                    'index': index,
                    'file_path': file_path,
                    'error': error_msg
                }
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            print(f"❌ 处理文件 {file_path} 尝试 {attempt+1}/{retry_count} 失败: {error_msg}")
            if attempt < retry_count - 1:
                sleep_time = retry_delay * (2 ** attempt)
                print(f"⏰ 等待 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
            else:
                print(f"💀 达到最大重试次数，放弃文件: {file_path}")
                return {
                    'index': index,
                    'file_path': file_path,
                    'error': error_msg
                }
        finally:
            # 确保session被正确关闭
            session.close()

def process_directory(directory, api_url, lang="auto", max_workers=5):
    """处理目录中的所有WAV文件"""
    # 获取所有WAV文件并按段落顺序排序
    wav_files = [f for f in os.listdir(directory) if f.endswith('.wav')]
    wav_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
    
    file_paths = [os.path.join(directory, filename) for filename in wav_files]
    results = []
    
    # 使用线程池并行处理文件
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建任务
        future_to_file = {
            executor.submit(process_audio_file, file_path, api_url, i+1, lang): (i, file_path)
            for i, file_path in enumerate(file_paths)
        }
        
        # 使用tqdm显示进度
        with tqdm(total=len(file_paths), desc="处理文件") as pbar:
            for future in concurrent.futures.as_completed(future_to_file):
                idx, file_path = future_to_file[future]
                try:
                    data = future.result()
                    results.append(data)
                    pbar.update(1)
                except Exception as exc:
                    print(f"{file_path} 生成了异常: {exc}")
                    results.append({
                        'index': idx,
                        'file_path': file_path,
                        'error': str(exc)
                    })
                    pbar.update(1)
    
    # 按原始索引排序结果
    results.sort(key=lambda x: x['index'])
    return results

def adjust_timestamps(results):
    """调整时间戳以确保连续性，基于wav文件的实际时长"""
    all_segments = []
    current_offset = 0
    
    for result in results:
        if 'error' in result:
            continue
            
        # 获取当前文件的所有片段和实际时长
        segments = result.get('segments', [])
        wav_duration = result.get('wav_duration')
        
        # 调整时间戳并添加到结果中
        for segment in segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start'] += current_offset
            adjusted_segment['end'] += current_offset
            all_segments.append(adjusted_segment)
        
        # 更新偏移量：优先使用wav文件的实际时长，否则使用最后一个片段的结束时间
        if wav_duration is not None:
            # 使用wav文件的实际时长，确保与视频时间轴对齐
            audio_length = wav_duration
            print(f"使用文件实际时长: {audio_length:.2f}秒")
        elif segments:
            # fallback到最后一个片段的结束时间
            audio_length = segments[-1]['end']
            print(f"使用最后片段结束时间: {audio_length:.2f}秒（注意：可能与视频不匹配）")
        else:
            # 没有片段也没有时长信息，跳过这个文件
            audio_length = 0
            print("警告：无法确定音频长度，跳过此文件")
        
        current_offset += audio_length
    
    return all_segments

def create_srt(segments, output_file):
    """创建SRT格式字幕文件，带UTF-8 BOM以支持中文"""
    with open(output_file, 'w', encoding='utf-8-sig') as f:
        # 写入UTF-8 BOM (EF BB BF)
        # encoding='utf-8-sig' 会自动添加BOM
        for i, segment in enumerate(segments):
            # 序号
            f.write(f"{i+1}\n")
            
            # 时间戳
            start_time = seconds_to_time(segment['start'])
            end_time = seconds_to_time(segment['end'])
            f.write(f"{start_time} --> {end_time}\n")
            
            # 文本内容
            text = segment['text'].strip()
            # 确保文本是UTF-8编码
            f.write(f"{text}\n\n")

def save_json_result(results, output_file):
    """保存原始JSON结果，便于后期处理"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def setup_logging(log_file=None):
    """设置日志记录"""
    import logging
    
    # 创建logger
    logger = logging.getLogger('wav_to_srt')
    logger.setLevel(logging.INFO)
    
    # 创建控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加handler到logger
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def main():
    parser = argparse.ArgumentParser(description='处理WAV文件并生成SRT字幕')
    parser.add_argument('directory', help='包含WAV文件的目录')
    parser.add_argument('--api-url', default='http://192.168.8.107:5001/asr', help='ASR API URL')
    parser.add_argument('--lang', default='auto', help='语言代码，默认为自动检测(auto)')
    parser.add_argument('--workers', type=int, default=5, help='并行处理的线程数')
    parser.add_argument('--output', help='输出SRT文件路径')
    parser.add_argument('--log', help='日志文件路径')
    parser.add_argument('--retry', type=int, default=3, help='API调用失败时的重试次数')
    parser.add_argument('--retry-delay', type=int, default=2, help='重试间隔的基础秒数')
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.log)
    
    # 如果未指定输出文件，使用目录名称
    if not args.output:
        dir_name = os.path.basename(os.path.normpath(args.directory))
        args.output = f"{dir_name}.srt"
    
    # 处理目录中的WAV文件
    logger.info(f"开始处理目录: {args.directory}")
    logger.info(f"使用ASR API: {args.api_url}")
    start_time = time.time()
    results = process_directory(args.directory, args.api_url, args.lang, args.workers)
    
    # 保存原始结果
    json_output = os.path.splitext(args.output)[0] + '.json'
    save_json_result(results, json_output)
    logger.info(f"原始结果已保存至: {json_output}")
    
    # 统计成功和失败的文件
    success_count = len([r for r in results if 'error' not in r])
    fail_count = len([r for r in results if 'error' in r])
    logger.info(f"处理文件统计: 成功={success_count}, 失败={fail_count}, 总计={len(results)}")
    
    if success_count > 0:
        # 调整时间戳
        logger.info("调整时间戳...")
        adjusted_segments = adjust_timestamps(results)
        
        # 创建SRT文件
        logger.info(f"创建SRT文件: {args.output}")
        create_srt(adjusted_segments, args.output)
        logger.info(f"共生成 {len(adjusted_segments)} 条字幕")
    else:
        logger.error("没有成功处理的文件，无法生成SRT")
    
    duration = time.time() - start_time
    logger.info(f"处理完成，总耗时: {duration:.2f}秒")
    logger.info(f"生成的SRT文件: {args.output}")

if __name__ == "__main__":
    main()