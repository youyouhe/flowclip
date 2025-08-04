import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Row, Col, Statistic, Tag, Button, Table, Space, Modal, Form, Input, message, Tabs, Typography, Divider } from 'antd';
import { 
  ArrowLeftOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  VideoCameraOutlined, 
  PlayCircleOutlined, 
  FileTextOutlined,
  FolderOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import { projectAPI } from '../services/api';
import { videoAPI } from '../services/api';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at?: string;
  video_count: number;
  completed_videos: number;
  total_slices: number;
}

interface Video {
  id: number;
  title: string;
  description?: string;
  url?: string;
  filename?: string;
  duration?: number;
  file_size?: number;
  thumbnail_url?: string;
  status: string;
  download_progress: number;
  created_at: string;
  updated_at?: string;
  processing_stage?: string;
  processing_progress?: number;
  processing_message?: string;
}

const ProjectDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [form] = Form.useForm();

  const fetchProject = async () => {
    if (!id) return;
    
    setLoading(true);
    try {
      const response = await projectAPI.getProject(parseInt(id));
      setProject(response.data);
    } catch (error) {
      message.error('获取项目详情失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchVideos = async () => {
    if (!id) return;
    
    setVideosLoading(true);
    try {
      const response = await projectAPI.getProjectVideos(parseInt(id));
      setVideos(response.data);
    } catch (error) {
      message.error('获取项目视频失败');
    } finally {
      setVideosLoading(false);
    }
  };

  useEffect(() => {
    fetchProject();
    fetchVideos();
  }, [id]);

  const handleUpdateProject = async (values: any) => {
    if (!project) return;
    
    try {
      await projectAPI.updateProject(project.id, values);
      message.success('项目更新成功');
      setEditModalVisible(false);
      fetchProject();
    } catch (error) {
      message.error('项目更新失败');
    }
  };

  const handleDeleteProject = async () => {
    if (!project) return;
    
    try {
      await projectAPI.deleteProject(project.id);
      message.success('项目删除成功');
      navigate('/dashboard/projects');
    } catch (error) {
      message.error('项目删除失败');
    }
  };

  const showEditModal = () => {
    if (!project) return;
    form.setFieldsValue({
      name: project.name,
      description: project.description,
    });
    setEditModalVisible(true);
  };

  const getStatusColor = (status: string) => {
    const colorMap = {
      active: 'green',
      completed: 'blue',
      paused: 'orange',
      archived: 'gray',
      pending: 'default',
      downloading: 'processing',
      downloaded: 'success',
      processing: 'warning',
      failed: 'error',
    };
    return colorMap[status as keyof typeof colorMap] || 'default';
  };

  const getStatusText = (status: string) => {
    const textMap = {
      active: '活跃',
      completed: '已完成',
      paused: '暂停',
      archived: '已归档',
      pending: '待处理',
      downloading: '下载中',
      downloaded: '已下载',
      processing: '处理中',
      failed: '失败',
    };
    return textMap[status as keyof typeof textMap] || status;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  const videoColumns = [
    {
      title: '视频标题',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: Video) => (
        <div className="flex items-center">
          <VideoCameraOutlined className="mr-2 text-blue-500" />
          <div>
            <div className="font-medium">{title || '未命名视频'}</div>
            <div className="text-xs text-gray-500">
              {record.filename && `文件: ${record.filename}`}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: Video) => {
        let icon = <ClockCircleOutlined />;
        if (status === 'completed') icon = <CheckCircleOutlined />;
        else if (status === 'processing' || status === 'downloading') icon = <LoadingOutlined />;
        
        return (
          <Tag color={getStatusColor(status)} icon={icon}>
            {getStatusText(status)}
          </Tag>
        );
      },
    },
    {
      title: '处理进度',
      key: 'progress',
      render: (record: Video) => {
        const progress = record.processing_progress || 0;
        return (
          <div className="w-full">
            <div className="flex justify-between text-xs mb-1">
              <span>{progress.toFixed(1)}%</span>
              <span>{record.processing_stage || '等待中'}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-500 h-2 rounded-full transition-all duration-300" 
                style={{ width: `${progress}%` }}
              />
            </div>
            {record.processing_message && (
              <div className="text-xs text-gray-500 mt-1 truncate">
                {record.processing_message}
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: '时长',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => duration ? formatDuration(duration) : '-',
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => size ? formatFileSize(size) : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
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
            查看
          </Button>
        </Space>
      ),
    },
  ];

  if (loading || !project) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingOutlined className="text-4xl" />
        <span className="ml-4">加载中...</span>
      </div>
    );
  }

  return (
    <div>
      {/* 页面头部 */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center">
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/dashboard/projects')}
            className="mr-4"
          >
            返回
          </Button>
          <div>
            <Title level={2} className="mb-0">
              <FolderOutlined className="mr-2" />
              {project.name}
            </Title>
            <Text type="secondary">项目ID: {project.id}</Text>
          </div>
        </div>
        <Space>
          <Button icon={<EditOutlined />} onClick={showEditModal}>
            编辑
          </Button>
          <Button 
            danger 
            icon={<DeleteOutlined />}
            onClick={handleDeleteProject}
          >
            删除
          </Button>
        </Space>
      </div>

      {/* 项目统计信息 */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="视频总数"
              value={project.video_count}
              prefix={<VideoCameraOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="已完成视频"
              value={project.completed_videos}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="处理进度"
              value={project.video_count > 0 ? Math.round((project.completed_videos / project.video_count) * 100) : 0}
              suffix="%"
              prefix={<LoadingOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="切片总数"
              value={project.total_slices}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 项目详细信息 */}
      <Card className="mb-6">
        <Title level={4}>项目信息</Title>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12}>
            <div>
              <Text strong>项目名称：</Text>
              <Text>{project.name}</Text>
            </div>
          </Col>
          <Col xs={24} sm={12}>
            <div>
              <Text strong>项目状态：</Text>
              <Tag color={getStatusColor(project.status)}>
                {getStatusText(project.status)}
              </Tag>
            </div>
          </Col>
          <Col xs={24} sm={12}>
            <div>
              <Text strong>创建时间：</Text>
              <Text>{new Date(project.created_at).toLocaleString('zh-CN')}</Text>
            </div>
          </Col>
          {project.updated_at && (
            <Col xs={24} sm={12}>
              <div>
                <Text strong>更新时间：</Text>
                <Text>{new Date(project.updated_at).toLocaleString('zh-CN')}</Text>
              </div>
            </Col>
          )}
          {project.description && (
            <Col xs={24}>
              <div>
                <Text strong>项目描述：</Text>
                <div className="mt-2">
                  <Text>{project.description}</Text>
                </div>
              </div>
            </Col>
          )}
        </Row>
      </Card>

      {/* 视频列表 */}
      <Card>
        <Title level={4}>项目视频</Title>
        <Table
          columns={videoColumns}
          dataSource={videos}
          rowKey="id"
          loading={videosLoading}
          pagination={{ 
            pageSize: 10, 
            showTotal: (total) => `共 ${total} 个视频`,
            showSizeChanger: true,
            showQuickJumper: true,
          }}
        />
      </Card>

      {/* 编辑项目模态框 */}
      <Modal
        title="编辑项目"
        open={editModalVisible}
        onOk={() => form.submit()}
        onCancel={() => setEditModalVisible(false)}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="项目名称" maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea
              placeholder="项目描述（可选）"
              rows={3}
              maxLength={500}
              showCount
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectDetail;