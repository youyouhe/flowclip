import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Button, Spin, Alert, Table, Tag, Typography } from 'antd';
import { PlusOutlined, PlayCircleOutlined, CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { dashboardAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { Text } = Typography;

interface DashboardStats {
  overview: {
    total_projects: number;
    total_videos: number;
    completed_videos: number;
    processing_videos: number;
    total_slices: number;
    failed_videos: number;
  };
  task_stats: {
    pending: number;
    running: number;
    success: number;
    failure: number;
  };
  recent_projects: Array<{
    id: number;
    name: string;
    description: string;
    created_at: string;
    video_count: number;
  }>;
  recent_activities: Array<{
    id: number;
    type: string;
    status: string;
    task_name: string;
    video_title: string;
    progress: number;
    created_at: string;
    message: string;
    error_message: string;
  }>;
}

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await dashboardAPI.getDashboardStats();
      setStats(response.data);
    } catch (err: any) {
      console.error('获取仪表盘数据失败:', err);
      setError(err.response?.data?.detail || '获取仪表盘数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'orange',
      running: 'blue',
      success: 'green',
      failure: 'red',
      completed: 'green',
      processing: 'blue',
      downloading: 'blue',
      failed: 'red'
    };
    return colors[status] || 'default';
  };

  const getStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      pending: '待处理',
      running: '运行中',
      success: '成功',
      failure: '失败',
      completed: '已完成',
      processing: '处理中',
      downloading: '下载中',
      failed: '失败'
    };
    return statusMap[status] || status;
  };

  const getTaskTypeText = (type: string) => {
    const typeMap: Record<string, string> = {
      download: '下载',
      extract_audio: '音频提取',
      split_audio: '音频分割',
      generate_srt: '字幕生成',
      process_complete: '完整处理'
    };
    return typeMap[type] || type;
  };

  const activityColumns = [
    {
      title: '任务类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => getTaskTypeText(type),
    },
    {
      title: '视频标题',
      dataIndex: 'video_title',
      key: 'video_title',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {getStatusText(status)}
        </Tag>
      ),
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress: number) => `${progress}%`,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  const projectColumns = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: any) => (
        <Button 
          type="link" 
          onClick={() => navigate(`/dashboard/projects/${record.id}`)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '视频数量',
      dataIndex: 'video_count',
      key: 'video_count',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
  ];

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchDashboardStats}>
              重试
            </Button>
          }
        />
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">仪表盘</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/dashboard/projects')}>
          创建新项目
        </Button>
      </div>

      <Row gutter={16} className="mb-6">
        <Col span={4}>
          <Card>
            <Statistic
              title="总项目数"
              value={stats.overview.total_projects}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="总视频数"
              value={stats.overview.total_videos}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="已完成视频"
              value={stats.overview.completed_videos}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="处理中视频"
              value={stats.overview.processing_videos}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="失败视频"
              value={stats.overview.failed_videos}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="总切片数"
              value={stats.overview.total_slices}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} className="mb-6">
        <Col span={12}>
          <Card title="任务状态统计">
            <Row gutter={16}>
              <Col span={6}>
                <Statistic
                  title="待处理"
                  value={stats.task_stats.pending}
                  valueStyle={{ color: '#fa8c16' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="运行中"
                  value={stats.task_stats.running}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="成功"
                  value={stats.task_stats.success}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="失败"
                  value={stats.task_stats.failure}
                  valueStyle={{ color: '#f5222d' }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="快速操作">
            <div className="space-y-2">
              <Button type="default" block onClick={() => navigate('/dashboard/projects')}>
                管理项目
              </Button>
              <Button type="default" block onClick={() => navigate('/dashboard/videos')}>
                管理视频
              </Button>
              <Button type="default" block onClick={() => navigate('/dashboard/llm-chat')}>
                LLM 聊天
              </Button>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="最近项目" extra={<Button type="link" onClick={() => navigate('/dashboard/projects')}>查看全部</Button>}>
            {stats.recent_projects.length > 0 ? (
              <Table
                dataSource={stats.recent_projects}
                columns={projectColumns}
                pagination={false}
                size="small"
                rowKey="id"
              />
            ) : (
              <div className="text-gray-500 text-center py-8">暂无项目</div>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="最近活动" extra={<Button type="link" onClick={fetchDashboardStats}>刷新</Button>}>
            {stats.recent_activities.length > 0 ? (
              <Table
                dataSource={stats.recent_activities}
                columns={activityColumns}
                pagination={false}
                size="small"
                rowKey="id"
              />
            ) : (
              <div className="text-gray-500 text-center py-8">暂无活动</div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;