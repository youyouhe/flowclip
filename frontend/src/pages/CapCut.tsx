import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Card, 
  Select, 
  Button, 
  Space, 
  message, 
  Spin, 
  Typography, 
  Row, 
  Col, 
  Table, 
  Tag, 
  Modal, 
  Input,
  Alert,
  Progress,
  Form,
  InputNumber,
  DatePicker
} from 'antd';
import { 
  PlayCircleOutlined, 
  EyeOutlined, 
  DeleteOutlined, 
  DownloadOutlined,
  VideoCameraAddOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  ClearOutlined as ClearFiltersOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { videoAPI } from '../services/api';
import { videoSliceAPI } from '../services/api';
import { capcutAPI } from '../services/api';
import { jianyingAPI } from '../services/api';
import { systemConfigAPI } from '../services/api';
import { projectAPI } from '../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

interface Video {
  id: number;
  title: string;
  project_id: number;
  status: string;
}

interface Project {
  id: number;
  name: string;
}

interface VideoSubSlice {
  id: number;
  slice_id: number;
  cover_title: string;
  start_time: number;
  end_time: number;
  duration: number;
  sliced_file_path: string;
  file_size: number;
  status: string;
  created_at: string;
}

interface VideoSlice {
  id: number;
  video_id: number;
  cover_title: string;
  title: string;
  description: string;
  tags: string[];
  start_time: number;
  end_time: number;
  duration: number;
  sliced_file_path: string;
  file_size: number;
  status: string;
  created_at: string;
  sub_slices?: VideoSubSlice[];
  capcut_status?: 'pending' | 'processing' | 'completed' | 'failed';
  capcut_task_id?: string;
  capcut_draft_url?: string;
  jianying_status?: 'pending' | 'processing' | 'completed' | 'failed';
  jianying_task_id?: string;
  jianying_draft_url?: string;
}

const CapCut: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [slices, setSlices] = useState<VideoSlice[]>([]);
  const [loading, setLoading] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [draftFolder, setDraftFolder] = useState('');
  const [capcutModalVisible, setCapcutModalVisible] = useState(false);
  const [jianyingModalVisible, setJianyingModalVisible] = useState(false);
  const [jianyingDraftFolder, setJianyingDraftFolder] = useState('');
  const [selectedSlice, setSelectedSlice] = useState<VideoSlice | null>(null);
  const [capcutStatus, setCapcutStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [jianyingStatus, setJianyingStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [capcutProgress, setCapcutProgress] = useState({
    isProcessing: false,
    progress: 0,
    message: '',
    taskId: ''
  });
  const [jianyingProgress, setJianyingProgress] = useState({
    isProcessing: false,
    progress: 0,
    message: '',
    taskId: ''
  });
  
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
  });

  useEffect(() => {
    loadVideos();
    loadProjects();
    checkCapCutStatus();
    checkJianyingStatus();
  }, []);

  const checkCapCutStatus = async () => {
    try {
      const response = await capcutAPI.getStatus();
      setCapcutStatus(response.data.status === 'online' ? 'online' : 'offline');
    } catch (error: any) {
      setCapcutStatus('offline');
    }
  };

  const checkJianyingStatus = async () => {
    try {
      const response = await jianyingAPI.getStatus();
      setJianyingStatus(response.data.status === 'online' ? 'online' : 'offline');
    } catch (error: any) {
      setJianyingStatus('offline');
    }
  };

  useEffect(() => {
    if (selectedVideo) {
      loadSlices();
    }
  }, [selectedVideo]);
  
  useEffect(() => {
    loadVideos();
  }, [filters]);

  // 监听切片状态变化，当有切片完成时显示提示
  const prevCompleted = useRef<number[]>([]);
  
  useEffect(() => {
    const completedSlices = slices.filter(s => s.capcut_status === 'completed');
    const processingSlices = slices.filter(s => s.capcut_status === 'processing');

    // 检查是否有新的完成的切片（避免重复提示）
    if (completedSlices.length > prevCompleted.current.length) {
      const newCompleted = completedSlices.filter(s => !prevCompleted.current.includes(s.id));
      if (newCompleted.length > 0) {
        const latestCompleted = newCompleted[0];
        message.success(`CapCut导出完成：${latestCompleted.cover_title}`);

        // 如果有草稿URL，也显示一个提示
        if (latestCompleted.capcut_draft_url) {
          setTimeout(() => {
            message.info(`📄 草稿文件已生成，可以点击"下载草稿"按钮下载`);
          }, 1000);
        }
      }
    }

    prevCompleted.current = completedSlices.map(s => s.id);
  }, [slices]);

  // 监听Jianying切片状态变化，当有切片完成时显示提示
  const prevJianyingCompleted = useRef<number[]>([]);

  useEffect(() => {
    const completedSlices = slices.filter(s => s.jianying_status === 'completed');

    // 检查是否有新的完成的Jianying切片（避免重复提示）
    if (completedSlices.length > prevJianyingCompleted.current.length) {
      const newCompleted = completedSlices.filter(s => !prevJianyingCompleted.current.includes(s.id));
      if (newCompleted.length > 0) {
        const latestCompleted = newCompleted[0];
        message.success(`Jianying导出完成：${latestCompleted.cover_title}`);

        // 如果有草稿URL，也显示一个提示
        if (latestCompleted.jianying_draft_url) {
          setTimeout(() => {
            message.info(`📄 Jianying草稿文件已生成，可以点击"Jianying草稿"按钮下载`);
          }, 1000);
        }
      }
    }

    prevJianyingCompleted.current = completedSlices.map(s => s.id);
  }, [slices]);

  // 定时检查任务状态（CapCut和Jianying）
  useEffect(() => {
    const checkTaskStatus = async () => {
      if (!selectedVideo) return;

      // 总是重新获取切片数据，不依赖闭包中的slices状态
      try {
        console.log('定时检查：重新获取切片状态');
        await loadSlices();
      } catch (error) {
        console.error('刷新切片状态失败:', error);
      }
    };

    const intervalId = setInterval(checkTaskStatus, 3000); // 每3秒检查一次
    return () => clearInterval(intervalId);
  }, [selectedVideo, loadSlices]); // 添加loadSlices依赖

  const loadVideos = async () => {
    try {
      setVideosLoading(true);
      // 构建查询参数
      const params: any = { status: 'completed' };
      if (filters.project_id) params.project_id = filters.project_id;
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.min_duration !== undefined) params.min_duration = filters.min_duration;
      if (filters.max_duration !== undefined) params.max_duration = filters.max_duration;
      if (filters.min_file_size !== undefined) params.min_file_size = filters.min_file_size;
      if (filters.max_file_size !== undefined) params.max_file_size = filters.max_file_size;

      const response = await videoAPI.getVideos(params);
      const videosData = response.data.videos || response.data;
      const completedVideos = videosData.filter((video: Video) =>
        video.status === 'completed'
      );
      setVideos(completedVideos);
    } catch (error: any) {
      message.error('加载视频列表失败');
    } finally {
      setVideosLoading(false);
    }
  };
  
  const loadProjects = async () => {
    try {
      const response = await projectAPI.getProjects();
      setProjects(response.data);
    } catch (error: any) {
      message.error('获取项目列表失败');
    }
  };
  
  const handleFilterChange = (key: string, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  const handleDateRangeChange = (dates: any, dateStrings: [string, string]) => {
    setFilters(prev => ({
      ...prev,
      start_date: dateStrings[0],
      end_date: dateStrings[1]
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
    });
  };

  const loadSlices = useCallback(async () => {
    if (!selectedVideo) return;

    try {
      setLoading(true);
      const response = await videoSliceAPI.getVideoSlices(selectedVideo);
      const slicesData = response.data;

      // 为每个切片加载子切片
      const slicesWithSubs = await Promise.all(
        slicesData.map(async (slice: VideoSlice) => {
          try {
            const subResponse = await videoSliceAPI.getSliceSubSlices(slice.id);
            return {
              ...slice,
              sub_slices: subResponse.data
            };
          } catch (error: any) {
            console.error(`加载切片 ${slice.id} 的子切片失败:`, error);
            return {
              ...slice,
              sub_slices: []
            };
          }
        })
      );

      setSlices(slicesWithSubs);
    } catch (error: any) {
      message.error('加载切片数据失败');
    } finally {
      setLoading(false);
    }
  }, [selectedVideo]);

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleCapCutExport = async (slice: VideoSlice) => {
    setSelectedSlice(slice);

    // 首先尝试从系统配置获取草稿文件夹路径
    try {
      const response = await systemConfigAPI.getSystemConfigs();
      const configs = response.data;
      const draftFolderConfig = configs.find((config: any) => config.key === 'capcut_draft_folder');
      let defaultDraftFolder = '';

      if (draftFolderConfig && draftFolderConfig.value) {
        defaultDraftFolder = draftFolderConfig.value;
      } else {
        // 如果系统配置中没有设置，则使用环境变量
        defaultDraftFolder = import.meta.env.VITE_CAPCUT_DRAFT_FOLDER || '';
      }

      setDraftFolder(defaultDraftFolder);
    } catch (error: any) {
      // 如果获取系统配置失败，使用环境变量作为备选
      const defaultDraftFolder = import.meta.env.VITE_CAPCUT_DRAFT_FOLDER || '';
      setDraftFolder(defaultDraftFolder);
      console.error('获取系统配置失败:', error);
    }

    setCapcutModalVisible(true);
  };

  const handleProcessCapCut = async () => {
    if (!selectedSlice || !draftFolder.trim()) {
      message.error('请填写草稿文件夹路径');
      return;
    }

    try {
      setLoading(true);
      // 调用后端API来处理CapCut导出
      setCapcutProgress({
        isProcessing: true,
        progress: 0,
        message: '正在启动CapCut导出任务...',
        taskId: 'capcut_' + Date.now()
      });

      setCapcutModalVisible(false);

      const response = await capcutAPI.exportSlice(selectedSlice.id, draftFolder);

      if (response.data.success) {
        // 更新切片状态
        setSlices(prev => prev.map(s =>
          s.id === selectedSlice.id
            ? {...s, capcut_status: 'processing', capcut_task_id: response.data.task_id}
            : s
        ));

        setCapcutProgress({
          isProcessing: false,
          progress: 100,
          message: 'CapCut导出任务已启动',
          taskId: response.data.task_id
        });

        message.success('CapCut导出任务已启动');
      } else {
        throw new Error(response.data.message || '导出失败');
      }
    } catch (error: any) {
      console.error('CapCut导出失败:', error);
      message.error('启动CapCut导出失败: ' + (error.response?.data?.detail || error.message || '未知错误'));
      setCapcutProgress({
        isProcessing: false,
        progress: 0,
        message: '处理失败: ' + (error.response?.data?.detail || error.message || '未知错误'),
        taskId: ''
      });
    } finally {
      setLoading(false);
    }
  };

  const handleJianyingExport = async (slice: VideoSlice) => {
    setSelectedSlice(slice);

    // 首先尝试从系统配置获取Jianying草稿文件夹路径
    try {
      const response = await systemConfigAPI.getSystemConfigs();
      const configs = response.data;
      const draftFolderConfig = configs.find((config: any) => config.key === 'jianying_draft_folder');
      let defaultDraftFolder = '';

      if (draftFolderConfig && draftFolderConfig.value) {
        defaultDraftFolder = draftFolderConfig.value;
      } else {
        // 如果系统配置中没有设置，则使用环境变量
        defaultDraftFolder = import.meta.env.VITE_JIANYING_DRAFT_FOLDER || '';
      }

      setJianyingDraftFolder(defaultDraftFolder);
    } catch (error: any) {
      // 如果获取系统配置失败，使用环境变量作为备选
      const defaultDraftFolder = import.meta.env.VITE_JIANYING_DRAFT_FOLDER || '';
      setJianyingDraftFolder(defaultDraftFolder);
      console.error('获取系统配置失败:', error);
    }

    setJianyingModalVisible(true);
  };

  const handleProcessJianying = async () => {
    if (!selectedSlice || !jianyingDraftFolder.trim()) {
      message.error('请填写Jianying草稿文件夹路径');
      return;
    }

    try {
      setLoading(true);
      // 调用后端API来处理Jianying导出
      setJianyingProgress({
        isProcessing: true,
        progress: 0,
        message: '正在启动Jianying导出任务...',
        taskId: 'jianying_' + Date.now()
      });

      setJianyingModalVisible(false);

      const response = await jianyingAPI.exportSlice(selectedSlice.id, jianyingDraftFolder);

      if (response.data.success) {
        // 更新切片状态
        setSlices(prev => prev.map(s =>
          s.id === selectedSlice.id
            ? {...s, jianying_status: 'processing', jianying_task_id: response.data.task_id}
            : s
        ));

        setJianyingProgress({
          isProcessing: false,
          progress: 100,
          message: 'Jianying导出任务已启动',
          taskId: response.data.task_id
        });

        message.success('Jianying导出任务已启动');
      } else {
        throw new Error(response.data.message || '导出失败');
      }
    } catch (error: any) {
      console.error('Jianying导出失败:', error);
      message.error('启动Jianying导出失败: ' + (error.response?.data?.detail || error.message || '未知错误'));
      setJianyingProgress({
        isProcessing: false,
        progress: 0,
        message: '处理失败: ' + (error.response?.data?.detail || error.message || '未知错误'),
        taskId: ''
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadDraft = async (slice: VideoSlice) => {
    if (!slice.capcut_draft_url) {
      message.error('CapCut草稿文件尚未生成');
      return;
    }

    try {
      message.success('正在准备下载...');
      // 直接在浏览器中打开下载链接
      window.open(slice.capcut_draft_url, '_blank');
    } catch (error: any) {
      message.error('下载失败');
    }
  };

  const handleDownloadJianyingDraft = async (slice: VideoSlice) => {
    if (!slice.jianying_draft_url) {
      message.error('Jianying草稿文件尚未生成');
      return;
    }

    try {
      message.success('正在准备下载...');
      // 直接在浏览器中打开下载链接
      window.open(slice.jianying_draft_url, '_blank');
    } catch (error: any) {
      message.error('下载失败');
    }
  };

  const sliceColumns = [
    {
      title: '封面标题',
      dataIndex: 'cover_title',
      key: 'cover_title',
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (time: number) => formatTime(time),
    },
    {
      title: '结束时间',
      dataIndex: 'end_time',
      key: 'end_time',
      render: (time: number) => formatTime(time),
    },
    {
      title: '持续时间',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => formatTime(duration),
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '子切片',
      key: 'sub_slices',
      render: (record: VideoSlice) => (
        <span>
          {record.sub_slices?.length || 0} 个子切片
        </span>
      ),
    },
    {
      title: 'CapCut状态',
      key: 'capcut_status',
      render: (record: VideoSlice) => {
        if (!record.capcut_status) {
          return <Tag color="default">未处理</Tag>;
        }

        const statusConfig = {
          pending: { color: 'default', text: '待处理' },
          processing: { color: 'processing', text: '处理中' },
          completed: { color: 'success', text: '已完成' },
          failed: { color: 'error', text: '失败' }
        };

        const config = statusConfig[record.capcut_status] || statusConfig.pending;

        if (record.capcut_status === 'completed' && record.capcut_draft_url) {
          return (
            <Space>
              <Tag color={config.color}>{config.text}</Tag>
              <Tag color="default">📄 草稿已生成</Tag>
            </Space>
          );
        }

        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: 'Jianying状态',
      key: 'jianying_status',
      render: (record: VideoSlice) => {
        if (!record.jianying_status) {
          return <Tag color="default">未处理</Tag>;
        }

        const statusConfig = {
          pending: { color: 'default', text: '待处理' },
          processing: { color: 'processing', text: '处理中' },
          completed: { color: 'success', text: '已完成' },
          failed: { color: 'error', text: '失败' }
        };

        const config = statusConfig[record.jianying_status] || statusConfig.pending;

        if (record.jianying_status === 'completed' && record.jianying_draft_url) {
          return (
            <Space>
              <Tag color={config.color}>{config.text}</Tag>
              <Tag color="default">📄 草稿已生成</Tag>
            </Space>
          );
        }

        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: VideoSlice) => (
        <Space>
          {/* Jianying导出按钮 */}
          <Button
            type="default"
            style={{ backgroundColor: '#ff4d4f', borderColor: '#ff4d4f', color: '#fff' }}
            icon={<VideoCameraAddOutlined />}
            onClick={() => handleJianyingExport(record)}
            disabled={jianyingStatus !== 'online' || record.jianying_status === 'processing'}
            title={
              jianyingStatus !== 'online'
                ? 'Jianying服务不可用'
                : record.jianying_status === 'processing'
                ? '正在处理中'
                : ''
            }
          >
            Jianying导出
          </Button>

          {/* CapCut导出按钮 */}
          <Button
            type="primary"
            icon={<VideoCameraAddOutlined />}
            onClick={() => handleCapCutExport(record)}
            disabled={capcutStatus !== 'online' || record.capcut_status === 'processing'}
            title={
              capcutStatus !== 'online'
                ? 'CapCut服务不可用'
                : record.capcut_status === 'processing'
                ? '正在处理中'
                : ''
            }
          >
            CapCut导出
          </Button>

          {/* 下载按钮 */}
          {record.capcut_status === 'completed' && record.capcut_draft_url && (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => handleDownloadDraft(record)}
            >
              CapCut草稿
            </Button>
          )}
          {record.jianying_status === 'completed' && record.jianying_draft_url && (
            <Button
              type="default"
              style={{ backgroundColor: '#52c41a', borderColor: '#52c41a', color: '#fff' }}
              icon={<DownloadOutlined />}
              onClick={() => handleDownloadJianyingDraft(record)}
            >
              Jianying草稿
            </Button>
          )}
          <Button
            icon={<EyeOutlined />}
            onClick={() => {
              Modal.info({
                title: '切片详情',
                content: (
                  <div>
                    <p><strong>描述:</strong> {record.description}</p>
                    <p><strong>标签:</strong> {record.tags?.join(', ')}</p>
                    <p><strong>文件路径:</strong> {record.sliced_file_path}</p>
                    {record.capcut_draft_url && (
                      <p><strong>CapCut草稿:</strong> 已生成</p>
                    )}
                    {record.jianying_draft_url && (
                      <p><strong>Jianying草稿:</strong> 已生成</p>
                    )}
                  </div>
                ),
                width: 600,
              });
            }}
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="capcut-management">
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Card title="视频导出管理">
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* 服务状态 */}
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col>
                  <Tag color={capcutStatus === 'online' ? 'success' : capcutStatus === 'checking' ? 'processing' : 'error'}>
                    CapCut服务: {capcutStatus === 'online' ? '在线' : capcutStatus === 'checking' ? '检查中...' : '离线'}
                  </Tag>
                  <Button size="small" onClick={checkCapCutStatus} style={{ marginLeft: 8 }}>
                    刷新
                  </Button>
                </Col>
                <Col>
                  <Tag color={jianyingStatus === 'online' ? 'success' : jianyingStatus === 'checking' ? 'processing' : 'error'}>
                    Jianying服务: {jianyingStatus === 'online' ? '在线' : jianyingStatus === 'checking' ? '检查中...' : '离线'}
                  </Tag>
                  <Button size="small" onClick={checkJianyingStatus} style={{ marginLeft: 8 }}>
                    刷新
                  </Button>
                </Col>
              </Row>
              
              {/* 处理进度显示 */}
              {capcutProgress.isProcessing && (
                <Alert
                  message="CapCut导出中"
                  description={
                    <div>
                      <Progress percent={capcutProgress.progress} status="active" />
                      <p>{capcutProgress.message}</p>
                      {capcutProgress.taskId && (
                        <Text type="secondary">任务ID: {capcutProgress.taskId}</Text>
                      )}
                    </div>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

              {jianyingProgress.isProcessing && (
                <Alert
                  message="Jianying导出中"
                  description={
                    <div>
                      <Progress percent={jianyingProgress.progress} status="active" />
                      <p>{jianyingProgress.message}</p>
                      {jianyingProgress.taskId && (
                        <Text type="secondary">任务ID: {jianyingProgress.taskId}</Text>
                      )}
                    </div>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}
              
              {/* 处理完成或失败提示 */}
              {!capcutProgress.isProcessing && capcutProgress.progress === 100 && (
                <Alert
                  message="CapCut导出完成"
                  description={capcutProgress.message}
                  type="success"
                  showIcon
                  style={{ marginBottom: 16 }}
                  closable
                  onClose={() => setCapcutProgress(prev => ({ ...prev, progress: 0, message: '' }))}
                />
              )}

              {!jianyingProgress.isProcessing && jianyingProgress.progress === 100 && (
                <Alert
                  message="Jianying导出完成"
                  description={jianyingProgress.message}
                  type="success"
                  showIcon
                  style={{ marginBottom: 16 }}
                  closable
                  onClose={() => setJianyingProgress(prev => ({ ...prev, progress: 0, message: '' }))}
                />
              )}
              
              <Row gutter={16}>
                <Col span={24}>
                  {/* 筛选器 */}
                  <div style={{ marginBottom: '16px' }}>
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
                            <Option key={project.id} value={project.id}>
                              {project.name}
                            </Option>
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
                          onPressEnter={loadVideos}
                        />
                      </Col>
                    </Row>
                    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                      <Col>
                        <Space>
                          <Button
                            type="primary"
                            icon={<SearchOutlined />}
                            onClick={loadVideos}
                            loading={videosLoading}
                          >
                            搜索
                          </Button>
                          <Button
                            icon={<ClearFiltersOutlined />}
                            onClick={clearFilters}
                          >
                            清除
                          </Button>
                          <Button
                            icon={<ReloadOutlined />}
                            onClick={loadVideos}
                            loading={videosLoading}
                          >
                            刷新
                          </Button>
                        </Space>
                      </Col>
                    </Row>
                  </div>
                </Col>
              </Row>
              
              <Row gutter={16}>
                <Col span={8}>
                  <Text strong>选择视频：</Text>
                  <Select
                    value={selectedVideo}
                    onChange={setSelectedVideo}
                    placeholder="选择视频文件"
                    style={{ width: '100%', marginTop: '8px' }}
                    loading={videosLoading}
                  >
                    {videos.map((video) => (
                      <Option key={video.id} value={video.id}>
                        {video.title}
                      </Option>
                    ))}
                  </Select>
                </Col>
              </Row>

              {selectedVideo && (
                <Table
                  columns={sliceColumns}
                  dataSource={slices}
                  rowKey="id"
                  loading={loading}
                  pagination={false}
                  expandable={{
                    expandedRowRender: (record: VideoSlice) => {
                      if (!record.sub_slices || record.sub_slices.length === 0) {
                        return (
                          <div style={{ padding: '16px', color: '#666' }}>
                            暂无子切片
                          </div>
                        );
                      }
                      
                      return (
                        <div style={{ padding: '16px' }}>
                          <h4 style={{ marginBottom: '12px' }}>
                            子切片列表 ({record.sub_slices.length}个)
                          </h4>
                          <Table
                            columns={[
                              {
                                title: '子切片标题',
                                dataIndex: 'cover_title',
                                key: 'cover_title',
                              },
                              {
                                title: '开始时间',
                                dataIndex: 'start_time',
                                key: 'start_time',
                                render: (time: number) => formatTime(time),
                              },
                              {
                                title: '结束时间',
                                dataIndex: 'end_time',
                                key: 'end_time',
                                render: (time: number) => formatTime(time),
                              },
                              {
                                title: '持续时间',
                                dataIndex: 'duration',
                                key: 'duration',
                                render: (duration: number) => formatTime(duration),
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
                                render: (status: string) => {
                                  const color = status === 'completed' ? 'green' : 'orange';
                                  return <Tag color={color}>{status}</Tag>;
                                },
                              },
                            ]}
                            dataSource={record.sub_slices}
                            rowKey="id"
                            pagination={false}
                            size="small"
                          />
                        </div>
                      );
                    },
                    rowExpandable: (record: VideoSlice) => {
                      return true;
                    },
                  }}
                />
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* CapCut导出模态框 */}
      <Modal
        title="CapCut导出设置"
        open={capcutModalVisible}
        onOk={handleProcessCapCut}
        onCancel={() => setCapcutModalVisible(false)}
        width={600}
        confirmLoading={loading}
      >
        {selectedSlice && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              message="确认导出到CapCut"
              description="将为选中的切片生成CapCut草稿文件，包含水波纹特效和水滴音频。"
              type="info"
              showIcon
            />

            <div>
              <Text strong>切片标题：</Text>
              <Text>{selectedSlice.cover_title}</Text>
            </div>

            <div>
              <Text strong>子切片数量：</Text>
              <Text>{selectedSlice.sub_slices?.length || 0}</Text>
            </div>

            <Form layout="vertical">
              <Form.Item
                label="草稿文件夹路径"
                required
              >
                <Input
                  value={draftFolder}
                  onChange={(e) => setDraftFolder(e.target.value)}
                  placeholder="请输入CapCut草稿文件夹路径"
                  addonBefore="路径"
                />
              </Form.Item>
            </Form>

            <Alert
              message="提示"
              description="请确保草稿文件夹路径正确，否则可能导致导出失败。"
              type="warning"
              showIcon
            />
          </Space>
        )}
      </Modal>

      {/* Jianying导出模态框 */}
      <Modal
        title="Jianying导出设置"
        open={jianyingModalVisible}
        onOk={handleProcessJianying}
        onCancel={() => setJianyingModalVisible(false)}
        width={600}
        confirmLoading={loading}
      >
        {selectedSlice && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              message="确认导出到Jianying"
              description="将为选中的切片生成Jianying草稿文件，包含彩虹渐变特效和水滴音频。"
              type="info"
              showIcon
            />

            <div>
              <Text strong>切片标题：</Text>
              <Text>{selectedSlice.cover_title}</Text>
            </div>

            <div>
              <Text strong>子切片数量：</Text>
              <Text>{selectedSlice.sub_slices?.length || 0}</Text>
            </div>

            <Form layout="vertical">
              <Form.Item
                label="Jianying草稿文件夹路径"
                required
              >
                <Input
                  value={jianyingDraftFolder}
                  onChange={(e) => setJianyingDraftFolder(e.target.value)}
                  placeholder="请输入Jianying草稿文件夹路径"
                  addonBefore="路径"
                />
              </Form.Item>
            </Form>

            <Alert
              message="提示"
              description="请确保Jianying草稿文件夹路径正确，否则可能导致导出失败。"
              type="warning"
              showIcon
            />
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default CapCut;