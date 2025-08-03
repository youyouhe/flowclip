import React, { useState, useEffect } from 'react';
import { Table, Button, Card, Space, Modal, Form, Input, message, Tag, Popconfirm } from 'antd';
import { PlusOutlined, EyeOutlined, EditOutlined, DeleteOutlined, FolderOutlined } from '@ant-design/icons';
import { projectAPI } from '../services/api';
import { useNavigate } from 'react-router-dom';

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

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const response = await projectAPI.getProjects();
      setProjects(response.data);
    } catch (error) {
      message.error('获取项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

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

      <Card>
        <Table
          columns={columns}
          dataSource={projects}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 个项目` }}
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