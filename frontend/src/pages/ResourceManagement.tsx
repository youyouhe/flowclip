import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Table, 
  Button, 
  Space, 
  message, 
  Modal, 
  Form, 
  Input, 
  Select, 
  Upload, 
  Tag, 
  Row, 
  Col, 
  Typography, 
  Divider,
  Alert,
  Spin,
  Popconfirm,
  Badge,
  Tooltip
} from 'antd';
import { 
  UploadOutlined, 
  DeleteOutlined, 
  EditOutlined, 
  EyeOutlined, 
  TagOutlined,
  PlayCircleOutlined,
  PictureOutlined,
  AudioOutlined,
  VideoCameraOutlined,
  SearchOutlined,
  FilterOutlined
} from '@ant-design/icons';
import { 
  resourceAPI, 
  Resource as ResourceType, 
  ResourceTag 
} from '../services/api';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

interface Resource {
  id: number;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  file_type: string;
  duration?: number;
  width?: number;
  height?: number;
  description?: string;
  is_public: boolean;
  download_count: number;
  view_count: number;
  created_at: string;
  tags: ResourceTag[];
}

const ResourceManagement: React.FC = () => {
  const [resources, setResources] = useState<Resource[]>([]);
  const [tags, setTags] = useState<ResourceTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [tagModalVisible, setTagModalVisible] = useState(false);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [form] = Form.useForm();
  const [tagForm] = Form.useForm();
  const [searchText, setSearchText] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<number[]>([]);

  // 加载资源列表
  const loadResources = async () => {
    try {
      setLoading(true);
      const response = await resourceAPI.getResources({
        file_type: fileTypeFilter === 'all' ? undefined : fileTypeFilter,
        search: searchText || undefined,
        tags: selectedTags.length > 0 ? selectedTags.join(',') : undefined,
        page: 1,
        page_size: 100
      });
      setResources(response.data.resources);
    } catch (error) {
      message.error('加载资源列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载标签列表
  const loadTags = async () => {
    try {
      const response = await resourceAPI.getResourceTags();
      setTags(response.data);
    } catch (error) {
      message.error('加载标签列表失败');
    }
  };

  useEffect(() => {
    loadResources();
    loadTags();
  }, [fileTypeFilter, searchText, selectedTags]);

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // 格式化时长
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 获取文件类型图标
  const getFileTypeIcon = (fileType: string) => {
    switch (fileType) {
      case 'video':
        return <VideoCameraOutlined style={{ color: '#1890ff' }} />;
      case 'audio':
        return <AudioOutlined style={{ color: '#52c41a' }} />;
      case 'image':
        return <PictureOutlined style={{ color: '#fa8c16' }} />;
      default:
        return <FileOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  // 文件上传前的处理
  const beforeUpload = (file: File) => {
    const isValidType = [
      'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm',
      'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/mpeg',
      'image/jpeg', 'image/png', 'image/gif', 'image/webp'
    ].includes(file.type);

    if (!isValidType) {
      message.error('不支持的文件类型！');
      return false;
    }

    const isLt10G = file.size / 1024 / 1024 / 1024 < 10;
    if (!isLt10G) {
      message.error('文件大小不能超过 10GB！');
      return false;
    }

    return true;
  };

  // 处理文件上传
  const handleUpload = async (values: any) => {
    try {
      const formData = new FormData();
      formData.append('file', values.file.file);
      formData.append('description', values.description || '');
      formData.append('is_public', values.is_public.toString());
      if (values.tags) {
        formData.append('tags', values.tags.join(','));
      }

      const response = await resourceAPI.uploadResource(formData);
      message.success('文件上传成功');
      setUploadModalVisible(false);
      form.resetFields();
      loadResources();
    } catch (error) {
      message.error('文件上传失败');
    }
  };

  // 删除资源
  const handleDelete = async (id: number) => {
    try {
      await resourceAPI.deleteResource(id);
      message.success('删除成功');
      loadResources();
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 创建标签
  const handleCreateTag = async (values: any) => {
    try {
      await resourceAPI.createResourceTag(
        values.name,
        values.tag_type,
        values.description
      );
      message.success('标签创建成功');
      setTagModalVisible(false);
      tagForm.resetFields();
      loadTags();
    } catch (error) {
      message.error('标签创建失败');
    }
  };

  // 删除标签
  const handleDeleteTag = async (id: number) => {
    try {
      await resourceAPI.deleteResourceTag(id);
      message.success('标签删除成功');
      loadTags();
    } catch (error) {
      message.error('标签删除失败');
    }
  };

  // 预览资源
  const handlePreview = async (resource: Resource) => {
    try {
      const response = await resourceAPI.getResourceViewUrl(resource.id);
      window.open(response.data.view_url, '_blank');
    } catch (error) {
      message.error('预览失败');
    }
  };

  // 列定义
  const columns = [
    {
      title: '文件名',
      dataIndex: 'original_filename',
      key: 'original_filename',
      render: (text: string, record: Resource) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {getFileTypeIcon(record.file_type)}
            <span style={{ marginLeft: 8, fontWeight: 500 }}>{text}</span>
          </div>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {record.filename}
          </Text>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      render: (type: string) => (
        <Tag color={type === 'video' ? 'blue' : type === 'audio' ? 'green' : 'orange'}>
          {type.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '时长',
      dataIndex: 'duration',
      key: 'duration',
      render: (duration: number) => formatDuration(duration),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: ResourceTag[]) => (
        <div>
          {tags.map(tag => (
            <Tag key={tag.id} icon={<TagOutlined />} color="cyan">
              {tag.name}
            </Tag>
          ))}
          {tags.length === 0 && <Text type="secondary">暂无标签</Text>}
        </div>
      ),
    },
    {
      title: '访问次数',
      dataIndex: 'view_count',
      key: 'view_count',
      render: (count: number) => <Badge count={count} showZero />,
    },
    {
      title: '下载次数',
      dataIndex: 'download_count',
      key: 'download_count',
      render: (count: number) => <Badge count={count} showZero />,
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
      render: (record: Resource) => (
        <Space size="middle">
          <Tooltip title="预览">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handlePreview(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除这个资源吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="resource-management">
      <Row gutter={[24, 24]}>
        <Col span={24}>
          <Card title="资源管理">
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* 搜索和过滤 */}
              <Row gutter={16}>
                <Col span={8}>
                  <Input
                    placeholder="搜索资源..."
                    prefix={<SearchOutlined />}
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    allowClear
                  />
                </Col>
                <Col span={4}>
                  <Select
                    value={fileTypeFilter}
                    onChange={setFileTypeFilter}
                    placeholder="文件类型"
                  >
                    <Option value="all">全部</Option>
                    <Option value="video">视频</Option>
                    <Option value="audio">音频</Option>
                    <Option value="image">图片</Option>
                  </Select>
                </Col>
                <Col span={8}>
                  <Button 
                    type="dashed" 
                    icon={<FilterOutlined />}
                    onClick={() => setTagModalVisible(true)}
                  >
                    管理标签
                  </Button>
                </Col>
                <Col span={4}>
                  <Button 
                    type="primary"
                    icon={<UploadOutlined />}
                    onClick={() => setUploadModalVisible(true)}
                  >
                    上传资源
                  </Button>
                </Col>
              </Row>

              {/* 资源列表 */}
              <Table
                columns={columns}
                dataSource={resources}
                rowKey="id"
                loading={loading}
                pagination={{
                  total: resources.length,
                  pageSize: 20,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  showTotal: (total, range) => 
                    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
                }}
              />
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 上传资源模态框 */}
      <Modal
        title="上传资源"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleUpload} layout="vertical">
          <Form.Item
            name="file"
            label="选择文件"
            rules={[{ required: true, message: '请选择文件' }]}
          >
            <Upload
              name="file"
              beforeUpload={beforeUpload}
              maxCount={1}
              showUploadList={false}
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={3} placeholder="请输入资源描述" />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="访问权限"
            initialValue={true}
          >
            <Select>
              <Option value={true}>公开</Option>
              <Option value={false}>私有</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="tags"
            label="标签"
          >
            <Select
              mode="multiple"
              placeholder="选择标签"
              allowClear
            >
              {tags.map(tag => (
                <Option key={tag.id} value={tag.id}>
                  {tag.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                上传
              </Button>
              <Button onClick={() => setUploadModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 标签管理模态框 */}
      <Modal
        title="标签管理"
        open={tagModalVisible}
        onCancel={() => setTagModalVisible(false)}
        footer={null}
        width={600}
      >
        <Row gutter={16}>
          <Col span={16}>
            <Title level={5}>现有标签</Title>
            <div style={{ marginBottom: 16 }}>
              {tags.map(tag => (
                <Tag 
                  key={tag.id} 
                  closable
                  onClose={() => handleDeleteTag(tag.id)}
                  style={{ marginBottom: 8 }}
                >
                  {tag.name} ({tag.tag_type})
                </Tag>
              ))}
              {tags.length === 0 && <Text type="secondary">暂无标签</Text>}
            </div>
          </Col>
          <Col span={8}>
            <Title level={5}>创建标签</Title>
            <Form form={tagForm} onFinish={handleCreateTag} layout="vertical">
              <Form.Item
                name="name"
                label="标签名称"
                rules={[{ required: true, message: '请输入标签名称' }]}
              >
                <Input placeholder="输入标签名称" />
              </Form.Item>

              <Form.Item
                name="tag_type"
                label="标签类型"
                rules={[{ required: true, message: '请选择标签类型' }]}
              >
                <Select placeholder="选择标签类型">
                  <Option value="audio">音频</Option>
                  <Option value="video">视频</Option>
                  <Option value="image">图片</Option>
                  <Option value="general">通用</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="description"
                label="描述"
              >
                <TextArea rows={3} placeholder="输入标签描述" />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit">
                  创建标签
                </Button>
              </Form.Item>
            </Form>
          </Col>
        </Row>
      </Modal>
    </div>
  );
};

export default ResourceManagement;