import os
import argparse
from pydub import AudioSegment
from pydub.silence import detect_silence, detect_nonsilent
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

# 默认参数
DEFAULT_INPUT_FILE = "audio_sample.m4a"
DEFAULT_OUTPUT_DIR = None  # 将根据输入文件名自动生成
DEFAULT_MIN_SILENCE_LEN = 500  # 毫秒
DEFAULT_SILENCE_THRESH = -35  # dB
DEFAULT_MAX_SEGMENT_LEN = 45000  # 毫秒 (45秒)，放宽限制
DEFAULT_STRICT_MAX_LEN = 60000  # 毫秒 (60秒)，绝对最大限制
DEFAULT_MIN_SEGMENT_LEN = 10000  # 毫秒 (10秒)，避免太短的片段
DEFAULT_PAUSE_THRESHOLD = 1000  # 超过此值的静音可能是句子边界
DEFAULT_SEARCH_WINDOW = 10000  # 搜索窗口大小 (10秒)，扩大到10秒
DEFAULT_DEBUG = False

def load_audio(file_path):
    """加载音频文件，支持wav、m4a和mp3格式"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    print(f"尝试加载文件: {file_path}")
    
    if file_ext == '.m4a':
        audio = AudioSegment.from_file(file_path, format="m4a")
    elif file_ext == '.wav':
        audio = AudioSegment.from_wav(file_path)
    elif file_ext == '.mp3':
        audio = AudioSegment.from_mp3(file_path)
    else:
        raise ValueError(f"不支持的音频格式: {file_ext}")
    
    print(f"成功加载音频，长度: {len(audio)/1000:.2f}秒")
    return audio

def get_silence_chunks(audio, min_silence_len=DEFAULT_MIN_SILENCE_LEN, silence_thresh=DEFAULT_SILENCE_THRESH, debug=DEFAULT_DEBUG):
    """检测音频中的静音段"""
    print(f"使用参数检测静音: 最小静音长度={min_silence_len}ms, 静音阈值={silence_thresh}dB")
    silence_chunks = detect_silence(
        audio, 
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )
    
    # 如果没有检测到静音，尝试更宽松的参数
    if len(silence_chunks) == 0:
        print("未检测到静音，尝试更宽松的参数...")
        for thresh in [silence_thresh + 5, silence_thresh + 10, silence_thresh + 15]:
            print(f"  尝试静音阈值: {thresh}dB")
            silence_chunks = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=thresh)
            if len(silence_chunks) > 0:
                print(f"  使用阈值 {thresh}dB 检测到 {len(silence_chunks)} 个静音段")
                break
    
    # 如果还是没检测到，降低最小静音长度
    if len(silence_chunks) == 0:
        min_silence_len = min_silence_len // 2
        print(f"仍未检测到静音，降低最小静音长度至 {min_silence_len}ms")
        silence_chunks = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh + 15)
    
    # 如果上面的方法都失败了，尝试检测非静音段，然后取反
    if len(silence_chunks) == 0:
        print("所有常规方法都失败了，尝试检测非静音段...")
        non_silent_chunks = detect_nonsilent(audio, min_silence_len=100, silence_thresh=silence_thresh + 20)
        
        # 从非静音段构造静音段
        if non_silent_chunks:
            silence_chunks = []
            # 添加开始到第一个非静音段
            if non_silent_chunks[0][0] > 0:
                silence_chunks.append((0, non_silent_chunks[0][0]))
            
            # 添加非静音段之间的间隙
            for i in range(len(non_silent_chunks) - 1):
                silence_chunks.append((non_silent_chunks[i][1], non_silent_chunks[i+1][0]))
            
            # 添加最后一个非静音段到结束
            if non_silent_chunks[-1][1] < len(audio):
                silence_chunks.append((non_silent_chunks[-1][1], len(audio)))
    
    print(f"最终检测到 {len(silence_chunks)} 个静音段")
    
    # 计算静音长度分布
    if len(silence_chunks) > 0:
        silence_lengths = [end - start for start, end in silence_chunks]
        avg_silence = sum(silence_lengths) / len(silence_lengths)
        median_silence = np.median(silence_lengths)
        print(f"平均静音长度: {avg_silence:.2f}ms, 中位数: {median_silence:.2f}ms")
        print(f"最短静音: {min(silence_lengths)}ms, 最长静音: {max(silence_lengths)}ms")
        
        # 绘制静音长度分布图
        if debug and len(silence_lengths) > 5:
            plt.figure(figsize=(10, 6))
            plt.hist(silence_lengths, bins=50)
            plt.xlabel('Silence Length (ms)')
            plt.ylabel('Frequency')
            plt.title('Silence Length Distribution')
            plt.axvline(x=avg_silence, color='r', linestyle='--', label=f'Mean: {avg_silence:.0f}ms')
            plt.axvline(x=median_silence, color='g', linestyle='--', label=f'Median: {median_silence:.0f}ms')
            plt.legend()
            
            # 保存图表
            plt.savefig('silence_distribution.png')
            print("静音分布图已保存为 silence_distribution.png")
    
    return silence_chunks

def classify_silence_points(silence_chunks, pause_threshold=DEFAULT_PAUSE_THRESHOLD):
    """将静音点分类为句子内部停顿和句子间停顿"""
    # 计算静音长度
    silence_lengths = [end - start for start, end in silence_chunks]
    
    if not silence_lengths:
        return [], []
    
    # 如果有足够的样本，使用聚类来找到自然分界点
    if len(silence_lengths) >= 20:
        try:
            from sklearn.cluster import KMeans
            # 将长度重塑为适合KMeans的形式
            X = np.array(silence_lengths).reshape(-1, 1)
            
            # 首先尝试将静音分为三类：短暂噪音、句内停顿和句子边界
            kmeans = KMeans(n_clusters=3, random_state=0, n_init=10).fit(X)
            centers = sorted(kmeans.cluster_centers_.flatten())
            
            # 如果三类聚类效果不好，回退到两类
            if len(centers) == 3 and centers[1] - centers[0] < 100:
                # 前两类太接近，使用两类聚类
                kmeans = KMeans(n_clusters=2, random_state=0, n_init=10).fit(X)
                centers = sorted(kmeans.cluster_centers_.flatten())
            
            # 确定哪个中心点代表句子边界
            sentence_boundary_center = centers[-1]  # 最大的中心点
            
            # 使用中心点的70%作为阈值，而不是绝对值
            pause_threshold = max(sentence_boundary_center * 0.7, DEFAULT_PAUSE_THRESHOLD * 0.8)
            print(f"使用聚类分析确定的句子边界阈值: {pause_threshold:.2f}ms (聚类中心点: {centers})")
        except Exception as e:
            # 如果聚类失败，使用基于分位数的方法
            print(f"聚类分析失败 ({str(e)})，使用分位数方法确定阈值")
            q75 = np.percentile(silence_lengths, 75)
            median = np.median(silence_lengths)
            pause_threshold = max((q75 + median) / 2, DEFAULT_PAUSE_THRESHOLD * 0.8)
            print(f"使用分位数确定的句子边界阈值: {pause_threshold:.2f}ms")
    else:
        # 样本不足时使用分布分析
        median = np.median(silence_lengths)
        mean = np.mean(silence_lengths)
        pause_threshold = max((median + mean) / 2, DEFAULT_PAUSE_THRESHOLD * 0.8)
        print(f"样本不足，使用均值和中位数确定的句子边界阈值: {pause_threshold:.2f}ms")
    
    # 分类静音点
    sentence_boundaries = []
    within_sentence_pauses = []
    
    for i, (start, end) in enumerate(silence_chunks):
        length = end - start
        midpoint = (start + end) // 2
        
        if length >= pause_threshold:
            sentence_boundaries.append((midpoint, length))
        else:
            within_sentence_pauses.append((midpoint, length))
    
    print(f"识别出 {len(sentence_boundaries)} 个句子边界和 {len(within_sentence_pauses)} 个句内停顿")
    return sentence_boundaries, within_sentence_pauses

def find_energy_minimum(audio, start_time, end_time, window_size=200):
    """在给定区间内寻找能量最低点，用于在没有明显静音时找到最佳切割点"""
    if end_time <= start_time:
        return start_time
    
    # 提取音频片段
    segment = audio[start_time:end_time]
    if len(segment) < window_size:
        return (start_time + end_time) // 2
    
    # 计算滑动窗口能量
    min_energy = float('inf')
    min_pos = start_time
    
    # 使用小窗口计算局部能量
    for win_start in range(0, len(segment) - window_size, window_size // 2):
        win_end = win_start + window_size
        window = segment[win_start:win_end]
        # 使用RMS能量
        energy = window.rms
        if energy < min_energy:
            min_energy = energy
            min_pos = start_time + win_start + window_size // 2
    
    return min_pos

def get_split_points(audio, audio_length, silence_chunks,
                     max_segment_len=DEFAULT_MAX_SEGMENT_LEN,
                     strict_max_len=DEFAULT_STRICT_MAX_LEN,
                     min_segment_len=DEFAULT_MIN_SEGMENT_LEN,
                     pause_threshold=DEFAULT_PAUSE_THRESHOLD,
                     search_window=DEFAULT_SEARCH_WINDOW):
    """确定切割点，优先在句子边界处切割"""
    # 将静音点分类
    sentence_boundaries, within_sentence_pauses = classify_silence_points(silence_chunks, pause_threshold)
    
    # 所有可能的切割点
    all_cut_points = sentence_boundaries + within_sentence_pauses
    # 按位置排序
    all_cut_points.sort(key=lambda x: x[0])
    
    # 初始切割点
    split_points = [0]  # 起始点
    
    # 当前处理位置
    current_pos = 0
    
    while current_pos < audio_length:
        # 下一个理想切割位置
        next_pos = current_pos + max_segment_len
        
        # 如果已经接近结束，直接添加结束点
        if next_pos >= audio_length:
            if audio_length not in split_points:
                split_points.append(audio_length)
            break
        
        # 在理想位置前后寻找合适的切割点，扩大搜索范围
        search_start = max(current_pos + min_segment_len, next_pos - search_window)  # 不早于最小段长度
        
        # 使用两种搜索范围：
        # 1. 首选搜索区域：在目标位置前后的窗口内
        # 2. 扩展搜索区域：如果找不到合适点，可以接受更长的段落，但不超过绝对限制
        preferred_search_end = min(audio_length, next_pos + search_window)
        extended_search_end = min(audio_length, current_pos + strict_max_len)
        
        # 首先在首选区域搜索
        search_end = preferred_search_end
        
        # 候选切割点
        candidates = []
        
        # 首先考虑句子边界
        for pos, length in sentence_boundaries:
            if search_start <= pos <= search_end:
                # 根据距离理想位置的远近和静音长度评分
                distance = abs(pos - next_pos)
                # 新的评分公式，更偏好距离理想位置近的点
                score = length / (1 + distance * 0.0001)
                candidates.append((pos, score, "句子边界"))
        
        # 如果没有找到句子边界，考虑句内停顿
        if not candidates:
            for pos, length in within_sentence_pauses:
                if search_start <= pos <= search_end:
                    distance = abs(pos - next_pos)
                    score = length / (1 + distance * 0.0002)  # 句内停顿的分数权重低一些
                    candidates.append((pos, score, "句内停顿"))
        
        # 如果还是没找到，尝试在扩展区域搜索句子边界
        if not candidates and extended_search_end > preferred_search_end:
            print(f"在首选区域未找到合适切割点，扩展搜索至 {extended_search_end/1000:.2f}s")
            search_end = extended_search_end
            
            # 在扩展区域中寻找句子边界
            for pos, length in sentence_boundaries:
                if preferred_search_end < pos <= extended_search_end:
                    # 这里给予额外奖励，鼓励在句子边界处切割，即使会导致段落较长
                    score = length * 1.5  # 给予更高权重
                    candidates.append((pos, score, "扩展区句子边界"))
        
        # 如果还是没找到，尝试寻找能量最低点
        if not candidates:
            try:
                # 在理想位置附近找能量最小点
                ideal_search_start = max(current_pos + min_segment_len, next_pos - 2000)
                ideal_search_end = min(audio_length, next_pos + 2000)
                best_pos = find_energy_minimum(audio, ideal_search_start, ideal_search_end)
                candidates.append((best_pos, 0, "能量最低点"))
            except Exception as e:
                print(f"能量分析失败: {str(e)}")
                # 如果能量分析失败，使用硬切点
                candidates.append((next_pos, 0, "硬切点"))
        
        # 选择最佳切割点
        best_pos, best_score, cut_type = max(candidates, key=lambda x: x[1])
        
        # 添加切割点
        if best_pos not in split_points and best_pos < audio_length:
            split_points.append(best_pos)
            print(f"在 {best_pos/1000:.2f}s 处添加切割点 (类型: {cut_type})")
            current_pos = best_pos
        else:
            # 如果无法找到合适切割点，强制前进
            current_pos = next_pos
    
    # 确保最后一个点是音频结束
    if split_points[-1] != audio_length:
        split_points.append(audio_length)
    
    # 排序并返回
    split_points.sort()
    return split_points

def split_audio(input_file=DEFAULT_INPUT_FILE,
                output_dir=DEFAULT_OUTPUT_DIR,
                min_silence_len=DEFAULT_MIN_SILENCE_LEN,
                silence_thresh=DEFAULT_SILENCE_THRESH,
                max_segment_len=DEFAULT_MAX_SEGMENT_LEN,
                strict_max_len=DEFAULT_STRICT_MAX_LEN,
                min_segment_len=DEFAULT_MIN_SEGMENT_LEN,
                pause_threshold=DEFAULT_PAUSE_THRESHOLD,
                search_window=DEFAULT_SEARCH_WINDOW,
                debug=DEFAULT_DEBUG):
    """根据静音切割音频文件，优化为尽量在句子边界处切割"""
    try:
        # 加载音频
        print(f"加载音频文件: {input_file}")
        audio = load_audio(input_file)
        
        # 创建输出目录
        if output_dir is None:
            base_name = os.path.basename(input_file)
            file_name = os.path.splitext(base_name)[0]
            output_dir = f"enhanced_splits_{file_name[:30]}"
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")
        
        # 检测静音段
        print("检测静音段...")
        silence_chunks = get_silence_chunks(audio, min_silence_len, silence_thresh, debug)
        
        # 如果检测到的静音段太少，尝试能量检测
        if len(silence_chunks) < 10:
            print("检测到的静音段太少，尝试能量检测...")
            energy_regions = detect_sentence_energy(audio)
            if energy_regions:
                # 将能量检测的结果合并到静音检测结果
                silence_chunks.extend(energy_regions)
                silence_chunks.sort()
        
        # 确定切割点
        print("确定切割点...")
        split_points = get_split_points(
            audio,
            len(audio),
            silence_chunks,
            max_segment_len,
            strict_max_len,
            min_segment_len,
            pause_threshold,
            search_window
        )
        
        # 切割音频并保存
        print(f"将音频切割为 {len(split_points) - 1} 个片段...")
        output_files = []
        for i in range(len(split_points) - 1):
            start_time = split_points[i]
            end_time = split_points[i + 1]
            
            # 切割片段
            segment = audio[start_time:end_time]
            
            # 保存片段
            output_file = os.path.join(output_dir, f"segment_{i+1:03d}.wav")
            segment.export(output_file, format="wav")
            output_files.append(output_file)
            
            print(f"  片段 {i+1:03d}: {start_time/1000:.2f}s - {end_time/1000:.2f}s ({(end_time-start_time)/1000:.2f}s)")
        
        print(f"完成! 切割后的文件保存在 {output_dir} 目录中")
        return output_files if output_files else []
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
        return []  # 返回空列表表示失败

def detect_sentence_energy(audio, window_size=1000, step_size=100):
    """使用能量检测句子结构"""
    print("使用能量检测句子结构...")
    
    # 将音频转换为数组进行处理
    samples = np.array(audio.get_array_of_samples())
    
    # 计算滑动窗口能量
    energies = []
    positions = []
    for start in range(0, len(samples) - window_size, step_size):
        window = samples[start:start+window_size]
        energy = np.sum(window**2) / window_size
        energies.append(energy)
        positions.append(start)
    
    # 归一化能量
    energies = np.array(energies)
    norm_energies = (energies - np.min(energies)) / (np.max(energies) - np.min(energies))
    
    # 检测低能量区域（可能是句子边界）
    threshold = 0.2  # 能量阈值
    low_energy_regions = []
    in_low_region = False
    start_pos = 0
    
    for i, energy in enumerate(norm_energies):
        if not in_low_region and energy < threshold:
            in_low_region = True
            start_pos = positions[i]
        elif in_low_region and energy >= threshold:
            in_low_region = False
            end_pos = positions[i]
            if end_pos - start_pos > 300:  # 忽略太短的低能量区域
                low_energy_regions.append((start_pos, end_pos))
    
    print(f"检测到 {len(low_energy_regions)} 个低能量区域，可能是句子边界")
    return low_energy_regions

def parse_arguments():
    parser = argparse.ArgumentParser(description="基于静音和句子结构智能切割音频文件")
    parser.add_argument("input_file", nargs="?", default=DEFAULT_INPUT_FILE,
                      help=f"输入音频文件路径，默认: {DEFAULT_INPUT_FILE}")
    parser.add_argument("-o", "--output-dir", 
                      help="输出目录，默认根据输入文件名自动生成")
    parser.add_argument("-s", "--min-silence", type=int, default=DEFAULT_MIN_SILENCE_LEN,
                      help=f"最小静音长度(毫秒)，默认: {DEFAULT_MIN_SILENCE_LEN}ms")
    parser.add_argument("-t", "--silence-threshold", type=int, default=DEFAULT_SILENCE_THRESH,
                      help=f"静音阈值(dB)，默认: {DEFAULT_SILENCE_THRESH}dB")
    parser.add_argument("-m", "--max-length", type=int, default=DEFAULT_MAX_SEGMENT_LEN,
                      help=f"目标最大长度(毫秒)，默认: {DEFAULT_MAX_SEGMENT_LEN}ms (45秒)")
    parser.add_argument("--strict-max", type=int, default=DEFAULT_STRICT_MAX_LEN,
                      help=f"绝对最大长度限制(毫秒)，默认: {DEFAULT_STRICT_MAX_LEN}ms (60秒)")
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_SEGMENT_LEN,
                      help=f"每段最小长度(毫秒)，默认: {DEFAULT_MIN_SEGMENT_LEN}ms (10秒)")
    parser.add_argument("-p", "--pause-threshold", type=int, default=DEFAULT_PAUSE_THRESHOLD,
                      help=f"句子边界静音阈值(毫秒)，默认: {DEFAULT_PAUSE_THRESHOLD}ms")
    parser.add_argument("-w", "--search-window", type=int, default=DEFAULT_SEARCH_WINDOW,
                      help=f"搜索窗口大小(毫秒)，默认: {DEFAULT_SEARCH_WINDOW}ms")
    parser.add_argument("-d", "--debug", action="store_true",
                      help="启用调试模式，生成静音分布图等")
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    split_audio(
        input_file=args.input_file,
        output_dir=args.output_dir,
        min_silence_len=args.min_silence,
        silence_thresh=args.silence_threshold,
        max_segment_len=args.max_length,
        strict_max_len=args.strict_max,
        min_segment_len=args.min_length,
        pause_threshold=args.pause_threshold,
        search_window=args.search_window,
        debug=args.debug
    )
