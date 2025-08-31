import React, { useState, useCallback } from 'react';
import { Upload, message, Progress, Button, Spin } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { videoAPI } from '../services/api';

interface ReliableUploadProps {
  file: File;
  projectId: number;
  title?: string;
  description?: string;
  onProgress: (percent: number) => void;
  onComplete: (result: any) => void;
  onError: (error: string) => void;
  maxRetries?: number;
}

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB per chunk

const ReliableUpload: React.FC<ReliableUploadProps> = ({
  file,
  projectId,
  title,
  description,
  onProgress,
  onComplete,
  onError,
  maxRetries = 3
}) => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [videoId, setVideoId] = useState<number | null>(null);

  const uploadChunk = useCallback(async (chunk: Blob, chunkIndex: number, totalChunks: number) => {
    let retries = 0;
    
    while (retries <= maxRetries) {
      try {
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('chunkIndex', chunkIndex.toString());
        formData.append('totalChunks', totalChunks.toString());
        formData.append('fileName', file.name);
        formData.append('fileSize', file.size.toString());
        formData.append('project_id', projectId.toString());
        
        // 添加标题和描述（仅在第一个分块时）
        if (chunkIndex === 0) {
          formData.append('title', title || file.name);
          formData.append('description', description || '');
        }
        
        // 如果不是第一个分块，添加video_id
        if (chunkIndex > 0 && videoId) {
          formData.append('video_id', videoId.toString());
        }
        
        // 调用实际的分块上传API
        const response = await videoAPI.uploadChunk(formData);
        
        if (!response || !response.data) {
          throw new Error('服务器响应无效');
        }
        
        // 保存video_id用于后续分块
        if (response.data.video_id && !videoId) {
          setVideoId(response.data.video_id);
        }
        
        // 如果上传完成，返回完整响应
        if (response.data.completed) {
          return response.data;
        }
        
        return true;
      } catch (error: any) {
        retries++;
        if (retries > maxRetries) {
          throw error;
        }
        // 等待后重试
        await new Promise(resolve => setTimeout(resolve, 1000 * retries));
      }
    }
    
    return false;
  }, [file, projectId, title, description, videoId, maxRetries]);

  const startUpload = useCallback(async () => {
    if (uploading) return;
    
    setUploading(true);
    setProgress(0);
    setVideoId(null);
    
    try {
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      
      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);
        
        const result = await uploadChunk(chunk, i, totalChunks);
        
        const chunkProgress = Math.round(((i + 1) / totalChunks) * 100);
        setProgress(chunkProgress);
        onProgress(chunkProgress);
        
        // 如果返回了完整响应，说明上传已完成
        if (result && typeof result === 'object' && result.completed) {
          // 通知上传完成
          onComplete({
            success: true,
            fileName: file.name,
            fileSize: file.size,
            video: result.video,
            taskId: result.task_id
          });
          
          message.success('文件上传完成');
          setUploading(false);
          return;
        }
      }
      
    } catch (error: any) {
      const errorMsg = error.message || '上传失败';
      onError(errorMsg);
      message.error(`上传失败: ${errorMsg}`);
    } finally {
      setUploading(false);
    }
  }, [file, uploading, onProgress, onComplete, onError, uploadChunk]);

  if (uploading) {
    return (
      <div style={{ textAlign: 'center', padding: '20px' }}>
        <Spin size="large" />
        <div style={{ marginTop: '10px' }}>
          <Progress percent={progress} />
          <p>正在上传: {file.name}</p>
          <p>大小: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ textAlign: 'center', padding: '20px' }}>
      <p>文件: {file.name}</p>
      <p>大小: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
      <Button 
        type="primary" 
        icon={<UploadOutlined />}
        onClick={startUpload}
        disabled={uploading}
      >
        开始上传
      </Button>
    </div>
  );
};

export default ReliableUpload;