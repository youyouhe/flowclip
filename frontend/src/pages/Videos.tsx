import React, { useState, useEffect, useRef } from 'react';
import { 
  Table, 
  Button, 
  Card, 
  Space, 
  Modal, 
  Form, 
  Input, 
  Select, 
  message, 
  Tag, 
  Progress, 
  Popconfirm, 
  Upload, 
  Row, 
  Col,
  DatePicker,
  InputNumber,
  Image
} from 'antd';
import { 
  PlusOutlined, 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  DeleteOutlined, 
  DownloadOutlined, 
  UploadOutlined,
  SearchOutlined,
  FilterOutlined,
  ClearOutlined,
  ReloadOutlined,
  PictureOutlined 
} from '@ant-design/icons';
import { videoAPI, projectAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { wsService, startHeartbeat, stopHeartbeat } from '../services/websocket';
import { useThumbnail } from '../hooks/useThumbnail';
import dayjs from 'dayjs';

interface Video {
  id: number;
  title: string;
  url: string;
  project_id: number;
  filename?: string;
  duration?: number;
  file_size?: number;
  thumbnail_url?: string;
  thumbnail_path?: string;  // 新增字段
  status: string;
  download_progress: number;
  processing_progress?: number; // Add this
  processing_stage?: string;    // Add this
  processing_message?: string;  // Add this
  created_at: string;
  project_name?: string;
}

interface Project {
  id: number;
  name: string;
}

const extractYouTubeVideoId = (url: string): string | null => {
  const regex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([^&\n?#]+)/;
  const match = url.match(regex);
  return match ? match[1] : null;
};

interface ThumbnailRendererProps {
  video: Video;
  title: string;
}

const ThumbnailRenderer: React.FC<ThumbnailRendererProps> = ({ video, title }) => {
  const { thumbnailUrl, loading, error } = useThumbnail(video);
  const [imgError, setImgError] = useState(false);

  const handleImageError = () => {
    console.warn(`Thumbnail failed to load for video ${video.id}: ${thumbnailUrl}`);
    setImgError(true);
  };

  const handleRetry = () => {
    // 重新加载页面以重新获取缩略图
    window.location.reload();
  };

  const getThumbnailSrc = () => {
    if (imgError || !thumbnailUrl) {
      // 如果图片加载失败或没有缩略图URL，使用默认的YouTube缩略图
      const youtubeVideoId = extractYouTubeVideoId(video.url);
      return youtubeVideoId ? `https://img.youtube.com/vi/${youtubeVideoId}/default.jpg` : null;
    }
    return thumbnailUrl;
  };

  const thumbnailSrc = getThumbnailSrc();

  if (!thumbnailSrc) {
    return (
      <div className="w-16 h-9 bg-gray-200 rounded mr-2 flex items-center justify-center">
        <PictureOutlined className="text-gray-400" />
      </div>
    );
  }

  return (
    <div className="relative">
      <Image
        src={thumbnailSrc}
        alt={title}
        className="w-16 h-9 object-cover rounded mr-2"
        preview={false}
        onError={handleImageError}
        placeholder={
          <div className="w-16 h-9 bg-gray-200 rounded mr-2 flex items-center justify-center">
            <PictureOutlined className="text-gray-400" />
          </div>
        }
      />
      {imgError && (
        <div className="absolute inset-0 bg-black bg-opacity-50 rounded mr-2 flex items-center justify-center">
          <Button
            type="text"
            size="small"
            icon={<PictureOutlined />}
            onClick={handleRetry}
            loading={loading}
            className="text-white hover:text-white"
          />
        </div>
      )}
    </div>
  );
};

const Videos: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const videosRef = useRef(videos); // Create a ref to hold the latest videos state
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [thumbnailUrls, setThumbnailUrls] = useState<{[key: number]: string}>({});
  const [form] = Form.useForm();
  const navigate = useNavigate();
  
  // 筛选状态
  const [filters, setFilters] = useState({
    project_id: undefined as number | undefined,
    status: undefined as string | undefined,
    search: '',
    start_date: undefined as string | undefined,
    end_date: undefined as string | undefined,
    min_duration: undefined as number | undefined,
    max_duration: undefined as number | undefined,
    min_file_size: undefined as number | undefined,
    max_file_size: undefined as number | undefined,
    page: 1,
    page_size: 10
  });
  
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: 10,
    total_pages: 0
  });

  const fetchVideos = async () => {
    setLoading(true);
    try {
      // 构建查询参数
      const params: any = {};
      if (filters.project_id) params.project_id = filters.project_id;
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.min_duration !== undefined) params.min_duration = filters.min_duration;
      if (filters.max_duration !== undefined) params.max_duration = filters.max_duration;
      if (filters.min_file_size !== undefined) params.min_file_size = filters.min_file_size;
      if (filters.max_file_size !== undefined) params.max_file_size = filters.max_file_size;
      if (filters.page) params.page = filters.page;
      if (filters.page_size) params.page_size = filters.page_size;
      
      const response = await videoAPI.getVideos(params);
      setVideos(response.data.videos || response.data);
      
      // 更新分页信息
      if (response.data.pagination) {
        setPagination(response.data.pagination);
      } else {
        setPagination({
          total: response.data.length || 0,
          page: filters.page,
          page_size: filters.page_size,
          total_pages: Math.ceil((response.data.length || 0) / filters.page_size)
        });
      }
      
      // 获取每个视频的缩略图URL
      const videoData = response.data.videos || response.data;
      const thumbnailPromises = videoData.map(async (video: Video) => {
        // 首先尝试使用新的缩略图路径生成URL
        if (video.thumbnail_path) {
          try {
            const thumbnailResponse = await resourceAPI.getThumbnailUrlByPath(video.thumbnail_path);
            return { id: video.id, url: thumbnailResponse.data.download_url };
          } catch (error) {
            console.error(`通过路径获取视频 ${video.id} 缩略图失败:`, error);
          }
        }
        
        // 如果没有thumbnail_path或获取失败，尝试使用旧的thumbnail_url
        if (video.thumbnail_url) {
          try {
            const thumbnailResponse = await videoAPI.getThumbnailDownloadUrl(video.id);
            return { id: video.id, url: thumbnailResponse.data.download_url };
          } catch (error) {
            console.error(`获取视频 ${video.id} 缩略图失败:`, error);
          }
        }
        
        // 如果都没有，生成一个默认的YouTube缩略图URL作为备用
        const youtubeVideoId = extractYouTubeVideoId(video.url);
        const fallbackUrl = youtubeVideoId ? `https://img.youtube.com/vi/${youtubeVideoId}/default.jpg` : null;
        return { id: video.id, url: fallbackUrl };
      });
      
      const thumbnailResults = await Promise.all(thumbnailPromises);
      const urlMap: {[key: number]: string} = {};
      thumbnailResults.forEach(result => {
        if (result.url) {
          urlMap[result.id] = result.url;
        }
      });
      setThumbnailUrls(urlMap);
    } catch (error) {
      message.error('获取视频列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchProjects = async () => {
    try {
      const response = await projectAPI.getProjects();
      setProjects(response.data);
    } catch (error) {
      message.error('获取项目列表失败');
    }
  };

  useEffect(() => {
    console.log('📋 [Videos] Component mounted');
    fetchVideos();
    fetchProjects();
    setupWebSocket();
    
    // 启动定时请求状态更新
    const statusUpdateInterval = setInterval(() => {
      if (wsService.connected) {
        wsService.requestStatusUpdate();
      }
    }, 15000); // 每15秒请求一次状态更新
    
    // 延迟请求一次状态更新，确保WebSocket连接建立
    const initialStatusUpdate = setTimeout(() => {
      if (wsService.connected) {
        console.log('🔄 [Videos] Requesting initial status update...');
        wsService.requestStatusUpdate();
      } else {
        console.log('⚠️ [Videos] WebSocket not connected yet, skipping initial status update');
      }
    }, 3000); // 3秒后请求一次状态更新
    
    return () => {
      cleanupWebSocket();
      clearInterval(statusUpdateInterval); // 清理定时器
      clearTimeout(initialStatusUpdate); // 清理初始状态更新定时器
    };
  }, []); // 空依赖数组，只在组件挂载时执行一次

  // 单独处理filters变化
  useEffect(() => {
    console.log('🔍 [Videos] Filters changed, refetching videos...');
    fetchVideos();
  }, [filters]);

  // Update the ref whenever the videos state changes
  useEffect(() => {
    videosRef.current = videos;
  }, [videos]);

  // 移除旧的订阅逻辑，现在使用状态查询模式
  // 这个useEffect已被删除，避免重复发送WebSocket消息

  const handleDownloadVideo = async (values: any) => {
    setDownloading(true);
    try {
      const formData = new FormData();
      formData.append('url', values.url);
      formData.append('project_id', values.project_id);
      formData.append('quality', values.quality);
      
      // 添加cookie文件（如果有）
      if (values.cookies && values.cookies[0]) {
        formData.append('cookies_file', values.cookies[0].originFileObj);
      }
      
      await videoAPI.downloadVideoWithCookies(formData, values.quality);
      message.success('视频下载任务已创建');
      setModalVisible(false);
      form.resetFields();
      
      // 等待一下让后端创建视频记录，然后查询活跃视频
      setTimeout(async () => {
        try {
          const activeVideos = await videoAPI.getActiveVideos();
          // 更新videos列表，添加新的活跃视频
          setVideos(prev => {
            const existingIds = prev.map(v => v.id);
            const newVideos = activeVideos.data.filter((v: Video) => !existingIds.includes(v.id));
            return [...newVideos, ...prev];
          });
        } catch (error) {
          console.error('获取活跃视频失败:', error);
          fetchVideos(); // 降级到完整刷新
        }
      }, 1000);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '视频下载失败');
    } finally {
      setDownloading(false);
    }
  };

  const handleDeleteVideo = async (id: number) => {
    try {
      await videoAPI.deleteVideo(id);
      message.success('视频删除成功');
      fetchVideos();
    } catch (error) {
      message.error('视频删除失败');
    }
  };

  const handleFilterChange = (key: string, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      page: 1 // 重置页码
    }));
  };

  const handleDateRangeChange = (dates: any, dateStrings: [string, string]) => {
    setFilters(prev => ({
      ...prev,
      start_date: dateStrings[0],
      end_date: dateStrings[1],
      page: 1
    }));
  };

  const clearFilters = () => {
    setFilters({
      project_id: undefined,
      status: undefined,
      search: '',
      start_date: undefined,
      end_date: undefined,
      min_duration: undefined,
      max_duration: undefined,
      min_file_size: undefined,
      max_file_size: undefined,
      page: 1,
      page_size: 10
    });
  };

  const setupWebSocket = () => {
    console.log('🔌 [Videos] Setting up WebSocket...');
    
    const token = localStorage.getItem('token');
    console.log('🔌 [Videos] Token from localStorage:', token ? `${token.substring(0, 20)}...` : 'null');
    
    if (!token) {
      console.log('❌ [Videos] No token found, skipping WebSocket connection');
      return;
    }

    // 检查是否已经连接，避免重复连接
    if (wsService.connected) {
      console.log('🔌 [Videos] WebSocket already connected, skipping setup');
      return;
    }

    console.log('🔌 [Videos] Connecting to WebSocket service...');
    
    // 连接WebSocket
    wsService.connect(token);
    startHeartbeat();
    console.log('🔌 [Videos] WebSocket connection initiated, heartbeat started');

    // 监听WebSocket事件
    wsService.on('connected', () => {
      console.log('✅ [Videos] WebSocket connected event received');
      // 连接成功，不需要订阅，现在使用状态查询模式
    });

    wsService.on('progress_update', (data: { video_id: number; video_status?: string; download_progress?: number; processing_progress?: number; processing_stage?: string; processing_message?: string; file_size?: number; file_size_unit?: string; total_size?: number }) => {
      console.log('📊 [Videos] Progress update received:', data);
      console.log('📊 [Videos] Update video ID:', data.video_id);
      
      // 查找对应的视频并更新，使用ref获取最新状态
      const currentVideos = videosRef.current;
      const videoIndex = currentVideos.findIndex(v => v.id === data.video_id);
      if (videoIndex !== -1) {
        console.log('✅ [Videos] Found video in list, updating...');
        const oldStatus = currentVideos[videoIndex].status;
        const newStatus = data.video_status || currentVideos[videoIndex].status;
        
        // 计算文件大小（如果有文件大小信息）
        let updatedFileSize = currentVideos[videoIndex].file_size;
        if (data.file_size && data.file_size_unit) {
          // 将文件大小转换为字节
          const sizeInBytes = convertSizeToBytes(data.file_size, data.file_size_unit);
          if (sizeInBytes > 0) {
            updatedFileSize = sizeInBytes;
          }
        } else if (data.total_size) {
          // 如果有总大小信息（单位可能是MiB或GiB），转换为字节
          updatedFileSize = Math.round(data.total_size * 1024 * 1024); // 假设是MiB
        }
        
        setVideos(prev => {
          const updated = [...prev];
          updated[videoIndex] = {
            ...updated[videoIndex],
            status: newStatus,
            download_progress: data.download_progress || updated[videoIndex].download_progress,
            processing_progress: data.processing_progress || updated[videoIndex].processing_progress,
            processing_stage: data.processing_stage || updated[videoIndex].processing_stage,
            processing_message: data.processing_message || updated[videoIndex].processing_message,
            file_size: updatedFileSize
          };
          return updated;
        });
        
        // 移除订阅逻辑，现在使用状态查询模式
        // 状态查询会自动获取所有活跃视频的最新状态
        
        // 如果下载接近完成（>=95%），主动查询特定视频的最终状态
        const downloadProgress = data.download_progress || 0;
        if (downloadProgress >= 95 && downloadProgress < 100) {
          console.log('🔄 [Videos] Video download near completion, requesting final status...');
          // 延迟1秒后查询特定视频的最终状态
          setTimeout(() => {
            if (wsService.connected) {
              wsService.requestVideoStatusUpdate(data.video_id);
            }
          }, 1000);
        }
        
        // 如果下载完成，刷新列表以获取完整信息
        if ((data.video_status === 'completed' || data.video_status === 'downloaded') && data.download_progress === 100) {
          console.log('📥 [Videos] Video download completed, refreshing list...');
          setTimeout(() => {
            fetchVideos();
          }, 2000);
        }
      } else {
        console.log('⚠️ [Videos] Video not found in current list, ID:', data.video_id);
        // If video not found, it might be a new video being downloaded.
        // Query active videos to get the new video into the list.
        const fetchActiveVideos = async () => {
          try {
            const activeVideos = await videoAPI.getActiveVideos();
            const newVideo = activeVideos.data.find((v: Video) => v.id === data.video_id);
            if (newVideo) {
              setVideos(prev => [...prev, newVideo]);
              console.log('✅ [Videos] Added new video to list:', newVideo.title);
            }
          } catch (error) {
            console.error('获取活跃视频失败:', error);
            fetchVideos(); // 降级到完整刷新
          }
        };
        fetchActiveVideos();
      }
    });

    wsService.on('disconnected', () => {
      console.log('🔌 [Videos] WebSocket disconnected event received');
    });

    wsService.on('error', (error: any) => { // Explicitly type as any for now, or define a more specific error interface if available
      console.error('❌ [Videos] WebSocket error event received:', error);
    });
  };

  const cleanupWebSocket = () => {
    console.log('🧹 [Videos] Cleaning up WebSocket connection...');
    stopHeartbeat();
    wsService.disconnect();
    
    // 移除所有事件监听器，防止重复注册
    // 注意：WebSocket服务本身是单例，所以不需要完全重置
    console.log('🧹 [Videos] WebSocket cleanup completed');
  };

  const showDownloadModal = () => {
    form.resetFields();
    setModalVisible(true);
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

  const convertSizeToBytes = (size: number, unit: string): number => {
    const unitMap: { [key: string]: number } = {
      'B': 1,
      'KB': 1024,
      'MB': 1024 * 1024,
      'GB': 1024 * 1024 * 1024,
      'KiB': 1024,
      'MiB': 1024 * 1024,
      'GiB': 1024 * 1024 * 1024,
      'bytes': 1
    };
    
    const multiplier = unitMap[unit] || 1;
    return Math.round(size * multiplier);
  };

  const columns = [
    {
      title: '视频标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string, record: Video) => (
        <div className="flex items-center">
          <ThumbnailRenderer 
            video={record}
            title={title}
          />
          <div>
            <div className="font-medium">{title}</div>
            <div className="text-sm text-gray-500">{formatDuration(record.duration)}</div>
          </div>
        </div>
      ),
    },
    {
      title: '项目',
      dataIndex: 'project_name',
      key: 'project_name',
      render: (projectName: string) => projectName || '未分类',
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: Video) => {
        // 根据下载进度决定显示状态
        const downloadProgress = record.download_progress || 0;
        
        let displayStatus = status;
        let statusConfig;
        
        // 优先根据下载进度判断
        if (downloadProgress >= 100) {
          // 下载完成，显示为已完成
          statusConfig = { color: 'green', text: '已完成' };
        } else if (downloadProgress > 0) {
          // 正在下载
          statusConfig = { color: 'blue', text: '下载中' };
        } else if (status === 'pending') {
          // 等待中
          statusConfig = { color: 'orange', text: '等待中' };
        } else if (status === 'processing') {
          // 处理中
          statusConfig = { color: 'cyan', text: '处理中' };
        } else if (status === 'downloaded') {
          // 已下载
          statusConfig = { color: 'purple', text: '已下载' };
        } else if (status === 'failed') {
          // 失败
          statusConfig = { color: 'red', text: '失败' };
        } else {
          // 其他状态
          statusConfig = { color: 'default', text: status };
        }
        
        return (
          <div>
            <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
            {(status === 'downloading' || (downloadProgress > 0 && downloadProgress < 100)) && (
              <div className="mt-1">
                <Progress
                  percent={Math.round(downloadProgress)}
                  size="small"
                  strokeColor={statusConfig.color}
                />
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Video) => (
        <Space size="middle">
          <Button
            type="link"
            icon={<PlayCircleOutlined />}
            onClick={() => navigate(`/dashboard/videos/${record.id}`)}
          >
            详情
          </Button>
          <Popconfirm
            title="确定要删除这个视频吗？"
            onConfirm={() => handleDeleteVideo(record.id)}
            okText="确定"
            cancelText="取消"
            disabled={(record.download_progress || 0) > 0 && (record.download_progress || 0) < 100}
          >
            <Button 
              type="link" 
              danger 
              icon={<DeleteOutlined />} 
              disabled={(record.download_progress || 0) > 0 && (record.download_progress || 0) < 100}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const qualityOptions = [
    { value: 'best', label: '最佳质量' },
    { value: '1080p', label: '1080p' },
    { value: '720p', label: '720p' },
    { value: '480p', label: '480p' },
    { value: '360p', label: '360p' },
  ];


  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">视频管理</h1>
        <Button 
          type="primary" 
          icon={<DownloadOutlined />} 
          onClick={showDownloadModal}
          disabled={projects.length === 0}
        >
          下载视频
        </Button>
      </div>

      {/* 筛选器 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={4}>
            <Select
              placeholder="选择项目"
              value={filters.project_id}
              onChange={(value) => handleFilterChange('project_id', value)}
              style={{ width: '100%' }}
              allowClear
            >
              {projects.map(project => (
                <Select.Option key={project.id} value={project.id}>
                  {project.name}
                </Select.Option>
              ))}
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="视频状态"
              value={filters.status}
              onChange={(value) => handleFilterChange('status', value)}
              style={{ width: '100%' }}
              allowClear
            >
              <Select.Option value="pending">等待中</Select.Option>
              <Select.Option value="downloading">下载中</Select.Option>
              <Select.Option value="downloaded">已下载</Select.Option>
              <Select.Option value="processing">处理中</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
              <Select.Option value="failed">失败</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Input.Group compact>
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最小时长(秒)"
                value={filters.min_duration}
                onChange={(value) => handleFilterChange('min_duration', value)}
              />
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最大时长(秒)"
                value={filters.max_duration}
                onChange={(value) => handleFilterChange('max_duration', value)}
              />
            </Input.Group>
          </Col>
          <Col span={4}>
            <Input.Group compact>
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最小大小(MB)"
                value={filters.min_file_size}
                onChange={(value) => handleFilterChange('min_file_size', value)}
              />
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最大大小(MB)"
                value={filters.max_file_size}
                onChange={(value) => handleFilterChange('max_file_size', value)}
              />
            </Input.Group>
          </Col>
          <Col span={6}>
            <DatePicker.RangePicker
              style={{ width: '100%' }}
              onChange={handleDateRangeChange}
              placeholder={['开始日期', '结束日期']}
            />
          </Col>
          <Col span={4}>
            <Input
              placeholder="搜索视频标题"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              onPressEnter={fetchVideos}
            />
          </Col>
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col>
            <Space>
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={fetchVideos}
                loading={loading}
              >
                搜索
              </Button>
              <Button
                icon={<ClearOutlined />}
                onClick={clearFilters}
              >
                清除
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchVideos}
                loading={loading}
              >
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={videos}
          rowKey="id"
          loading={loading}
          pagination={{
            current: pagination.page,
            pageSize: pagination.page_size,
            total: pagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
            onChange: (page, pageSize) => {
              setFilters(prev => ({
                ...prev,
                page,
                page_size: pageSize || 10
              }));
            },
          }}
          scroll={{ x: 800 }}
        />
      </Card>

      <Modal
        title="下载YouTube视频"
        open={modalVisible}
        onOk={() => form.submit()}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        okText="开始下载"
        cancelText="取消"
        okButtonProps={{ 
          icon: <DownloadOutlined />,
          loading: downloading,
          disabled: downloading
        }}
        cancelButtonProps={{ disabled: downloading }}
        closable={!downloading}
        maskClosable={!downloading}
      >
        <Form form={form} layout="vertical" onFinish={handleDownloadVideo} disabled={downloading}>
          <Form.Item
            name="url"
            label="YouTube URL"
            rules={[
              { required: true, message: '请输入YouTube视频URL' },
              { type: 'url', message: '请输入有效的URL' },
              { pattern: /youtube\.com|youtu\.be/, message: '请输入YouTube视频URL' }
            ]}
          >
            <Input
              placeholder="https://youtube.com/watch?v=..."
              allowClear
            />
          </Form.Item>

          <Form.Item
            name="project_id"
            label="选择项目"
            rules={[{ required: true, message: '请选择项目' }]}
          >
            <Select placeholder="选择项目">
              {projects.map(project => (
                <Select.Option key={project.id} value={project.id}>
                  {project.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="quality"
            label="视频质量"
            initialValue="best"
          >
            <Select>
              {qualityOptions.map(option => (
                <Select.Option key={option.value} value={option.value}>
                  {option.label}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="cookies"
            label="Cookie文件（可选）"
            valuePropName="fileList"
            getValueFromEvent={(e: any) => {
              if (Array.isArray(e)) {
                return e;
              }
              return e?.fileList;
            }}
            extra="上传YouTube cookie文件以避免下载限制，文件格式应为Netscape格式的cookies.txt"
          >
            <Upload
              accept=".txt"
              maxCount={1}
              beforeUpload={(file) => {
                const isTxt = file.type === 'text/plain' || file.name.endsWith('.txt');
                if (!isTxt) {
                  message.error('只能上传txt格式的cookie文件！');
                }
                return false; // 阻止自动上传，等待表单提交
              }}
              customRequest={({ file, onSuccess }) => {
                // 空操作，完全禁用自动上传
                if (onSuccess) onSuccess('ok');
              }}
            >
              <Button icon={<UploadOutlined />}>选择cookie文件</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Videos;
