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
  Tooltip,
  Checkbox
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
  FilterOutlined,
  FileOutlined
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
  is_active: boolean;
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
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [tagForm] = Form.useForm();
  const [searchText, setSearchText] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [showInactive, setShowInactive] = useState<boolean>(false);

  // 加载资源列表
  const loadResources = async () => {
    try {
      setLoading(true);
      console.log('Loading resources with filters:', {
        fileTypeFilter,
        searchText,
        selectedTags,
        page: 1,
        page_size: 100
      });
      
      // 构建查询参数
      const params: any = {
        file_type: fileTypeFilter === 'all' ? undefined : fileTypeFilter,
        search: searchText || undefined,
        tags: selectedTags.length > 0 ? selectedTags.join(',') : undefined,
        page: 1,
        page_size: 100
      };
      
      // 控制资源显示状态
      if (showInactive) {
        // 显示所有资源（不添加 is_active 过滤器）
        console.log('显示所有资源，不添加 is_active 过滤器');
      } else {
        // 只显示活跃的资源
        params.is_active = true;
        console.log('只显示活跃资源，添加 is_active=true');
      }
      
      console.log('发送查询参数:', params);
      const response = await resourceAPI.getResources(params);
      
      console.log('Resources response:', response);
      console.log('Resources data structure:', {
        hasData: !!response.data,
        isArray: Array.isArray(response.data),
        hasResources: !!response.data?.resources,
        resourcesLength: response.data?.resources?.length,
        fullData: response.data
      });
      
      setResources(response.data.resources || []);
    } catch (error) {
      console.error('加载资源失败:', error);
      message.error('加载资源列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载标签列表
  const loadTags = async () => {
    try {
      console.log('Loading tags...');
      const response = await resourceAPI.getResourceTags();
      console.log('Tags response:', response);
      console.log('Tags response structure:', {
        hasData: !!response.data,
        isArray: Array.isArray(response.data),
        dataLength: response.data?.length,
        fullData: response.data
      });
      
      // 输出原始响应文本以检查编码
      console.log('Raw response data:', response.data);
      console.log('Response data type:', typeof response.data);
      console.log('Response data as string:', JSON.stringify(response.data));
      console.log('First tag name as string:', response.data?.[0]?.name);
      
      const tagsData = response.data?.data || response.data || [];
      console.log('Processed tags:', tagsData);
      console.log('First tag sample:', tagsData[0]);
      
      setTags(tagsData);
    } catch (error) {
      console.error('加载标签失败:', error);
      message.error('加载标签列表失败');
    }
  };

  useEffect(() => {
    loadResources();
    loadTags();
  }, [fileTypeFilter, searchText, selectedTags, showInactive]);

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

  
  // 处理文件上传
  const handleUpload = async (values: any) => {
    try {
      console.log('=== UPLOAD DEBUG START ===');
      console.log('Upload form values:', values);
      console.log('Values file structure:', {
        hasFile: !!values.file,
        isArray: Array.isArray(values.file),
        length: values.file?.length,
        firstFile: values.file?.[0],
        hasOriginFileObj: values.file?.[0]?.originFileObj,
        originFileObjName: values.file?.[0]?.originFileObj?.name
      });
      
      const formData = new FormData();
      
      // 确保我们获取到实际的文件对象
      if (values.file && values.file[0] && values.file[0].originFileObj) {
        const fileObj = values.file[0].originFileObj;
        formData.append('file', fileObj);
        console.log('✅ File added to FormData:', fileObj.name, fileObj.size, fileObj.type);
      } else {
        console.error('❌ No file found in form values');
        throw new Error('未选择文件');
      }
      
      formData.append('description', values.description || '');
      formData.append('is_public', values.is_public.toString());
      
      console.log('Tags value:', values.tags);
      console.log('Tags type:', typeof values.tags);
      console.log('Tags is array:', Array.isArray(values.tags));
      
      if (values.tags && values.tags.length > 0) {
        const tagsString = values.tags.join(',');
        formData.append('tags', tagsString);
        console.log('✅ Tags added to FormData:', tagsString);
      } else {
        console.log('ℹ️ No tags provided');
      }

      console.log('📋 FormData entries:');
      for (let [key, value] of formData.entries()) {
        console.log(`  ${key}:`, value instanceof File ? `${value.name} (${value.size} bytes, ${value.type})` : value);
      }

      console.log('🚀 Sending upload request...');
      const response = await resourceAPI.uploadResource(formData);
      console.log('✅ Upload response:', response);
      console.log('=== UPLOAD DEBUG END ===');
      
      message.success('文件上传成功');
      setUploadModalVisible(false);
      form.resetFields();
      loadResources();
    } catch (error) {
      console.error('❌ UPLOAD ERROR:', error);
      console.error('Error response:', error.response);
      console.error('Error data:', error.response?.data);
      console.error('Error status:', error.response?.status);
      message.error(error.response?.data?.detail || '文件上传失败');
    }
  };

  // 删除资源
  const handleDelete = async (id: number) => {
    try {
      console.log('🗑️ Attempting to delete resource:', id);
      await resourceAPI.deleteResource(id);
      console.log('✅ Delete successful');
      message.success('删除成功');
      loadResources();
    } catch (error) {
      console.error('❌ Delete error:', error);
      message.error('删除失败');
    }
  };

  const handleRestore = async (id: number) => {
    try {
      console.log('🔄 Attempting to restore resource:', id);
      // 更新资源的 is_active 状态为 true
      await resourceAPI.toggleResourceActiveStatus(id, true);
      console.log('✅ Restore successful');
      message.success('恢复成功');
      loadResources();
    } catch (error) {
      console.error('❌ Restore error:', error);
      message.error('恢复失败');
    }
  };

  // 创建标签
  const handleCreateTag = async (values: any) => {
    try {
      console.log('🏷️ Creating tag:', values);
      await resourceAPI.createResourceTag(
        values.name,
        values.tag_type,
        values.description
      );
      console.log('✅ Tag creation successful');
      message.success('标签创建成功');
      setTagModalVisible(false);
      tagForm.resetFields();
      loadTags();
    } catch (error) {
      console.error('❌ Tag creation error:', error);
      message.error('标签创建失败');
    }
  };

  // 删除标签
  const handleDeleteTag = async (id: number) => {
    try {
      console.log('🗑️ Deleting tag:', id);
      await resourceAPI.deleteResourceTag(id);
      console.log('✅ Tag deletion successful');
      message.success('标签删除成功');
      loadTags();
    } catch (error) {
      console.error('❌ Tag deletion error:', error);
      message.error('标签删除失败');
    }
  };

  // 预览资源
  const handlePreview = async (resource: Resource) => {
    try {
      console.log('👁️ Attempting to preview resource:', resource.id, resource.original_filename);
      const response = await resourceAPI.getResourceViewUrl(resource.id);
      console.log('✅ Preview URL response:', response);
      // 设置预览URL并显示弹窗
      setPreviewUrl(response.data.view_url);
      setSelectedResource(resource);
      setPreviewModalVisible(true);
    } catch (error) {
      console.error('❌ Preview error:', error);
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
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean, record: Resource) => (
        <Badge 
          status={isActive ? 'success' : 'error'} 
          text={isActive ? '正常' : '已删除'}
        />
      ),
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
              disabled={!record.is_active}
            />
          </Tooltip>
          {record.is_active ? (
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
          ) : (
            <Popconfirm
              title="确定要恢复这个资源吗？"
              onConfirm={() => handleRestore(record.id)}
              okText="恢复"
              cancelText="取消"
            >
              <Tooltip title="恢复">
                <Button
                  type="text"
                  icon={<EditOutlined />}
                  style={{ color: '#1890ff' }}
                />
              </Tooltip>
            </Popconfirm>
          )}
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
                <Col span={4}>
                  <Checkbox 
                    checked={showInactive}
                    onChange={(e) => setShowInactive(e.target.checked)}
                  >
                    显示已删除
                  </Checkbox>
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
            valuePropName="fileList"
            getValueFromEvent={(e: any) => {
              if (Array.isArray(e)) {
                return e;
              }
              return e?.fileList;
            }}
          >
            <Upload
              name="file"
              accept="video/*,audio/*,image/*"
              maxCount={1}
              beforeUpload={(file) => {
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

                return false; // 阻止自动上传，等待表单提交
              }}
              customRequest={({ file, onSuccess }) => {
                // 空操作，完全禁用自动上传
                if (onSuccess) onSuccess('ok');
              }}
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
              onChange={(value) => console.log('🏷️ Tags selected:', value)}
              onDropdownVisibleChange={(open) => {
                if (open) {
                  console.log('🏷️ Dropdown opened, available tags:', tags.length);
                }
              }}
            >
              {tags.map(tag => (
                <Option key={tag.id} value={tag.id}>
                  {tag.name} ({tag.tag_type})
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" onClick={() => form.submit()}>
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

      {/* 预览资源模态框 */}
      <Modal
        title="资源预览"
        open={previewModalVisible}
        onCancel={() => setPreviewModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedResource && (
          <div>
            <h3>{selectedResource.original_filename}</h3>
            <p>文件类型: {selectedResource.file_type}</p>
            <p>文件大小: {formatFileSize(selectedResource.file_size)}</p>
            {selectedResource.duration && <p>时长: {formatDuration(selectedResource.duration)}</p>}
            
            {/* 下载URL和复制按钮 */}
            <div style={{ marginTop: 16, marginBottom: 16 }}>
              <Button 
                type="primary" 
                onClick={async () => {
                  try {
                    const response = await resourceAPI.getResourceDownloadUrl(selectedResource.id);
                    const downloadUrl = response.data.download_url;
                    
                    // 复制到剪贴板，兼容不同浏览器
                    if (navigator.clipboard && window.isSecureContext) {
                      // 现代浏览器支持
                      await navigator.clipboard.writeText(downloadUrl);
                      message.success('下载链接已复制到剪贴板');
                    } else {
                      // 降级方案
                      const textArea = document.createElement('textarea');
                      textArea.value = downloadUrl;
                      document.body.appendChild(textArea);
                      textArea.focus();
                      textArea.select();
                      try {
                        document.execCommand('copy');
                        message.success('下载链接已复制到剪贴板');
                      } catch (err) {
                        message.error('复制失败，请手动复制链接');
                        console.error('复制失败:', err);
                      }
                      document.body.removeChild(textArea);
                    }
                  } catch (error) {
                    console.error('获取下载链接失败:', error);
                    message.error('获取下载链接失败');
                  }
                }}
              >
                复制下载链接
              </Button>
            </div>
            
            {previewUrl && (
              <div style={{ marginTop: 16 }}>
                {selectedResource.file_type === 'image' ? (
                  <img 
                    src={previewUrl} 
                    alt="预览" 
                    style={{ maxWidth: '100%', maxHeight: '60vh' }} 
                  />
                ) : selectedResource.file_type === 'video' ? (
                  <video 
                    src={previewUrl} 
                    controls 
                    style={{ width: '100%', maxHeight: '60vh' }} 
                  />
                ) : selectedResource.file_type === 'audio' ? (
                  <audio 
                    src={previewUrl} 
                    controls 
                    style={{ width: '100%' }} 
                  />
                ) : (
                  <div>
                    <p>该文件类型不支持在线预览</p>
                    <Button 
                      type="primary" 
                      onClick={() => window.open(previewUrl, '_blank')}
                    >
                      下载文件
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ResourceManagement;