# Flowclip Whisper Large V3 集成指南

## 项目概述
本指南介绍如何在Flowclip项目中集成OpenAI Whisper Large V3模型，以提升自动语音识别(ASR)的准确性和多语言支持能力。

## 技术优势
- 支持99种语言
- 基于500万小时标注数据训练
- 零样本学习能力强
- 相比现有ASR模型性能更优

## 集成步骤

### 1. 环境准备
```bash
# 创建新项目目录
mkdir youtube-slicer-whisper
cd youtube-slicer-whisper

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装基础依赖
pip install torch>=1.13.0 transformers>=4.35.0 datasets>=2.14.0
pip install librosa soundfile numpy scipy
```

### 2. 核心依赖项
在requirements.txt中添加：
```txt
torch>=1.13.0
transformers>=4.35.0
datasets>=2.14.0
librosa>=0.10.1
soundfile>=0.12.1
numpy>=1.24.3
scipy>=1.11.4
```

### 3. Whisper模型集成代码
创建`whisper_asr.py`文件：

```python
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import librosa
import numpy as np
from typing import Dict, Any

class WhisperASR:
    def __init__(self, model_name: str = "openai/whisper-large-v3"):
        """
        初始化Whisper ASR模型
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = WhisperProcessor.from_pretrained(model_name)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_name).to(self.device)
        
    def transcribe_audio(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        """
        转录音频文件
        """
        # 加载音频
        audio, sampling_rate = librosa.load(audio_path, sr=16000)
        
        # 预处理音频
        input_features = self.processor(
            audio, 
            sampling_rate=sampling_rate, 
            return_tensors="pt"
        ).input_features.to(self.device)
        
        # 生成转录
        forced_decoder_ids = self.processor.get_decoder_prompt_ids(language=language, task="transcribe")
        predicted_ids = self.model.generate(input_features, forced_decoder_ids=forced_decoder_ids)
        
        # 解码结果
        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        
        return {
            "text": transcription[0],
            "language": language
        }
        
    def transcribe_with_timestamps(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        """
        带时间戳的转录
        """
        # 加载音频
        audio, sampling_rate = librosa.load(audio_path, sr=16000)
        
        # 预处理音频
        input_features = self.processor(
            audio, 
            sampling_rate=sampling_rate, 
            return_tensors="pt"
        ).input_features.to(self.device)
        
        # 生成带时间戳的转录
        forced_decoder_ids = self.processor.get_decoder_prompt_ids(language=language, task="transcribe")
        generated_ids = self.model.generate(
            input_features,
            forced_decoder_ids=forced_decoder_ids,
            return_timestamps=True
        )
        
        # 解码结果
        transcription = self.processor.batch_decode(generated_ids, decode_with_timestamps=True)
        
        return {
            "text_with_timestamps": transcription[0],
            "language": language
        }

# 使用示例
if __name__ == "__main__":
    # 初始化模型
    asr = WhisperASR()
    
    # 转录音频
    result = asr.transcribe_audio("path/to/audio.wav", language="zh")
    print(f"转录结果: {result['text']}")
```

### 4. 与现有Flowclip集成

#### 4.1 修改音频处理服务
在`youtube_downloader_minio.py`中集成Whisper：

```python
# 添加Whisper导入
from app.services.whisper_asr import WhisperASR

class YouTubeDownloaderMinio:
    def __init__(self, cookies_file: str = None):
        self.cookies_file = cookies_file
        self.whisper_asr = WhisperASR()  # 初始化Whisper模型
        
    async def generate_transcript_with_whisper(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        """
        使用Whisper生成转录
        """
        try:
            # 调用Whisper转录
            result = self.whisper_asr.transcribe_with_timestamps(audio_path, language)
            
            return {
                'success': True,
                'transcript': result['text_with_timestamps'],
                'language': result['language']
            }
        except Exception as e:
            raise Exception(f"Whisper转录失败: {str(e)}")
```

#### 4.2 API端点更新
在`app/api/v1/asr.py`中添加Whisper支持：

```python
from app.services.whisper_asr import WhisperASR

@router.post("/transcribe-whisper")
async def transcribe_with_whisper(
    audio_file: UploadFile = File(...),
    language: str = Query("zh", description="语言代码")
):
    """
    使用Whisper模型进行音频转录
    """
    try:
        # 保存上传的音频文件
        contents = await audio_file.read()
        temp_file = f"/tmp/{audio_file.filename}"
        with open(temp_file, "wb") as f:
            f.write(contents)
        
        # 初始化Whisper模型
        whisper_asr = WhisperASR()
        
        # 执行转录
        result = whisper_asr.transcribe_with_timestamps(temp_file, language)
        
        return {
            "success": True,
            "transcript": result["text_with_timestamps"],
            "language": result["language"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")
```

### 5. 性能优化建议

#### 5.1 模型加速选项
```python
# 使用Flash Attention 2加速
model = WhisperForConditionalGeneration.from_pretrained(
    model_name, 
    use_flash_attention_2=True
).to(device)

# 使用torch.compile优化
model = torch.compile(model)
```

#### 5.2 分块处理长音频
```python
def transcribe_long_audio(self, audio_path: str, chunk_length: int = 30) -> str:
    """
    分块处理长音频文件
    """
    audio, sr = librosa.load(audio_path, sr=16000)
    chunk_samples = chunk_length * sr
    
    transcriptions = []
    for i in range(0, len(audio), chunk_samples):
        chunk = audio[i:i + chunk_samples]
        # 处理音频块
        result = self.transcribe_audio_chunk(chunk, sr)
        transcriptions.append(result)
    
    return " ".join(transcriptions)
```

### 6. Docker配置优化

#### 6.1 更新Dockerfile
```dockerfile
# 添加CUDA支持（如果使用GPU）
FROM nvidia/cuda:11.8-devel-ubuntu20.04

# 安装Python和依赖
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 安装PyTorch和相关依赖
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装其他依赖
COPY requirements.txt .
RUN pip3 install -r requirements.txt
```

#### 6.2 GPU支持配置
在docker-compose.yml中添加GPU支持：
```yaml
services:
  whisper-asr:
    build: ./whisper-service
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 7. 测试验证

#### 7.1 基本功能测试
```python
def test_whisper_integration():
    """测试Whisper集成"""
    asr = WhisperASR()
    
    # 测试中文转录
    result = asr.transcribe_audio("test_chinese.wav", "zh")
    assert "success" in result
    assert len(result["text"]) > 0
    
    # 测试英文转录
    result = asr.transcribe_audio("test_english.wav", "en")
    assert "success" in result
```

#### 7.2 性能基准测试
```python
import time

def benchmark_whisper():
    """Whisper性能基准测试"""
    asr = WhisperASR()
    
    start_time = time.time()
    result = asr.transcribe_audio("test_audio.wav", "zh")
    end_time = time.time()
    
    print(f"转录耗时: {end_time - start_time:.2f}秒")
    print(f"音频长度: {get_audio_length('test_audio.wav'):.2f}秒")
    print(f"实时因子: {(end_time - start_time) / get_audio_length('test_audio.wav'):.2f}")
```

### 8. 部署建议

#### 8.1 模型缓存
```python
# 在应用启动时预加载模型
class ASRService:
    _instance = None
    _model = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._model = WhisperASR()
        return cls._instance
```

#### 8.2 负载均衡
```python
# 使用多个模型实例处理并发请求
class WhisperPool:
    def __init__(self, pool_size: int = 2):
        self.models = [WhisperASR() for _ in range(pool_size)]
        self.current = 0
        
    def get_model(self):
        model = self.models[self.current]
        self.current = (self.current + 1) % len(self.models)
        return model
```

## 注意事项

1. **硬件要求**：Whisper Large V3模型较大，建议使用GPU加速
2. **内存需求**：模型加载需要约6GB显存
3. **网络访问**：首次运行需要下载模型文件（约3GB）
4. **语言支持**：确保测试多种语言的转录效果
5. **错误处理**：添加适当的异常处理和重试机制

## 预期收益

1. **准确性提升**：相比现有ASR模型，Whisper在多种语言上准确率更高
2. **多语言支持**：支持99种语言，满足国际化需求
3. **零样本学习**：无需额外训练即可处理新领域内容
4. **时间戳支持**：提供精确的词级时间戳信息

这个集成方案可以帮助您充分利用Whisper Large V3的强大功能，提升Flowclip的ASR能力。