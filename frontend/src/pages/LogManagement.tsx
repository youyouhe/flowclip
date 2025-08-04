import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Table, 
  Button, 
  Space, 
  Input, 
  Select, 
  DatePicker, 
  Tag, 
  Modal, 
  message, 
  Spin, 
  Typography, 
  Row, 
  Col, 
  Statistic, 
  Alert,
  Tooltip,
  Popconfirm,
  Tabs,
  Badge,
  Descriptions,
  Timeline
} from 'antd';
import { 
  DeleteOutlined, 
  SearchOutlined, 
  FilterOutlined, 
  ClearOutlined,
  ReloadOutlined,
  BarChartOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { logAPI, videoAPI } from '../services/api';
import { wsService } from '../services/websocket';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;
const { Search } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

interface ProcessingLog {
  id: number;
  task_id: number;
  task_name: string;
  task_type: string;
  video_id: number;
  video_title: string;
  old_status: string;
  new_status: string;
  message: string;
  details: Record<string, any>;
  created_at: string;
  level: string;
}

interface Video {
  id: number;
  title: string;
  status: string;
}

interface LogStatistics {
  by_status: Array<{ status: string; count: number }>;
  by_task_type: Array<{ task_type: string; count: number }>;
  by_date: Array<{ date: string; count: number }>;
  total_logs: number;
}

interface VideoLogSummary {
  video_id: number;
  video_title: string;
  task_statistics: Array<{
    task_type: string;
    status: string;
    count: number;
    last_updated: string;
  }>;
  recent_logs: ProcessingLog[];
}

const LogManagement: React.FC = () => {
  const [logs, setLogs] = useState<ProcessingLog[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState<LogStatistics | null>(null);
  const [videoSummary, setVideoSummary] = useState<VideoLogSummary | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [selectedLog, setSelectedLog] = useState<ProcessingLog | null>(null);
  const [logDetailVisible, setLogDetailVisible] = useState(false);
  
  // 筛选状态
  const [filters, setFilters] = useState({
    video_id: undefined as number | undefined,
    task_type: undefined as string | undefined,
    status: undefined as string | undefined,
    level: 'INFO',
    search: '',
    start_date: undefined as string | undefined,
    end_date: undefined as string | undefined,
    page: 1,
    page_size: 50
  });
  
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: 50,
    total_pages: 0
  });

  useEffect(() => {
    loadVideos();
    loadLogs();
    loadStatistics();
    
    // 设置WebSocket监听
    wsService.on('log_update', handleLogUpdate);
    
    return () => {
      wsService.off('log_update', handleLogUpdate);
    };
  }, []);

  useEffect(() => {
    loadLogs();
  }, [filters]);

  const handleLogUpdate = (data: any) => {
    // 实时更新日志
    if (data.type === 'log_update') {
      loadLogs();
      loadStatistics();
    }
  };

  const loadVideos = async () => {
    try {
      const response = await videoAPI.getVideos();
      // 确保response.data是数组，如果不是则设置为空数组
      const videosData = Array.isArray(response.data) ? response.data : [];
      setVideos(videosData);
    } catch (error) {
      message.error('加载视频列表失败');
      setVideos([]); // 出错时设置为空数组
    }
  };

  const loadLogs = async () => {
    try {
      setLoading(true);
      const response = await logAPI.getProcessingLogs(filters);
      
      setLogs(response.data.logs);
      setPagination(response.data.pagination);
    } catch (error) {
      message.error('加载日志失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await logAPI.getLogsStatistics({
        video_id: filters.video_id,
        start_date: filters.start_date,
        end_date: filters.end_date
      });
      
      setStatistics(response.data.statistics);
    } catch (error) {
      console.error('加载统计信息失败:', error);
    }
  };

  const loadVideoSummary = async (videoId: number) => {
    try {
      setLoading(true);
      const response = await logAPI.getVideoLogsSummary(videoId);
      setVideoSummary(response.data);
      setSelectedVideo(videoId);
    } catch (error) {
      message.error('加载视频日志汇总失败');
    } finally {
      setLoading(false);
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
      video_id: undefined,
      task_type: undefined,
      status: undefined,
      level: 'INFO',
      search: '',
      start_date: undefined,
      end_date: undefined,
      page: 1,
      page_size: 50
    });
  };

  const handleDeleteLog = async (logId: number) => {
    try {
      await logAPI.deleteLog(logId);
      message.success('日志删除成功');
      loadLogs();
      loadStatistics();
    } catch (error) {
      message.error('删除日志失败');
    }
  };

  const handleDeleteVideoLogs = async (videoId: number) => {
    try {
      await logAPI.deleteVideoLogs(videoId);
      message.success('视频日志删除成功');
      loadLogs();
      loadStatistics();
      if (selectedVideo === videoId) {
        setVideoSummary(null);
        setSelectedVideo(null);
      }
    } catch (error) {
      message.error('删除视频日志失败');
    }
  };

  const showLogDetail = (log: ProcessingLog) => {
    setSelectedLog(log);
    setLogDetailVisible(true);
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'SUCCESS': 'green',
      'PENDING': 'blue',
      'PROCESSING': 'orange',
      'FAILURE': 'red',
      'CANCELLED': 'gray'
    };
    return colors[status] || 'default';
  };

  const getStatusIcon = (status: string) => {
    const icons: Record<string, React.ReactNode> = {
      'SUCCESS': <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      'PENDING': <ClockCircleOutlined style={{ color: '#1890ff' }} />,
      'PROCESSING': <InfoCircleOutlined style={{ color: '#fa8c16' }} />,
      'FAILURE': <ExclamationCircleOutlined style={{ color: '#f5222d' }} />,
      'CANCELLED': <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
    };
    return icons[status] || <InfoCircleOutlined />;
  };

  const getLevelColor = (level: string) => {
    const colors: Record<string, string> = {
      'ERROR': 'red',
      'WARN': 'orange',
      'INFO': 'blue',
      'DEBUG': 'gray'
    };
    return colors[level] || 'default';
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (level: string) => (
        <Tag color={getLevelColor(level)}>
          {level}
        </Tag>
      ),
    },
    {
      title: '视频',
      dataIndex: 'video_title',
      key: 'video_title',
      width: 200,
      ellipsis: true,
    },
    {
      title: '任务类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 120,
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 150,
      ellipsis: true,
    },
    {
      title: '状态变化',
      key: 'status_change',
      width: 150,
      render: (record: ProcessingLog) => (
        <Space>
          {record.old_status && (
            <Tag color={getStatusColor(record.old_status)}>
              {record.old_status}
            </Tag>
          )}
          <span>→</span>
          <Tag color={getStatusColor(record.new_status)}>
            {record.new_status}
          </Tag>
        </Space>
      ),
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (record: ProcessingLog) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => showLogDetail(record)}
          >
            详情
          </Button>
          <Popconfirm
            title="确定删除这条日志吗？"
            onConfirm={() => handleDeleteLog(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="log-management">
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Card>
            <Title level={3}>
              <FileTextOutlined /> 日志管理
            </Title>
          </Card>
        </Col>
      </Row>

      {/* 统计信息 */}
      {statistics && (
        <Row gutter={[24, 24]} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总日志数"
                value={statistics.total_logs}
                prefix={<FileTextOutlined />}
              />
            </Card>
          </Col>
          <Col span={18}>
            <Card title="状态分布">
              <Row gutter={16}>
                {statistics.by_status.map((stat) => (
                  <Col span={6} key={stat.status}>
                    <Statistic
                      title={stat.status}
                      value={stat.count}
                      prefix={getStatusIcon(stat.status)}
                      valueStyle={{ color: getStatusColor(stat.status) }}
                    />
                  </Col>
                ))}
              </Row>
            </Card>
          </Col>
        </Row>
      )}

      {/* 筛选器 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={4}>
            <Select
              placeholder="选择视频"
              value={filters.video_id}
              onChange={(value) => handleFilterChange('video_id', value)}
              style={{ width: '100%' }}
              allowClear
            >
              {Array.isArray(videos) && videos.map((video) => (
                <Option key={video.id} value={video.id}>
                  {video.title}
                </Option>
              ))}
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="任务类型"
              value={filters.task_type}
              onChange={(value) => handleFilterChange('task_type', value)}
              style={{ width: '100%' }}
              allowClear
            >
              <Option value="download">下载</Option>
              <Option value="extract_audio">音频提取</Option>
              <Option value="split_audio">音频分割</Option>
              <Option value="generate_srt">字幕生成</Option>
              <Option value="video_slicing">视频切片</Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="状态"
              value={filters.status}
              onChange={(value) => handleFilterChange('status', value)}
              style={{ width: '100%' }}
              allowClear
            >
              <Option value="SUCCESS">成功</Option>
              <Option value="PENDING">待处理</Option>
              <Option value="PROCESSING">处理中</Option>
              <Option value="FAILURE">失败</Option>
              <Option value="CANCELLED">已取消</Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="日志级别"
              value={filters.level}
              onChange={(value) => handleFilterChange('level', value)}
              style={{ width: '100%' }}
            >
              <Option value="ERROR">ERROR</Option>
              <Option value="WARN">WARN</Option>
              <Option value="INFO">INFO</Option>
              <Option value="DEBUG">DEBUG</Option>
            </Select>
          </Col>
          <Col span={4}>
            <RangePicker
              style={{ width: '100%' }}
              onChange={handleDateRangeChange}
              placeholder={['开始日期', '结束日期']}
            />
          </Col>
          <Col span={4}>
            <Search
              placeholder="搜索日志"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              onSearch={() => loadLogs()}
              enterButton
            />
          </Col>
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col>
            <Space>
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={loadLogs}
                loading={loading}
              >
                搜索
              </Button>
              <Button
                icon={<ClearOutlined />}
                onClick={clearFilters}
              >
                清除筛选
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={loadLogs}
                loading={loading}
              >
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 日志列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={logs}
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
                page_size: pageSize || 50
              }));
            },
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 日志详情弹窗 */}
      <Modal
        title="日志详情"
        open={logDetailVisible}
        onCancel={() => setLogDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedLog && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="日志ID">{selectedLog.id}</Descriptions.Item>
            <Descriptions.Item label="任务ID">{selectedLog.task_id}</Descriptions.Item>
            <Descriptions.Item label="视频">{selectedLog.video_title}</Descriptions.Item>
            <Descriptions.Item label="任务类型">{selectedLog.task_type}</Descriptions.Item>
            <Descriptions.Item label="任务名称">{selectedLog.task_name}</Descriptions.Item>
            <Descriptions.Item label="时间">
              {dayjs(selectedLog.created_at).format('YYYY-MM-DD HH:mm:ss')}
            </Descriptions.Item>
            <Descriptions.Item label="级别">
              <Tag color={getLevelColor(selectedLog.level)}>
                {selectedLog.level}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态变化">
              <Space>
                {selectedLog.old_status && (
                  <Tag color={getStatusColor(selectedLog.old_status)}>
                    {selectedLog.old_status}
                  </Tag>
                )}
                <span>→</span>
                <Tag color={getStatusColor(selectedLog.new_status)}>
                  {selectedLog.new_status}
                </Tag>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="消息" span={2}>
              {selectedLog.message}
            </Descriptions.Item>
            <Descriptions.Item label="详细信息" span={2}>
              <pre style={{ 
                background: '#f5f5f5', 
                padding: '8px', 
                borderRadius: '4px',
                fontSize: '12px',
                maxHeight: '200px',
                overflow: 'auto'
              }}>
                {JSON.stringify(selectedLog.details, null, 2)}
              </pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default LogManagement;