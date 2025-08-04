import React, { useState, useEffect } from 'react';
import { 
  Table, 
  Button, 
  Card, 
  Space, 
  Modal, 
  Form, 
  Input, 
  message, 
  Tag, 
  Popconfirm, 
  Select, 
  Row, 
  Col,
  DatePicker 
} from 'antd';
import { 
  PlusOutlined, 
  EyeOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  FolderOutlined, 
  SearchOutlined, 
  FilterOutlined, 
  ClearOutlined,
  ReloadOutlined 
} from '@ant-design/icons';
import { projectAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at?: string;
  video_count?: number;
}

const Projects: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  
  // 筛选状态
  const [filters, setFilters] = useState({
    status: undefined as string | undefined,
    search: '',
    start_date: undefined as string | undefined,
    end_date: undefined as string | undefined,
    min_video_count: undefined as number | undefined,
    max_video_count: undefined as number | undefined,
    page: 1,
    page_size: 10
  });
  
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: 10,
    total_pages: 0
  });

  const fetchProjects = async () => {
    setLoading(true);
    try {
      // 构建查询参数
      const params: any = {};
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.min_video_count !== undefined) params.min_video_count = filters.min_video_count;
      if (filters.max_video_count !== undefined) params.max_video_count = filters.max_video_count;
      if (filters.page) params.page = filters.page;
      if (filters.page_size) params.page_size = filters.page_size;
      
      const response = await projectAPI.getProjects(params);
      setProjects(response.data.projects || response.data);
      
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
    } catch (error) {
      message.error('获取项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [filters]);

  const handleCreateProject = async (values: any) => {
    try {
      await projectAPI.createProject(values);
      message.success('项目创建成功');
      setModalVisible(false);
      form.resetFields();
      fetchProjects();
    } catch (error) {
      message.error('项目创建失败');
    }
  };

  const handleUpdateProject = async (values: any) => {
    if (!editingProject) return;
    
    try {
      await projectAPI.updateProject(editingProject.id, values);
      message.success('项目更新成功');
      setModalVisible(false);
      setEditingProject(null);
      form.resetFields();
      fetchProjects();
    } catch (error) {
      message.error('项目更新失败');
    }
  };

  const handleDeleteProject = async (id: number) => {
    try {
      await projectAPI.deleteProject(id);
      message.success('项目删除成功');
      fetchProjects();
    } catch (error) {
      message.error('项目删除失败');
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
      status: undefined,
      search: '',
      start_date: undefined,
      end_date: undefined,
      min_video_count: undefined,
      max_video_count: undefined,
      page: 1,
      page_size: 10
    });
  };

  const showCreateModal = () => {
    setEditingProject(null);
    form.resetFields();
    setModalVisible(true);
  };

  const showEditModal = (project: Project) => {
    setEditingProject(project);
    form.setFieldsValue(project);
    setModalVisible(true);
  };

  const handleModalOk = () => {
    form.validateFields().then((values) => {
      if (editingProject) {
        handleUpdateProject(values);
      } else {
        handleCreateProject(values);
      }
    });
  };

  const columns = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <div className="flex items-center">
          <FolderOutlined className="mr-2 text-blue-500" />
          {name}
        </div>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '视频数量',
      dataIndex: 'video_count',
      key: 'video_count',
      render: (count: number) => count || 0,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap = {
          active: 'green',
          completed: 'blue',
          paused: 'orange',
          archived: 'gray',
        };
        return (
          <Tag color={colorMap[status as keyof typeof colorMap] || 'default'}>
            {status}
          </Tag>
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
      render: (_: any, record: Project) => (
        <Space size="middle">
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/dashboard/projects/${record.id}`)}
          >
            查看
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => showEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个项目吗？"
            onConfirm={() => handleDeleteProject(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">项目管理</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={showCreateModal}>
          创建新项目
        </Button>
      </div>

      {/* 筛选器 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={4}>
            <Select
              placeholder="项目状态"
              value={filters.status}
              onChange={(value) => handleFilterChange('status', value)}
              style={{ width: '100%' }}
              allowClear
            >
              <Select.Option value="active">活跃</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
              <Select.Option value="paused">暂停</Select.Option>
              <Select.Option value="archived">已归档</Select.Option>
            </Select>
          </Col>
          <Col span={4}>
            <Input.Group compact>
              <Input
                style={{ width: '50%' }}
                placeholder="最少视频数"
                type="number"
                value={filters.min_video_count}
                onChange={(e) => handleFilterChange('min_video_count', e.target.value ? parseInt(e.target.value) : undefined)}
              />
              <Input
                style={{ width: '50%' }}
                placeholder="最多视频数"
                type="number"
                value={filters.max_video_count}
                onChange={(e) => handleFilterChange('max_video_count', e.target.value ? parseInt(e.target.value) : undefined)}
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
          <Col span={6}>
            <Input
              placeholder="搜索项目名称或描述"
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              onPressEnter={fetchProjects}
            />
          </Col>
          <Col span={4}>
            <Space>
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={fetchProjects}
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
            </Space>
          </Col>
        </Row>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={projects}
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
        />
      </Card>

      <Modal
        title={editingProject ? '编辑项目' : '创建新项目'}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => {
          setModalVisible(false);
          setEditingProject(null);
          form.resetFields();
        }}
        okText={editingProject ? '更新' : '创建'}
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

export default Projects;