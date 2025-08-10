import React, { useState, useEffect } from 'react';
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
  Form
} from 'antd';
import { 
  PlayCircleOutlined, 
  EyeOutlined, 
  DeleteOutlined, 
  DownloadOutlined,
  VideoCameraAddOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';
import { videoAPI } from '../services/api';
import { videoSliceAPI } from '../services/api';
import { capcutAPI } from '../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

interface Video {
  id: number;
  title: string;
  project_id: number;
  status: string;
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
}

const CapCut: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [slices, setSlices] = useState<VideoSlice[]>([]);
  const [loading, setLoading] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [draftFolder, setDraftFolder] = useState('');
  const [capcutModalVisible, setCapcutModalVisible] = useState(false);
  const [selectedSlice, setSelectedSlice] = useState<VideoSlice | null>(null);
  const [capcutStatus, setCapcutStatus] = useState<'online' | 'offline' | 'checking'>('checking');
const [capcutProgress, setCapcutProgress] = useState({
  isProcessing: false,
  progress: 0,
  message: '',
  taskId: ''
});

  useEffect(() => {
    loadVideos();
    checkCapCutStatus();
  }, []);

  const checkCapCutStatus = async () => {
    try {
      const response = await capcutAPI.getStatus();
      setCapcutStatus(response.data.status === 'online' ? 'online' : 'offline');
    } catch (error) {
      setCapcutStatus('offline');
    }
  };

  useEffect(() => {
    if (selectedVideo) {
      loadSlices();
    }
  }, [selectedVideo]);

  const loadVideos = async () => {
    try {
      setVideosLoading(true);
      const response = await videoAPI.getVideos({ status: 'completed' });
      const videosData = response.data.videos || response.data;
      const completedVideos = videosData.filter((video: Video) => 
        video.status === 'completed'
      );
      setVideos(completedVideos);
    } catch (error) {
      message.error('加载视频列表失败');
    } finally {
      setVideosLoading(false);
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
    // 从环境变量获取默认的draft folder
    const defaultDraftFolder = import.meta.env.VITE_CAPCUT_DRAFT_FOLDER || '';
    setDraftFolder(defaultDraftFolder);
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
            ? {...s, capcut_status: 'completed', capcut_draft_url: response.data.draft_url} 
            : s
        ));
        
        setCapcutProgress({
          isProcessing: false,
          progress: 100,
          message: 'CapCut导出完成',
          taskId: null
        });
        
        message.success('CapCut导出完成');
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
        taskId: null
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadDraft = async (slice: VideoSlice) => {
    if (!slice.capcut_draft_url) {
      message.error('草稿文件尚未生成');
      return;
    }
    
    try {
      // 这里应该调用后端API获取下载链接
      message.success('正在准备下载...');
      // 模拟下载
      window.open(slice.capcut_draft_url, '_blank');
    } catch (error) {
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
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: VideoSlice) => (
        <Space>
          <Button
            type="primary"
            icon={<VideoCameraAddOutlined />}
            onClick={() => handleCapCutExport(record)}
            disabled={capcutStatus !== 'online'}
            title={capcutStatus !== 'online' ? 'CapCut服务不可用' : ''}
          >
            CapCut导出
          </Button>
          {record.capcut_status === 'completed' && (
            <Button
              icon={<DownloadOutlined />}
              onClick={() => handleDownloadDraft(record)}
            >
              下载
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
          <Card title="CapCut导出管理">
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* CapCut服务状态 */}
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col>
                  <Tag color={capcutStatus === 'online' ? 'success' : capcutStatus === 'checking' ? 'processing' : 'error'}>
                    CapCut服务: {capcutStatus === 'online' ? '在线' : capcutStatus === 'checking' ? '检查中...' : '离线'}
                  </Tag>
                  <Button size="small" onClick={checkCapCutStatus} style={{ marginLeft: 8 }}>
                    刷新
                  </Button>
                </Col>
              </Row>
              
              {/* CapCut处理进度显示 */}
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
              
              {/* CapCut处理完成或失败提示 */}
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
    </div>
  );
};

export default CapCut;