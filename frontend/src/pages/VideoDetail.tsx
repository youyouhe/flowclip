import React, { useState, useEffect, useRef } from 'react';
import { Card, Descriptions, Button, Space, message, Spin, Tag, Progress, Row, Col, Divider, Typography, Modal, Steps, Table, Popover } from 'antd';
import { PlayCircleOutlined, DownloadOutlined, ArrowLeftOutlined, SoundOutlined, ScissorOutlined, FileTextOutlined, LoadingOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { videoAPI } from '../services/api';
import { wsService, startHeartbeat, stopHeartbeat } from '../services/websocket';
import ReactPlayer from 'react-player';

import { TaskStatus, AudioInfo, SplitInfo, SrtInfo, ProcessingStatus, StageInfo } from '../types';

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;

interface Video {
  id: number;
  title: string;
  description?: string;
  url: string;
  project_id: number;
  filename?: string;
  duration?: number;
  file_size?: number;
  thumbnail_url?: string;
  status: string;
  download_progress: number;
  created_at: string;
  file_path?: string;
  processing_metadata?: any;
  processing_progress?: number;
  processing_stage?: string;
  processing_message?: string;
}

const VideoDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [video, setVideo] = useState<Video | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const playerRef = useRef<ReactPlayer>(null);
  const [useNativePlayer, setUseNativePlayer] = useState(false);
  
  // 新的状态管理
  const [processingModalVisible, setProcessingModalVisible] = useState(false);
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [processingStep, setProcessingStep] = useState(0);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingStatus, setProcessingStatus] = useState<'idle' | 'processing' | 'completed' | 'failed'>('idle');
  const [audioInfo, setAudioInfo] = useState<AudioInfo | null>(null);
  const [splitInfo, setSplitInfo] = useState<SplitInfo | null>(null);
  const [srtInfo, setSrtInfo] = useState<SrtInfo | null>(null);
  const [audioStatus, setAudioStatus] = useState<ProcessingStatus | null>(null);
  const [splitStatus, setSplitStatus] = useState<ProcessingStatus | null>(null);
  const [srtStatus, setSrtStatus] = useState<ProcessingStatus | null>(null);
  const [completionNotified, setCompletionNotified] = useState(false);
  const [processingStatusData, setProcessingStatusData] = useState<any>(null);
  
  // SRT字幕查看状态
  const [srtModalVisible, setSrtModalVisible] = useState(false);
  const [srtContent, setSrtContent] = useState<string>('');
  const [srtSubtitles, setSrtSubtitles] = useState<any[]>([]);
  const [srtLoading, setSrtLoading] = useState(false);

  // 从数据库获取准确的处理状态
  const fetchProcessingStatus = async () => {
    if (!id) return;
    
    try {
      const response = await videoAPI.getProcessingStatus(parseInt(id));
      const status = response.data;
      setProcessingStatusData(status);
      
      // 更新各个阶段的状态，获取详细信息
      if (status.extract_audio_status === 'completed' || status.extract_audio_status === 'success') {
        try {
          const audioResponse = await videoAPI.getAudioDownloadUrl(parseInt(id));
          setAudioStatus({
            status: 'completed',
            progress: status.extract_audio_progress,
            duration: audioResponse.data.duration || 0
          });
        } catch (error) {
          setAudioStatus({
            status: 'completed',
            progress: status.extract_audio_progress,
            duration: 0
          });
        }
      } else {
        setAudioStatus(null);
      }
      
      setSplitStatus((status.split_audio_status === 'completed' || status.split_audio_status === 'success') ? {
        status: 'completed',
        progress: status.split_audio_progress
      } : null);
      
      if (status.generate_srt_status === 'completed' || status.generate_srt_status === 'success') {
        try {
          // 获取SRT内容来获取条数
          const srtResponse = await videoAPI.getSrtContent(parseInt(id));
          setSrtStatus({
            status: 'completed',
            progress: status.generate_srt_progress,
            totalSegments: srtResponse.data.total_subtitles || 0
          });
        } catch (error) {
          setSrtStatus({
            status: 'completed',
            progress: status.generate_srt_progress,
            totalSegments: 0
          });
        }
      } else {
        setSrtStatus(null);
      }
      
      console.log('处理状态数据:', status);
    } catch (error) {
      console.error('获取处理状态失败:', error);
    }
  };

  // 获取当前阶段的中文描述
  const getCurrentStageText = (stage: string) => {
    const stageMap: Record<string, string> = {
      'download': '视频下载',
      'extract_audio': '音频提取',
      'split_audio': '音频分割',
      'generate_srt': '字幕生成',
      'completed': '已完成',
      'pending': '等待开始'
    };
    return stageMap[stage] || stage;
  };

  // 根据current_stage渲染当前处理状态
  const renderCurrentStageStatus = () => {
    if (!processingStatusData) return null;
    
    const { current_stage } = processingStatusData;
    
    if (!current_stage || current_stage === 'pending') {
      return (
        <div className="text-center p-4 text-gray-500">
          等待开始处理...
        </div>
      );
    }
    
    const getCurrentStageInfo = () => {
      switch (current_stage) {
        case 'download':
          return {
            label: '视频下载',
            status: processingStatusData.download_status,
            progress: processingStatusData.download_progress,
            color: processingStatusData.download_status === 'completed' ? 'green' : 'blue'
          };
        case 'extract_audio':
          return {
            label: '音频提取',
            status: processingStatusData.extract_audio_status,
            progress: processingStatusData.extract_audio_progress,
            color: processingStatusData.extract_audio_status === 'completed' ? 'green' : 'blue'
          };
        case 'split_audio':
          return {
            label: '音频分割',
            status: processingStatusData.split_audio_status,
            progress: processingStatusData.split_audio_progress,
            color: processingStatusData.split_audio_status === 'completed' ? 'green' : 'blue'
          };
        case 'generate_srt':
          return {
            label: '字幕生成',
            status: processingStatusData.generate_srt_status,
            progress: processingStatusData.generate_srt_progress,
            color: processingStatusData.generate_srt_status === 'completed' ? 'green' : 'blue'
          };
        case 'completed':
          return {
            label: '所有处理',
            status: 'completed',
            progress: 100,
            color: 'green'
          };
        default:
          return null;
      }
    };
    
    const stageInfo = getCurrentStageInfo();
    if (!stageInfo) return null;
    
    const statusText = {
      'pending': '待处理',
      'processing': '进行中',
      'completed': '已完成',
      'failed': '失败',
      'PENDING': '待处理',
      'RUNNING': '进行中',
      'SUCCESS': '已完成',
      'FAILURE': '失败',
      'COMPLETED': '已完成'
    };
    
    const processingText = {
      'download': '下载中',
      'extract_audio': '提取中',
      'split_audio': '分割中',
      'generate_srt': '生成中'
    };
    
    return (
      <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold text-blue-800">
            📍 当前阶段: {stageInfo.label}
          </div>
          <div>
            <Tag 
              color={stageInfo.color} 
              className="text-sm font-medium"
            >
              {stageInfo.status === 'completed' || stageInfo.status === 'SUCCESS' || stageInfo.status === 'COMPLETED' ? 
                '✅ 已完成' : 
                stageInfo.status === 'processing' || stageInfo.status === 'RUNNING' ? 
                '⏳ ' + (processingText as any)[current_stage] : 
                '⏸️ ' + ((statusText as any)[stageInfo.status] || stageInfo.status || '未知状态')}
            </Tag>
          </div>
        </div>
        
        <div className="flex items-center">
          <div className="flex-1 mr-3">
            <Progress 
              percent={Math.round(stageInfo.progress || 0)} 
              size="small" 
              strokeColor={stageInfo.color}
              showInfo 
            />
          </div>
          <div className="text-sm font-medium text-gray-600">
            {Math.round(stageInfo.progress || 0)}%
          </div>
        </div>
        
        {stageInfo.status === 'processing' && stageInfo.progress > 0 && (
          <div className="mt-2 text-xs text-gray-500 text-center">
            {current_stage === 'download' && '正在下载视频文件...'}
            {current_stage === 'extract_audio' && '正在从视频中提取音频...'}
            {current_stage === 'split_audio' && '正在根据静音分割音频...'}
            {current_stage === 'generate_srt' && '正在使用ASR生成字幕...'}
          </div>
        )}
      </div>
    );
  };

  // 从视频对象的processing_metadata中获取处理状态（向后兼容）
  const getProcessingStatusFromVideo = () => {
    if (processingStatusData) {
      return {
        hasAudio: processingStatusData.extract_audio_status === 'completed',
        hasSplits: processingStatusData.split_audio_status === 'completed',
        hasSrt: processingStatusData.generate_srt_status === 'completed',
        audioInfo: processingStatusData.extract_audio_status === 'completed' ? {
          status: processingStatusData.extract_audio_status,
          progress: processingStatusData.extract_audio_progress
        } : null,
        splitInfo: processingStatusData.split_audio_status === 'completed' ? {
          status: processingStatusData.split_audio_status,
          progress: processingStatusData.split_audio_progress
        } : null,
        srtInfo: processingStatusData.generate_srt_status === 'completed' ? {
          status: processingStatusData.generate_srt_status,
          progress: processingStatusData.generate_srt_progress
        } : null
      };
    }
    
    // 向后兼容：如果没有processingStatusData，使用旧的metadata
    if (!video?.processing_metadata) return {};
    
    const metadata = video.processing_metadata;
    return {
      hasAudio: metadata.audio_path || metadata.audio_info,
      hasSplits: metadata.split_files || metadata.split_info,
      hasSrt: metadata.srt_files || metadata.srt_info,
      audioInfo: metadata.audio_info,
      splitInfo: metadata.split_info,
      srtInfo: metadata.srt_info
    };
  };

  // 监听视频数据变化，更新处理状态
  useEffect(() => {
    if (video?.processing_metadata) {
      const status = getProcessingStatusFromVideo();
      setAudioInfo(status.audioInfo || null);
      setSplitInfo(status.splitInfo || null);
      setSrtInfo(status.srtInfo || null);
    }
  }, [video]);

  useEffect(() => {
    console.log('🔧 [VideoDetail] Component mounted with ID:', id);
    console.log('🔧 [VideoDetail] Current location:', window.location.href);
    console.log('🔧 [VideoDetail] User logged in:', !!localStorage.getItem('token'));
    
    fetchVideoDetail();
    fetchProcessingStatus();
    setupWebSocket();
    
    // 移除轮询定时器，使用WebSocket实时更新
    // 注意：WebSocket已经提供实时更新，不需要轮询
    
    return () => {
      // 清理WebSocket连接
      cleanupWebSocket();
    };
  }, [id]);

  // 当视频数据变化时，订阅WebSocket进度更新
  useEffect(() => {
    if (video && wsService.connected) {
      wsService.subscribeVideoProgress(video.id);
    }
  }, [video]);

  const setupWebSocket = () => {
    console.log('🔧 [VideoDetail] Setting up WebSocket...');
    
    const token = localStorage.getItem('token');
    console.log('🔧 [VideoDetail] Token from localStorage:', token ? `${token.substring(0, 20)}...` : 'null');
    
    if (!token) {
      console.log('❌ [VideoDetail] No token found, skipping WebSocket connection');
      return;
    }

    console.log('🔧 [VideoDetail] Connecting to WebSocket service...');
    
    // 连接WebSocket
    wsService.connect(token);
    startHeartbeat();
    console.log('🔧 [VideoDetail] WebSocket connection initiated, heartbeat started');

    // 监听WebSocket事件
    wsService.on('connected', () => {
      console.log('✅ [VideoDetail] WebSocket connected event received');
      console.log('📹 [VideoDetail] Current video data:', video);
      console.log('📹 [VideoDetail] Video ID from URL:', id);
      
      if (video) {
        console.log('📡 [VideoDetail] Subscribing to video progress for video ID:', video.id);
        wsService.subscribeVideoProgress(video.id);
      } else {
        console.log('⚠️ [VideoDetail] Video data not available yet, will subscribe when available');
      }
    });

    wsService.on('progress_update', (data: any) => {
      console.log('📊 [VideoDetail] Progress update received:', data);
      console.log('📊 [VideoDetail] Update video ID:', data.video_id);
      console.log('📊 [VideoDetail] Current page video ID:', id);
      
      if (data.video_id == id) {
        console.log('✅ [VideoDetail] Progress update matches current video, updating state...');
        console.log('📊 [VideoDetail] Before update - Video status:', video?.status);
        console.log('📊 [VideoDetail] Before update - Download progress:', video?.download_progress);
        
        // 更新视频状态
        setVideo(prev => {
          if (!prev) {
            console.log('⚠️ [VideoDetail] Previous video state is null');
            return null;
          }
          
          const updatedVideo = {
            ...prev,
            status: data.video_status || prev.status,
            download_progress: data.download_progress || prev.download_progress,
            processing_progress: data.processing_progress || prev.processing_progress,
            processing_stage: data.processing_stage || prev.processing_stage,
            processing_message: data.processing_message || prev.processing_message
          };
          
          console.log('📊 [VideoDetail] Video state updated:');
          console.log('   - Status:', updatedVideo.status);
          console.log('   - Download progress:', updatedVideo.download_progress);
          console.log('   - Processing progress:', updatedVideo.processing_progress);
          console.log('   - Processing stage:', updatedVideo.processing_stage);
          
          return updatedVideo;
        });

        // 如果有处理任务，也更新处理进度
        if (data.tasks && data.tasks.length > 0) {
          console.log('🔄 [VideoDetail] Processing tasks found:', data.tasks.length);
          const latestTask = data.tasks[0];
          console.log('🔄 [VideoDetail] Latest task:', latestTask);
          
          if (latestTask.status === 'running' || latestTask.status === 'success') {
            console.log('🔄 [VideoDetail] Updating processing progress...');
            setProcessingProgress(latestTask.progress || 0);
            
            // 更新处理步骤
            const stepMap: Record<string, number> = {
              'extract_audio': 0,
              'split_audio': 1,
              'generate_srt': 2,
              'completed': 3
            };
            const newStep = stepMap[latestTask.stage] || 0;
            console.log('🔄 [VideoDetail] Updating processing step from', processingStep, 'to', newStep);
            setProcessingStep(newStep);
            
            // 更新处理状态
            if (latestTask.status === 'success' && !completionNotified) {
              console.log('✅ [VideoDetail] Processing completed!');
              setProcessingStatus('completed');
              setProcessingProgress(100);
              setCompletionNotified(true);
              message.success('处理完成！');
              
              // 3秒后自动关闭模态框
              setTimeout(() => {
                setProcessingModalVisible(false);
              }, 3000);
            }
          }
        } else {
          console.log('📊 [VideoDetail] No processing tasks in update');
        }
      } else {
        console.log('⚠️ [VideoDetail] Progress update video ID does not match current video');
        console.log('   - Update video ID:', data.video_id);
        console.log('   - Current video ID:', id);
      }
    });

    wsService.on('disconnected', () => {
      console.log('🔌 [VideoDetail] WebSocket disconnected event received');
    });

    wsService.on('error', (error: any) => {
      console.error('❌ [VideoDetail] WebSocket error event received:', error);
    });

    wsService.on('pong', (data: any) => {
      console.log('💓 [VideoDetail] Pong response received:', data);
    });
  };

  const cleanupWebSocket = () => {
    console.log('🧹 [VideoDetail] Cleaning up WebSocket connection...');
    stopHeartbeat();
    wsService.disconnect();
    console.log('🧹 [VideoDetail] WebSocket cleanup completed');
  };

  const fetchVideoDetail = async () => {
    if (!id) return;
    
    try {
      setLoading(true);
      const response = await videoAPI.getVideo(parseInt(id));
      setVideo(response.data);
      
      // 如果视频已完成，获取播放URL
      if (response.data.status === 'completed' && response.data.file_path) {
        await fetchVideoUrl();
      }
      
      // 调试：打印处理元数据
      console.log('视频处理元数据:', response.data.processing_metadata);
    } catch (error) {
      message.error('获取视频详情失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchVideoUrl = async () => {
    try {
      // 获取当前用户的token
      const token = localStorage.getItem('token');
      if (!token) {
        message.error('请先登录');
        return;
      }
      
      // 使用新的流式传输端点，避免CORS和403问题
      const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://192.168.8.107:8001';
      const streamUrl = `${apiBaseUrl}/api/v1/videos/${id}/stream?token=${token}`;
      
      console.log('设置流式播放URL:', streamUrl);
      setVideoUrl(streamUrl);
      
      // 为了调试，也获取原始下载URL
      const downloadResponse = await videoAPI.getVideoDownloadUrl(parseInt(id!), 3600);
      console.log('MinIO下载URL:', downloadResponse.data.download_url);
      console.log('对象名称:', downloadResponse.data.object_name);
      
    } catch (error) {
      console.error('获取视频URL失败:', error);
      message.error('无法获取视频播放地址，请稍后重试');
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      pending: 'orange',
      downloading: 'blue',
      processing: 'cyan',
      completed: 'green',
      failed: 'red',
    };
    return colorMap[status] || 'default';
  };

  const getStatusText = (status: string) => {
    const textMap: Record<string, string> = {
      pending: '等待中',
      downloading: '下载中',
      processing: '处理中',
      completed: '已完成',
      failed: '失败',
    };
    return textMap[status] || status;
  };

  const handleDownloadVideo = async () => {
    if (!video) return;
    
    try {
      setDownloading(true);
      const response = await videoAPI.getVideoDownloadUrl(video.id, 3600);
      const url = response.data.download_url;
      
      // 创建下载链接
      const link = document.createElement('a');
      link.href = url;
      link.download = video.filename || `${video.title}.mp4`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      message.success('开始下载视频');
    } catch (error) {
      message.error('获取下载链接失败');
    } finally {
      setDownloading(false);
    }
  };

  
  const handleExtractAudio = async () => {
    if (!video) return;
    
    try {
      setProcessingModalVisible(true);
      setProcessingStatus('processing');
      setProcessingStep(0);
      setProcessingProgress(0);
      setCompletionNotified(false);
      
      const response = await videoAPI.extractAudio(video.id);
      setCurrentTask(response.data);
      console.log('提取音频响应:', response.data);
      
      // 修复：使用正确的task_id字段名
      const taskId = response.data.task_id;
      if (!taskId || taskId === 'undefined') {
        console.error('task_id无效:', taskId);
        message.error('获取任务ID失败');
        setProcessingModalVisible(false);
        return;
      }
      
      console.log('任务已启动，等待WebSocket更新，taskId:', taskId);
      // 移除轮询，使用WebSocket实时更新
      // pollTaskStatus(taskId);
      message.success('音频提取任务已启动');
    } catch (error) {
      console.error('启动音频提取失败:', error);
      message.error('启动音频提取失败');
      setProcessingModalVisible(false);
    }
  };

  const handleSplitAudio = async () => {
    if (!video) return;
    
    try {
      setProcessingModalVisible(true);
      setProcessingStatus('processing');
      setProcessingStep(1);
      setProcessingProgress(0);
      setCompletionNotified(false);
      
      const response = await videoAPI.splitAudio(video.id);
      setCurrentTask(response.data);
      console.log('分割音频响应:', response.data);
      
      // 修复：使用正确的task_id字段名
      const taskId = response.data.task_id;
      if (!taskId || taskId === 'undefined') {
        console.error('task_id无效:', taskId);
        message.error('获取任务ID失败');
        setProcessingModalVisible(false);
        return;
      }
      
      console.log('任务已启动，等待WebSocket更新，taskId:', taskId);
      // 移除轮询，使用WebSocket实时更新
      // pollTaskStatus(taskId);
      message.success('音频分割任务已启动');
    } catch (error) {
      console.error('启动音频分割失败:', error);
      message.error('启动音频分割失败');
      setProcessingModalVisible(false);
    }
  };

  const handleGenerateSrt = async () => {
    if (!video) return;
    
    try {
      setProcessingModalVisible(true);
      setProcessingStatus('processing');
      setProcessingStep(2);
      setProcessingProgress(0);
      setCompletionNotified(false);
      
      // 首先获取分割文件信息，如果没有则使用空数组
      let splitFiles = [];
      try {
        // 尝试从视频的处理元数据中获取分割文件信息
        const videoResponse = await videoAPI.getVideo(video.id);
        if (videoResponse.data.processing_metadata && videoResponse.data.processing_metadata.split_files) {
          splitFiles = videoResponse.data.processing_metadata.split_files;
        }
      } catch (e) {
        console.log('无法获取分割文件信息，使用空数组');
      }
      
      const response = await videoAPI.generateSrt(video.id, splitFiles);
      setCurrentTask(response.data);
      console.log('生成SRT响应:', response.data);
      
      // 修复：使用正确的task_id字段名
      const taskId = response.data.task_id;
      if (!taskId || taskId === 'undefined') {
        console.error('task_id无效:', taskId);
        message.error('获取任务ID失败');
        setProcessingModalVisible(false);
        return;
      }
      
      console.log('任务已启动，等待WebSocket更新，taskId:', taskId);
      // 移除轮询，使用WebSocket实时更新
      // pollTaskStatus(taskId);
      message.success('SRT生成任务已启动');
    } catch (error) {
      console.error('启动SRT生成失败:', error);
      message.error('启动SRT生成失败');
      setProcessingModalVisible(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    if (!video) return;
    
    console.log('开始轮询任务状态 - videoId:', video.id, 'taskId:', taskId);
    
    const pollInterval = setInterval(async () => {
      try {
        console.log('查询任务状态 - videoId:', video.id, 'taskId:', taskId);
        const response = await videoAPI.getTaskStatus(video.id, taskId);
        const taskStatus = response.data;
        console.log('任务状态响应:', taskStatus);
        setCurrentTask(taskStatus);
        
        // 更新进度
        if (taskStatus.progress !== undefined) {
          setProcessingProgress(taskStatus.progress);
        }
        
        // 更新步骤
        if (taskStatus.step) {
          const stepMap: Record<string, number> = {
            'extract_audio': 0,
            'split_audio': 1,
            'generate_srt': 2,
            'completed': 3
          };
          setProcessingStep(stepMap[taskStatus.step] || 0);
        }
        
        // 检查任务是否完成
        if (taskStatus.status === 'SUCCESS' || taskStatus.status === 'completed') {
          clearInterval(pollInterval);
          setProcessingStatus('completed');
          setProcessingProgress(100);
          
          // 更新相应的信息
          if (taskStatus.result) {
            if (taskStatus.result.audio_info) {
              setAudioInfo(taskStatus.result.audio_info);
            }
            if (taskStatus.result.split_info) {
              setSplitInfo(taskStatus.result.split_info);
            }
            if (taskStatus.result.srt_info) {
              setSrtInfo(taskStatus.result.srt_info);
            }
          }
          
          message.success('处理完成！');
          
          // 3秒后自动关闭模态框
          setTimeout(() => {
            setProcessingModalVisible(false);
          }, 3000);
          
          // 刷新处理状态
          setTimeout(() => {
            fetchProcessingStatus();
          }, 1000);
          
        } else if (taskStatus.status === 'FAILURE' || taskStatus.status === 'failed') {
          clearInterval(pollInterval);
          setProcessingStatus('failed');
          message.error('处理失败：' + (taskStatus.error || '未知错误'));
          
          // 刷新处理状态
          setTimeout(() => {
            fetchProcessingStatus();
          }, 1000);
        }
      } catch (error) {
        console.error('获取任务状态失败:', error);
      }
    }, 2000);
  };

  const handleDownloadAudio = async () => {
    if (!video) return;
    
    try {
      const response = await videoAPI.getAudioDownloadUrl(video.id);
      const url = response.data.download_url;
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `${video.title}_audio.wav`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      message.success('开始下载音频');
    } catch (error) {
      message.error('获取音频下载链接失败');
    }
  };

  const handleDownloadSrt = async () => {
    if (!video) return;
    
    try {
      // 直接使用新的后端代理端点下载SRT，避免MinIO编码问题
      const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://192.168.8.107:8001';
      const token = localStorage.getItem('token');
      
      if (!token) {
        message.error('请先登录');
        return;
      }
      
      // 构建直接下载URL
      const downloadUrl = `${apiBaseUrl}/api/v1/videos/${video.id}/srt-download`;
      
      // 创建带认证头的下载链接
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${video.title}.srt`;
      
      // 添加认证头
      link.onclick = function() {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', downloadUrl, true);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.responseType = 'blob';
        
        xhr.onload = function() {
          if (xhr.status === 200) {
            const blob = new Blob([xhr.response], { type: 'text/plain; charset=utf-8' });
            const url = window.URL.createObjectURL(blob);
            const downloadLink = document.createElement('a');
            downloadLink.href = url;
            downloadLink.download = `${video.title}.srt`;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(downloadLink);
            message.success('SRT字幕下载成功');
          } else {
            message.error('SRT字幕下载失败');
          }
        };
        
        xhr.onerror = function() {
          message.error('SRT字幕下载失败');
        };
        
        xhr.send();
      };
      
      // 直接触发点击（简化版本）
      const xhr = new XMLHttpRequest();
      xhr.open('GET', downloadUrl, true);
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.responseType = 'blob';
      
      xhr.onload = function() {
        if (xhr.status === 200) {
          const blob = new Blob([xhr.response], { type: 'text/plain; charset=utf-8' });
          const url = window.URL.createObjectURL(blob);
          const downloadLink = document.createElement('a');
          downloadLink.href = url;
          downloadLink.download = `${video.title}.srt`;
          document.body.appendChild(downloadLink);
          downloadLink.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(downloadLink);
          message.success('SRT字幕下载成功');
        } else {
          message.error('SRT字幕下载失败');
        }
      };
      
      xhr.onerror = function() {
        message.error('SRT字幕下载失败');
      };
      
      xhr.send();
      
    } catch (error) {
      console.error('SRT下载错误:', error);
      message.error('获取SRT下载链接失败');
    }
  };

  const handleViewSrt = async () => {
    if (!video) return;
    
    try {
      setSrtLoading(true);
      setSrtModalVisible(true);
      
      const response = await videoAPI.getSrtContent(video.id);
      setSrtContent(response.data.content);
      setSrtSubtitles(response.data.subtitles);
      
      message.success('SRT字幕加载成功');
    } catch (error) {
      message.error('获取SRT字幕内容失败');
      setSrtModalVisible(false);
    } finally {
      setSrtLoading(false);
    }
  };


  const renderSrtModal = () => {
    const srtColumns = [
      {
        title: '序号',
        dataIndex: 'id',
        key: 'id',
        width: 60,
      },
      {
        title: '时间轴',
        dataIndex: 'time',
        key: 'time',
        width: 200,
      },
      {
        title: '字幕内容',
        dataIndex: 'text',
        key: 'text',
        render: (text: string) => (
          <div style={{ whiteSpace: 'pre-wrap', maxWidth: 400 }}>{text}</div>
        ),
      },
    ];

    return (
      <Modal
        title="SRT字幕预览"
        open={srtModalVisible}
        onCancel={() => setSrtModalVisible(false)}
        width={800}
        footer={[
          <Button key="download" type="primary" onClick={handleDownloadSrt}>
            <DownloadOutlined /> 下载SRT文件
          </Button>,
          <Button key="close" onClick={() => setSrtModalVisible(false)}>关闭</Button>,
        ]}
      >
        <div className="p-4" style={{ maxHeight: 600, overflow: 'auto' }}>
          {srtLoading ? (
            <div className="flex items-center justify-center h-64">
              <Spin size="large" />
              <Text className="ml-4">加载字幕中...</Text>
            </div>
          ) : (
            <div>
              <div className="mb-4 flex justify-between items-center">
                <Text>总字幕数: {srtSubtitles.length} 条</Text>
                <Text type="secondary">文件大小: {(srtContent.length / 1024).toFixed(1)} KB</Text>
              </div>
              
              <Table
                dataSource={srtSubtitles}
                columns={srtColumns}
                pagination={{
                  pageSize: 10,
                  showTotal: (total) => `共 ${total} 条字幕`,
                }}
                rowKey="id"
                size="small"
                bordered
              />
              
              <Divider>原始SRT内容</Divider>
              <Card size="small" className="mt-4">
                <pre style={{ 
                  whiteSpace: 'pre-wrap', 
                  wordBreak: 'break-all',
                  maxHeight: 300,
                  overflow: 'auto',
                  fontSize: '12px',
                  margin: 0
                }}>{srtContent}</pre>
              </Card>
            </div>
          )}
        </div>
      </Modal>
    );
  };

  const renderProcessingModal = () => {
    return (
      <Modal
        title="视频处理进度"
        open={processingModalVisible}
        onCancel={() => setProcessingModalVisible(false)}
        footer={null}
        width={600}
      >
        <div className="p-4">
          <Steps
            current={processingStep}
            status={processingStatus === 'failed' ? 'error' : 'process'}
            className="mb-6"
          >
            <Step title="提取音频" description="从视频中提取音频文件" />
            <Step title="分割音频" description="根据静音智能分割音频" />
            <Step title="生成字幕" description="使用ASR生成SRT字幕" />
            <Step title="完成" description="所有处理步骤完成" />
          </Steps>
          
          <div className="text-center mb-4">
            {processingStatus === 'processing' && (
              <>
                <LoadingOutlined className="text-2xl text-blue-500 mb-2" />
                <div className="text-lg font-semibold">
                  {processingStep === 0 && '正在提取音频...'}
                  {processingStep === 1 && '正在分割音频...'}
                  {processingStep === 2 && '正在生成字幕...'}
                </div>
              </>
            )}
            {processingStatus === 'completed' && (
              <>
                <div className="text-2xl text-green-500 mb-2">✓</div>
                <div className="text-lg font-semibold text-green-600">处理完成！</div>
              </>
            )}
            {processingStatus === 'failed' && (
              <>
                <div className="text-2xl text-red-500 mb-2">✗</div>
                <div className="text-lg font-semibold text-red-600">处理失败</div>
              </>
            )}
          </div>
          
          <Progress
            percent={processingProgress}
            status={processingStatus === 'failed' ? 'exception' : 'active'}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
            className="mb-4"
          />
          
          {currentTask && (
            <div className="text-sm text-gray-600 text-center">
              任务ID: {currentTask.task_id || currentTask.taskId}
            </div>
          )}
          
          {(audioInfo || splitInfo || srtInfo) && (
            <div className="mt-4 p-3 bg-gray-50 rounded">
              <h4 className="font-semibold mb-2">处理结果:</h4>
              {audioInfo && (
                <div className="text-sm mb-1">
                  ✓ 音频提取完成: {audioInfo.audioFilename} ({Math.round(audioInfo.duration)}秒)
                </div>
              )}
              {splitInfo && (
                <div className="text-sm mb-1">
                  ✓ 音频分割完成: {splitInfo.totalSegments} 个片段
                </div>
              )}
              {srtInfo && (
                <div className="text-sm mb-1">
                  ✓ 字幕生成完成: {srtInfo.totalSegments} 条字幕
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    );
  };

  const renderVideoPlayer = () => {
    if (!video) return null;

    if (video.status !== 'completed') {
      return (
        <div className="flex flex-col items-center justify-center h-96 bg-gray-100 rounded-lg">
          {video.status === 'downloading' ? (
            <>
              <Progress
                type="circle"
                percent={Math.round(video.download_progress)}
                size={120}
                strokeColor={getStatusColor(video.status)}
              />
              <Text className="mt-4 text-lg">
                正在下载... {Math.round(video.download_progress)}%
              </Text>
            </>
          ) : (
            <>
              <PlayCircleOutlined 
                style={{ fontSize: 64, color: '#d9d9d9' }} 
              />
              <Text className="mt-4 text-lg">
                视频{getStatusText(video.status)}
              </Text>
            </>
          )}
        </div>
      );
    }

    if (!videoUrl) {
      return (
        <div className="flex items-center justify-center h-96 bg-gray-100 rounded-lg">
          <Spin size="large" />
          <Text className="ml-4">加载视频中...</Text>
        </div>
      );
    }

    if (useNativePlayer) {
      return (
        <div className="video-player-container">
          <video
            src={videoUrl}
            controls
            width="100%"
            height="600px"
            style={{ maxWidth: '100%', height: 'auto' }}
            onLoadedData={() => console.log('原生视频播放器加载成功')}
            onError={(e) => {
              console.error('原生视频播放器错误:', e);
              message.error('视频加载失败，可能是格式不支持或网络问题');
            }}
          >
            您的浏览器不支持视频播放。
          </video>
        </div>
      );
    }

    return (
      <div className="video-player-container">
        <ReactPlayer
          ref={playerRef}
          url={videoUrl}
          width="100%"
          height="600px"
          controls={true}
          playing={false}
          light={false}
          pip={false}
          config={{
            file: {
              forceVideo: true,
              attributes: {
                controlsList: 'nodownload',
                preload: 'metadata',
                crossOrigin: 'anonymous',
              }
            }
          }}
          onReady={() => console.log('视频播放器准备就绪')}
          onStart={() => console.log('视频开始播放')}
          onError={(error) => {
            console.error('视频播放错误:', error);
            message.error('ReactPlayer加载失败，尝试使用原生播放器');
            setUseNativePlayer(true);
          }}
          onProgress={({ played }) => setProgress(played * 100)}
        />
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  if (!video) {
    return (
      <div className="text-center py-12">
        <Title level={3}>视频不存在</Title>
        <Button type="primary" onClick={() => navigate('/dashboard/videos')}>
          返回视频列表
        </Button>
      </div>
    );
  }

  return (
    <div className="video-detail">
      <div className="mb-6">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/dashboard/videos')}
          className="mb-4"
        >
          返回视频列表
        </Button>
        <Title level={2}>{video.title}</Title>
      </div>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card className="mb-6">
            {renderVideoPlayer()}
          </Card>

          {video.description && (
            <Card title="视频描述" className="mb-6">
              <Paragraph
                ellipsis={{
                  rows: 4,
                  expandable: true,
                  symbol: '展开',
                }}
              >
                {video.description}
              </Paragraph>
            </Card>
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card title="视频信息" className="mb-6">
            <Descriptions column={1} layout="horizontal">
              <Descriptions.Item label="状态">
                <Tag color={getStatusColor(video.status)}>
                  {getStatusText(video.status)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="时长">
                {formatDuration(video.duration)}
              </Descriptions.Item>
              <Descriptions.Item label="文件大小">
                {formatFileSize(video.file_size)}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(video.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label="项目ID">
                {video.project_id}
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <Space direction="vertical" className="w-full">
              {video.status === 'completed' && (
                <>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => playerRef.current?.getInternalPlayer()?.play()}
                    block
                  >
                    播放视频
                  </Button>
                  <Button
                    type="default"
                    icon={<DownloadOutlined />}
                    onClick={handleDownloadVideo}
                    loading={downloading}
                    block
                  >
                    下载视频
                  </Button>
                  
                  <Divider orientation="left">音频处理</Divider>
                  <Button
                    type={audioInfo ? "default" : "primary"}
                    icon={<SoundOutlined />}
                    onClick={handleExtractAudio}
                    block
                    disabled={audioInfo ? true : false}
                  >
                    提取音频 {audioInfo && "✓"}
                  </Button>
                  <Button
                    type={splitInfo ? "default" : (audioInfo ? "primary" : "default")}
                    icon={<ScissorOutlined />}
                    onClick={handleSplitAudio}
                    block
                    disabled={!audioInfo || splitInfo ? true : false}
                  >
                    分割音频 {splitInfo && "✓"}
                  </Button>
                  <Button
                    type={srtInfo ? "default" : (splitInfo ? "primary" : "default")}
                    icon={<FileTextOutlined />}
                    onClick={handleGenerateSrt}
                    block
                    disabled={!splitInfo || srtInfo ? true : false}
                  >
                    生成字幕 {srtInfo && "✓"}
                  </Button>
                  
                    
                  {(audioInfo || splitInfo || srtInfo) && (
                    <>
                      <Divider orientation="left">下载处理结果</Divider>
                      {audioInfo && (
                        <Button
                          type="link"
                          icon={<SoundOutlined />}
                          onClick={handleDownloadAudio}
                          block
                        >
                          下载音频文件 ({Math.round(audioInfo.duration)}秒)
                        </Button>
                      )}
                      {srtInfo && (
                        <>
                          <Button
                            type="primary"
                            icon={<EyeOutlined />}
                            onClick={handleViewSrt}
                            block
                            className="mb-2"
                          >
                            查看SRT字幕 ({srtInfo.totalSegments}条)
                          </Button>
                          <Button
                            type="link"
                            icon={<DownloadOutlined />}
                            onClick={handleDownloadSrt}
                            block
                          >
                            下载SRT字幕
                          </Button>
                        </>
                      )}
                    </>
                  )}
                  
                  <Button
                    type="dashed"
                    onClick={() => {
                      if (videoUrl) {
                        console.log('测试访问视频URL:', videoUrl);
                        // 在新标签页打开测试
                        window.open(videoUrl, '_blank');
                      }
                    }}
                    block
                  >
                    测试视频链接
                  </Button>
                </>
              )}
            </Space>
          </Card>

          <Card title="处理状态" extra={
            <Button 
              type="text" 
              size="small"
              onClick={fetchProcessingStatus}
              icon={<ReloadOutlined />}
            >
              刷新
            </Button>
          }>
            {processingStatusData && (
              <div className="mb-4 p-2 bg-gray-50 rounded">
                <div className="text-sm text-gray-600">
                  当前阶段: <strong>{getCurrentStageText(processingStatusData.current_stage)}</strong>
                </div>
                <div className="text-sm text-gray-600">
                  整体进度: <strong>{Math.round(processingStatusData.overall_progress || 0)}%</strong>
                </div>
              </div>
            )}
            
            {processingStatusData && (
              <div className="mb-4">
                {renderCurrentStageStatus()}
              </div>
            )}
            
            {processingStatusData?.updated_at && (
              <div className="mt-2 text-xs text-gray-500">
                最后更新: {new Date(processingStatusData.updated_at).toLocaleString('zh-CN')}
              </div>
            )}
          </Card>

          <Card title="原始信息">
            <Descriptions column={1} layout="horizontal" size="small">
              <Descriptions.Item label="视频ID">
                <Text copyable>{video.id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="原始URL">
                <Text copyable ellipsis>
                  {video.url}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="文件名">
                {video.filename || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="存储路径">
                <Text copyable ellipsis>
                  {video.file_path || '无'}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="视频URL">
                <Text copyable ellipsis>
                  {videoUrl || '未获取'}
                </Text>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
      
      {/* 处理进度模态框 */}
      {renderProcessingModal()}
      
      {/* SRT字幕预览模态框 */}
      {renderSrtModal()}
    </div>
  );
};

export default VideoDetail;