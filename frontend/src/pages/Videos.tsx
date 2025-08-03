import React, { useState, useEffect, useRef } from 'react';
import { Table, Button, Card, Space, Modal, Form, Input, Select, message, Tag, Progress, Popconfirm, Upload } from 'antd';
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined, DeleteOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import { videoAPI, projectAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { wsService, startHeartbeat, stopHeartbeat } from '../services/websocket';

interface Video {
  id: number;
  title: string;
  url: string;
  project_id: number;
  filename?: string;
  duration?: number;
  file_size?: number;
  thumbnail_url?: string;
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

  const fetchVideos = async () => {
    setLoading(true);
    try {
      const response = await videoAPI.getVideos();
      setVideos(response.data);
      
      // 获取每个视频的缩略图URL
      const thumbnailPromises = response.data.map(async (video: Video) => {
        if (video.url) {
          try {
            const thumbnailResponse = await videoAPI.getThumbnailDownloadUrl(video.id);
            return { id: video.id, url: thumbnailResponse.data.download_url };
          } catch (error) {
            console.error(`获取视频 ${video.id} 缩略图失败:`, error);
            return { id: video.id, url: null };
          }
        }
        return { id: video.id, url: null };
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
    }, 10000); // 每10秒请求一次状态更新
    
    return () => {
      cleanupWebSocket();
      clearInterval(statusUpdateInterval); // 清理定时器
    };
  }, []);

  // Update the ref whenever the videos state changes
  useEffect(() => {
    videosRef.current = videos;
  }, [videos]);

  // 当视频列表更新时，订阅所有视频的进度更新
  useEffect(() => {
    if (videos.length > 0 && wsService.connected) {
      console.log('📡 [Videos] Subscribing to all videos progress updates');
      videos.forEach(video => {
        wsService.subscribeVideoProgress(video.id);
      });
    }
  }, [videos]);

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
      fetchVideos();
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

  const setupWebSocket = () => {
    console.log('🔌 [Videos] Setting up WebSocket...');
    
    const token = localStorage.getItem('token');
    console.log('🔌 [Videos] Token from localStorage:', token ? `${token.substring(0, 20)}...` : 'null');
    
    if (!token) {
      console.log('❌ [Videos] No token found, skipping WebSocket connection');
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
      // 连接成功后，订阅所有当前视频的进度更新
      videos.forEach(video => {
        wsService.subscribeVideoProgress(video.id);
      });
    });

    wsService.on('progress_update', (data: { video_id: number; video_status?: string; download_progress?: number; processing_progress?: number; processing_stage?: string; processing_message?: string }) => {
      console.log('📊 [Videos] Progress update received:', data);
      console.log('📊 [Videos] Update video ID:', data.video_id);
      
      // 查找对应的视频并更新，使用ref获取最新状态
      const currentVideos = videosRef.current;
      const videoIndex = currentVideos.findIndex(v => v.id === data.video_id);
      if (videoIndex !== -1) {
        console.log('✅ [Videos] Found video in list, updating...');
        setVideos(prev => {
          const updated = [...prev];
          updated[videoIndex] = {
            ...updated[videoIndex],
            status: data.video_status || updated[videoIndex].status,
            download_progress: data.download_progress || updated[videoIndex].download_progress,
            processing_progress: data.processing_progress || updated[videoIndex].processing_progress,
            processing_stage: data.processing_stage || updated[videoIndex].processing_stage,
            processing_message: data.processing_message || updated[videoIndex].processing_message
          };
          return updated;
        });
        
        // 如果下载完成，刷新列表以获取完整信息
        if (data.video_status === 'completed' && data.download_progress === 100) {
          console.log('📥 [Videos] Video download completed, refreshing list...');
          setTimeout(() => {
            fetchVideos();
          }, 2000);
        }
      } else {
        console.log('⚠️ [Videos] Video not found in current list');
        // If video not found, it might be a new video being downloaded.
        // Fetch videos again to get the new video into the list.
        fetchVideos(); 
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

  const columns = [
    {
      title: '视频标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title: string, record: Video) => (
        <div className="flex items-center">
          {thumbnailUrls[record.id] ? (
            <img
              src={thumbnailUrls[record.id]}
              alt={title}
              className="w-16 h-9 object-cover rounded mr-2"
              onError={(e) => {
                // 如果图片加载失败，隐藏图片元素
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
              }}
            />
          ) : record.thumbnail_url ? (
            <img
              src={record.thumbnail_url}
              alt={title}
              className="w-16 h-9 object-cover rounded mr-2"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
              }}
            />
          ) : null}
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
        const statusMap = {
          pending: { color: 'orange', text: '等待中' },
          downloading: { color: 'blue', text: '下载中' },
          processing: { color: 'cyan', text: '处理中' },
          completed: { color: 'green', text: '已完成' },
          failed: { color: 'red', text: '失败' },
        };
        
        const statusConfig = statusMap[status as keyof typeof statusMap] || { color: 'default', text: status };
        
        return (
          <div>
            <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
            {status === 'downloading' && (
              <div className="mt-1">
                <Progress
                  percent={Math.round(record.download_progress)}
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
            disabled={record.status === 'downloading'}
          >
            <Button type="link" danger icon={<DeleteOutlined />} disabled={record.status === 'downloading'}>
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

      <Card>
        <Table
          columns={columns}
          dataSource={videos}
          rowKey="id"
          loading={loading}
          pagination={{ 
            pageSize: 10, 
            showTotal: (total) => `共 ${total} 个视频`,
            showSizeChanger: true,
            showQuickJumper: true,
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
