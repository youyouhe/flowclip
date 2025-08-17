import React, { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, Select, Space, message, Spin, Typography, Row, Col, Table, Tag, Modal, Form, Tabs, Divider, Alert, Progress } from 'antd';
import { PlayCircleOutlined, ScissorOutlined, UploadOutlined, EyeOutlined, EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { llmAPI } from '../services/api';
import { videoAPI } from '../services/api';
import { videoSliceAPI } from '../services/api';
import { wsService, startHeartbeat, stopHeartbeat } from '../services/websocket';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

interface Video {
  id: number;
  title: string;
  project_id: number;
  status: string;
}

interface LLMAnalysis {
  id: number;
  video_id: number;
  analysis_data: SliceData[];
  cover_title: string;
  status: string;
  is_validated: boolean;
  is_applied: boolean;
  created_at: string;
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
  type: string;
  created_at: string;
  sub_slices?: VideoSubSlice[];
}

const SliceManagement: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [analyses, setAnalyses] = useState<LLMAnalysis[]>([]);
  const [slices, setSlices] = useState<VideoSlice[]>([]);
  const [loading, setLoading] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [validateModalVisible, setValidateModalVisible] = useState(false);
  const [processModalVisible, setProcessModalVisible] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState<LLMAnalysis | null>(null);
  const [jsonInput, setJsonInput] = useState('');
  const [coverTitle, setCoverTitle] = useState('');
  const [form] = Form.useForm();
  
  // 切片处理进度状态
  const [sliceProgress, setSliceProgress] = useState<{
    isProcessing: boolean;
    progress: number;
    message: string;
    taskId: string | null;
  }>({
    isProcessing: false,
    progress: 0,
    message: '',
    taskId: null
  });
  
  // 轮询定时器引用
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // 定义新的切片数据接口，以匹配新的JSON格式
  interface SliceChapter {
    cover_title: string;
    start: string; // 格式: "00:08:20,100"
    end: string;   // 格式: "00:10:55,300"
  }
  
  interface SliceData {
    cover_title: string;
    title: string;
    desc: string;
    tags: string[];
    start: string; // 格式: "00:08:15,250"
    end: string;   // 格式: "00:15:45,800"
    chapters: SliceChapter[];
  }

  useEffect(() => {
    loadVideos();
    initWebSocket();
    return () => {
      stopHeartbeat();
      wsService.disconnect();
      // 清理轮询定时器
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (selectedVideo) {
      loadAnalyses();
      loadSlices();
      // 订阅视频进度更新
      if (wsService.connected) {
        wsService.subscribeVideoProgress(selectedVideo);
      }
    }
  }, [selectedVideo]);

  const initWebSocket = () => {
    const token = localStorage.getItem('token');
    if (token) {
      wsService.connect(token);
      startHeartbeat();
      
      // 监听进度更新
      wsService.on('progress_update', (data: any) => {
        console.log('收到进度更新:', data);
        
        // 检查是否是切片任务的进度更新
        if (data.task_id === sliceProgress.taskId && sliceProgress.isProcessing) {
          setSliceProgress(prev => ({
            ...prev,
            progress: data.progress || 0,
            message: data.message || '处理中...'
          }));
        }
        
        // 如果切片任务完成，刷新数据
        if (data.status === 'completed' && sliceProgress.isProcessing) {
          // 清理轮询定时器
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          
          setSliceProgress(prev => ({
            ...prev,
            isProcessing: false,
            progress: 100,
            message: '切片处理完成'
          }));
          
          // 延迟刷新数据，确保数据库已更新
          setTimeout(() => {
            loadAnalyses();
            loadSlices();
          }, 1000);
        }
        
        // 如果切片任务失败
        if (data.status === 'failed' && sliceProgress.isProcessing) {
          // 清理轮询定时器
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          
          setSliceProgress(prev => ({
            ...prev,
            isProcessing: false,
            message: `处理失败: ${data.error || '未知错误'}`
          }));
          message.error(`切片处理失败: ${data.error || '未知错误'}`);
        }
      });
      
      // 监听连接状态
      wsService.on('connected', () => {
        console.log('WebSocket连接已建立');
        if (selectedVideo) {
          wsService.subscribeVideoProgress(selectedVideo);
        }
      });
    }
  };
  
  // 轮询获取任务状态
  const pollTaskStatus = async (taskId: string) => {
    if (!selectedVideo) return;
    
    try {
      const response = await videoAPI.getTaskStatus(selectedVideo, taskId);
      const taskStatus = response.data;
      
      // 更新进度
      setSliceProgress(prev => ({
        ...prev,
        progress: taskStatus.progress || 0,
        message: taskStatus.message || '处理中...'
      }));
      
      // 检查任务是否完成
      if (taskStatus.status === 'completed' || taskStatus.status === 'success') {
        // 停止轮询
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        
        setSliceProgress(prev => ({
          ...prev,
          isProcessing: false,
          progress: 100,
          message: '切片处理完成'
        }));
        
        // 刷新数据
        setTimeout(() => {
          loadAnalyses();
          loadSlices();
        }, 1000);
        
        message.success('切片处理完成');
      } else if (taskStatus.status === 'failed') {
        // 停止轮询
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        
        setSliceProgress(prev => ({
          ...prev,
          isProcessing: false,
          message: `处理失败: ${taskStatus.error || '未知错误'}`
        }));
        
        message.error(`切片处理失败: ${taskStatus.error || '未知错误'}`);
      }
    } catch (error) {
      console.error('获取任务状态失败:', error);
    }
  };

  const loadVideos = async () => {
    try {
      setVideosLoading(true);
      // 只获取SRT处理成功的视频
      const response = await videoAPI.getVideos({ srt_processed: true });
      // 处理分页响应格式
      const videosData = response.data.videos || response.data;
      
      setVideos(videosData);
    } catch (error) {
      message.error('加载视频列表失败');
    } finally {
      setVideosLoading(false);
    }
  };

  const loadAnalyses = async () => {
    if (!selectedVideo) return;
    
    try {
      setLoading(true);
      const response = await videoSliceAPI.getVideoAnalyses(selectedVideo);
      setAnalyses(response.data);
    } catch (error) {
      message.error('加载分析数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSlices = async () => {
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
          } catch (error) {
            console.error(`加载切片 ${slice.id} 的子切片失败:`, error);
            return {
              ...slice,
              sub_slices: []
            };
          }
        })
      );
      
      setSlices(slicesWithSubs);
    } catch (error) {
      message.error('加载切片数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleValidateData = async () => {
    if (!jsonInput.trim() || !coverTitle.trim() || !selectedVideo) {
      message.error('请填写完整信息');
      return;
    }

    try {
      setLoading(true);
      const parsedData = JSON.parse(jsonInput);
      
      const response = await videoSliceAPI.validateSliceData({
        video_id: selectedVideo,
        analysis_data: parsedData,
        cover_title: coverTitle
      });

      if (response.data.is_valid) {
        message.success('数据验证成功！');
        setValidateModalVisible(false);
        setJsonInput('');
        setCoverTitle('');
        loadAnalyses();
      } else {
        message.error('数据验证失败：' + response.data.message);
        if (response.data.errors) {
          response.data.errors.forEach((error: string) => {
            message.error(error);
          });
        }
      }
    } catch (error: any) {
      console.error('验证失败:', error);
      if (error.response?.data?.detail) {
        message.error('验证失败: ' + error.response.data.detail);
      } else {
        message.error('JSON格式错误或验证失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleProcessSlices = async () => {
    if (!selectedAnalysis) return;

    try {
      setLoading(true);
      const response = await videoSliceAPI.processSlices({
        analysis_id: selectedAnalysis.id,
        slice_items: selectedAnalysis.analysis_data
      });

      // 设置处理状态
      setSliceProgress({
        isProcessing: true,
        progress: 0,
        message: '正在启动切片任务...',
        taskId: response.data.task_id
      });

      message.success('切片处理任务已启动，请查看进度');
      setProcessModalVisible(false);
      
      // 启动轮询机制作为WebSocket的备用方案
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      pollIntervalRef.current = setInterval(() => {
        if (response.data.task_id) {
          pollTaskStatus(response.data.task_id);
        }
      }, 3000); // 每3秒轮询一次
      
    } catch (error: any) {
      console.error('启动处理失败:', error);
      message.error('启动处理失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

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

  const handleDeleteAnalysis = async (analysisId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个分析数据吗？此操作不可恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          setLoading(true);
          await videoSliceAPI.deleteAnalysis(analysisId);
          message.success('分析数据删除成功');
          loadAnalyses();
        } catch (error) {
          message.error('删除分析数据失败');
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const handleDeleteSlice = async (sliceId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个切片吗？此操作会同时删除所有子切片。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          setLoading(true);
          await videoSliceAPI.deleteSlice(sliceId);
          message.success('切片删除成功');
          loadSlices();
        } catch (error) {
          message.error('删除切片失败');
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const handleDeleteSubSlice = async (subSliceId: number, sliceId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个子切片吗？',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          setLoading(true);
          await videoSliceAPI.deleteSubSlice(subSliceId);
          message.success('子切片删除成功');
          loadSlices();
        } catch (error) {
          message.error('删除子切片失败');
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const analysisColumns = [
    {
      title: '封面标题',
      dataIndex: 'cover_title',
      key: 'cover_title',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'applied' ? 'green' : status === 'validated' ? 'blue' : 'orange';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '已验证',
      dataIndex: 'is_validated',
      key: 'is_validated',
      render: (validated: boolean) => (
        <Tag color={validated ? 'green' : 'red'}>
          {validated ? '已验证' : '未验证'}
        </Tag>
      ),
    },
    {
      title: '已应用',
      dataIndex: 'is_applied',
      key: 'is_applied',
      render: (applied: boolean) => (
        <Tag color={applied ? 'green' : 'red'}>
          {applied ? '已应用' : '未应用'}
        </Tag>
      ),
    },
    {
      title: '切片数量',
      dataIndex: 'analysis_data',
      key: 'slice_count',
      render: (data: any[]) => data.length,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: LLMAnalysis) => (
        <Space>
          {record.is_validated && !record.is_applied && (
            <Button
              type="primary"
              icon={<ScissorOutlined />}
              onClick={() => {
                setSelectedAnalysis(record);
                setProcessModalVisible(true);
              }}
              disabled={sliceProgress.isProcessing}
              loading={sliceProgress.isProcessing}
            >
              切片
            </Button>
          )}
          <Button
            icon={<EyeOutlined />}
            onClick={() => {
              Modal.info({
                title: '分析数据详情',
                content: (
                  <pre style={{ maxHeight: '400px', overflow: 'auto' }}>
                    {JSON.stringify(record.analysis_data, null, 2)}
                  </pre>
                ),
                width: 800,
              });
            }}
          >
            查看
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteAnalysis(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

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
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const color = type === 'full' ? 'green' : 'orange';
        const displayText = type === 'full' ? '完整' : '片段';
        return <Tag color={color}>{displayText}</Tag>;
      },
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
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: VideoSlice) => (
        <Space>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={async () => {
              try {
                const response = await videoSliceAPI.getSliceDownloadUrl(record.id);
                window.open(response.data.url, '_blank');
              } catch (error) {
                message.error('获取播放链接失败');
              }
            }}
          >
            播放
          </Button>
          <Button
            icon={<EyeOutlined />}
            onClick={() => {
              Modal.info({
                title: '切片详情',
                content: (
                  <div>
                    <p><strong>描述:</strong> {record.desc || record.description}</p>
                    <p><strong>标签:</strong> {record.tags?.join(', ')}</p>
                    <p><strong>文件路径:</strong> {record.sliced_file_path}</p>
                  </div>
                ),
                width: 600,
              });
            }}
          >
            详情
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteSlice(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div className="slice-management">
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Card title="视频切片管理">
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* 切片处理进度显示 */}
              {sliceProgress.isProcessing && (
                <Alert
                  message="切片处理中"
                  description={
                    <div>
                      <Progress percent={sliceProgress.progress} status="active" />
                      <p>{sliceProgress.message}</p>
                      {sliceProgress.taskId && (
                        <Text type="secondary">任务ID: {sliceProgress.taskId}</Text>
                      )}
                    </div>
                  }
                  type="info"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}
              
              {/* 切片处理完成或失败提示 */}
              {!sliceProgress.isProcessing && sliceProgress.progress === 100 && (
                <Alert
                  message="切片处理完成"
                  description={sliceProgress.message}
                  type="success"
                  showIcon
                  style={{ marginBottom: 16 }}
                  closable
                  onClose={() => setSliceProgress(prev => ({ ...prev, progress: 0, message: '' }))}
                />
              )}
              
              {!sliceProgress.isProcessing && sliceProgress.progress > 0 && sliceProgress.progress < 100 && (
                <Alert
                  message="切片处理失败"
                  description={sliceProgress.message}
                  type="error"
                  showIcon
                  style={{ marginBottom: 16 }}
                  closable
                  onClose={() => setSliceProgress(prev => ({ ...prev, progress: 0, message: '' }))}
                />
              )}
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
                <Col span={8}>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setValidateModalVisible(true)}
                    disabled={!selectedVideo}
                  >
                    验证切片数据
                  </Button>
                </Col>
              </Row>

              {selectedVideo && (
                <Tabs defaultActiveKey="analyses">
                  <TabPane tab="分析数据" key="analyses">
                    <Table
                      columns={analysisColumns}
                      dataSource={analyses}
                      rowKey="id"
                      loading={loading}
                      pagination={false}
                    />
                  </TabPane>
                  <TabPane tab="切片结果" key="slices">
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
                                  {
                                    title: '操作',
                                    key: 'actions',
                                    render: (subSlice: VideoSubSlice) => (
                                      <Space>
                                        <Button
                                          type="primary"
                                          size="small"
                                          icon={<PlayCircleOutlined />}
                                          onClick={async () => {
                                            try {
                                              const response = await videoSliceAPI.getSubSliceDownloadUrl(subSlice.id);
                                              window.open(response.data.url, '_blank');
                                            } catch (error) {
                                              message.error('获取播放链接失败');
                                            }
                                          }}
                                        >
                                          播放
                                        </Button>
                                        <Button
                                          danger
                                          size="small"
                                          icon={<DeleteOutlined />}
                                          onClick={() => handleDeleteSubSlice(subSlice.id, record.id)}
                                        >
                                          删除
                                        </Button>
                                      </Space>
                                    ),
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
                  </TabPane>
                </Tabs>
              )}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 验证数据模态框 */}
      <Modal
        title="验证切片数据"
        open={validateModalVisible}
        onOk={handleValidateData}
        onCancel={() => setValidateModalVisible(false)}
        width={800}
        confirmLoading={loading}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            message="请输入LLM生成的JSON数据"
            description="数据格式应为数组，包含切片信息。每个切片至少需要包含cover_title、title、desc、start、end和chapters字段。"
            type="info"
            showIcon
          />
          
          <Form form={form} layout="vertical">
            <Form.Item
              label="封面标题"
              name="cover_title"
              rules={[{ required: true, message: '请输入封面标题' }]}
            >
              <Input
                value={coverTitle}
                onChange={(e) => setCoverTitle(e.target.value)}
                placeholder="输入封面标题，用于分组管理"
              />
            </Form.Item>
            
            <Form.Item
              label="JSON数据"
              name="json_data"
              rules={[{ required: true, message: '请输入JSON数据' }]}
            >
              <TextArea
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                placeholder="粘贴LLM生成的JSON数据..."
                rows={15}
                style={{ fontFamily: 'monospace' }}
              />
            </Form.Item>
          </Form>
        </Space>
      </Modal>

      {/* 处理切片模态框 */}
      <Modal
        title="处理视频切片"
        open={processModalVisible}
        onOk={handleProcessSlices}
        onCancel={() => setProcessModalVisible(false)}
        confirmLoading={loading}
      >
        {selectedAnalysis && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              message="确认处理切片"
              description={`即将处理 ${selectedAnalysis.analysis_data.length} 个切片，这可能需要一些时间。`}
              type="warning"
              showIcon
            />
            
            <div>
              <Text strong>封面标题：</Text>
              <Text>{selectedAnalysis.cover_title}</Text>
            </div>
            
            <div>
              <Text strong>切片数量：</Text>
              <Text>{selectedAnalysis.analysis_data.length}</Text>
            </div>
            
            <Divider />
            
            <div>
              <Text strong>切片预览：</Text>
              <div style={{ maxHeight: '200px', overflow: 'auto', marginTop: '8px' }}>
                {selectedAnalysis.analysis_data.slice(0, 3).map((slice: SliceData, index: number) => (
                  <div key={index} style={{ marginBottom: '8px', padding: '8px', border: '1px solid #d9d9d9', borderRadius: '4px' }}>
                    <Text strong>{slice.cover_title}</Text>
                    <br />
                    <Text type="secondary">{slice.title}</Text>
                    <br />
                    <Text type="secondary">{slice.start} - {slice.end}</Text>
                    <br />
                    {slice.chapters && slice.chapters.length > 0 && (
                      <Text type="secondary">章节: {slice.chapters.length} 个</Text>
                    )}
                  </div>
                ))}
                {selectedAnalysis.analysis_data.length > 3 && (
                  <Text type="secondary">... 还有 {selectedAnalysis.analysis_data.length - 3} 个切片</Text>
                )}
              </div>
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default SliceManagement;