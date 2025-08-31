import React, { useState } from 'react';
import { 
  Modal, 
  Form, 
  Input, 
  Select, 
  Upload, 
  Button, 
  message, 
  Progress, 
  Typography,
  Space,
  Alert
} from 'antd';
import { 
  UploadOutlined, 
  VideoCameraOutlined,
  InboxOutlined
} from '@ant-design/icons';
import { projectAPI, videoAPI } from '../services/api';
import ReliableUpload from './ReliableUpload';

const { TextArea } = Input;
const { Text } = Typography;
const { Dragger } = Upload;

interface VideoUploadModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: (video: any) => void;
}

interface Project {
  id: number;
  name: string;
}

const VideoUploadModal: React.FC<VideoUploadModalProps> = ({
  visible,
  onCancel,
  onSuccess
}) => {
  const [form] = Form.useForm();
  const [projects, setProjects] = useState<Project[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [loadingProjects, setLoadingProjects] = useState(false);

  // 加载项目列表
  React.useEffect(() => {
    if (visible) {
      loadProjects();
    }
  }, [visible]);

  const loadProjects = async () => {
    try {
      setLoadingProjects(true);
      const response = await projectAPI.getProjects();
      setProjects(response.data);
    } catch (error) {
      message.error('加载项目列表失败');
    } finally {
      setLoadingProjects(false);
    }
  };

  const handleBeforeUpload = (file: File) => {
    // 验证文件类型
    const allowedTypes = [
      'video/mp4', 
      'video/webm', 
      'video/quicktime', 
      'video/x-msvideo', 
      'video/x-matroska',
      'video/x-flv',
      'video/x-ms-wmv'
    ];
    
    // 检查文件扩展名作为备选验证方式
    const allowedExtensions = ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
      message.error(`不支持的文件类型: ${file.type || fileExtension}`);
      return false;
    }

    // 验证文件大小（2GB）
    const maxSize = 6 * 1024 * 1024 * 1024; // 2GB
    if (file.size > maxSize) {
      message.error('文件大小不能超过2GB');
      return false;
    }

    return true;
  };

  const handleUpload = async (values: any) => {
    try {
      setUploading(true);
      setUploadProgress(0);

      // 验证表单数据
      if (!values.title) {
        message.error('请输入视频标题');
        setUploading(false);
        return;
      }
      
      if (!values.project_id) {
        message.error('请选择所属项目');
        setUploading(false);
        return;
      }
      
      // 验证文件
      console.log('视频文件数据:', values.videoFile);
      if (!values.videoFile || !values.videoFile[0]) {
        message.error('请选择要上传的视频文件');
        setUploading(false);
        return;
      }
      
      const uploadedFile = values.videoFile[0];
      if (!uploadedFile.originFileObj) {
        message.error('请选择要上传的视频文件');
        setUploading(false);
        return;
      }

      // 使用分块上传方式上传文件
      const fileObj = uploadedFile.originFileObj;
      const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB per chunk
      const totalChunks = Math.ceil(fileObj.size / CHUNK_SIZE);
      let videoId = null;

      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, fileObj.size);
        const chunk = fileObj.slice(start, end);
        
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('chunkIndex', i.toString());
        formData.append('totalChunks', totalChunks.toString());
        formData.append('fileName', fileObj.name);
        formData.append('fileSize', fileObj.size.toString());
        formData.append('project_id', values.project_id.toString());
        
        // 添加标题和描述（仅在第一个分块时）
        if (i === 0) {
          formData.append('title', values.title);
          formData.append('description', values.description || '');
        }
        
        // 如果不是第一个分块，添加video_id
        if (i > 0 && videoId) {
          formData.append('video_id', videoId.toString());
        }
        
        try {
          const response = await videoAPI.uploadChunk(formData);
          
          if (!response || !response.data) {
            throw new Error('服务器响应无效');
          }
          
          // 保存video_id用于后续分块
          if (response.data.video_id && !videoId) {
            videoId = response.data.video_id;
          }
          
          const chunkProgress = Math.round(((i + 1) / totalChunks) * 100);
          setUploadProgress(chunkProgress);
          
          // 如果上传完成，返回完整响应
          if (response.data.completed) {
            message.success('视频上传已开始，可在后台继续处理');
            if (response.data.video) {
              onSuccess(response.data.video);
            } else if (response.data.video_id) {
              onSuccess({ id: response.data.video_id });
            }
            // 重置表单和状态
            form.resetFields();
            setUploadProgress(0);
            setUploading(false);
            onCancel();
            return;
          }
        } catch (error: any) {
          throw error;
        }
      }
      
      // 重置表单和状态
      form.resetFields();
      setUploadProgress(0);
      setUploading(false);
      onCancel();

    } catch (error: any) {
      console.error('上传处理失败:', error);
      message.error(`上传处理失败: ${error.message || '未知错误'}`);
      setUploadProgress(0);
      setUploading(false);
    }
  };

  const uploadProps = {
    beforeUpload: handleBeforeUpload,
    maxCount: 1,
    accept: '.mp4,.webm,.mov,.avi,.mkv,.flv,.wmv',
    disabled: uploading,
    // 自定义上传请求，阻止默认上传行为
    customRequest: ({ file, onSuccess, onError }) => {
      // 我们不在此处上传文件，而是在表单提交时上传
      // 这里只是阻止默认的上传行为
      if (onSuccess) {
        onSuccess({ status: 'done' });
      }
    }
  };

  return (
    <Modal
      title="上传视频"
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={600}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleUpload}
      >
        <Form.Item
          name="title"
          label="视频标题"
          rules={[{ required: true, message: '请输入视频标题' }]}
        >
          <Input 
            placeholder="请输入视频标题" 
            maxLength={500}
            showCount
          />
        </Form.Item>

        <Form.Item
          name="description"
          label="视频描述"
        >
          <TextArea 
            placeholder="请输入视频描述（可选）" 
            rows={3}
            maxLength={1000}
            showCount
          />
        </Form.Item>

        <Form.Item
          name="project_id"
          label="所属项目"
          rules={[{ required: true, message: '请选择所属项目' }]}
        >
          <Select
            placeholder="请选择项目"
            loading={loadingProjects}
          >
            {projects.map(project => (
              <Select.Option key={project.id} value={project.id}>
                {project.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="videoFile"
          label="视频文件"
          rules={[{ required: true, message: '请选择视频文件' }]}
          valuePropName="fileList"
          getValueFromEvent={(e) => {
            if (Array.isArray(e)) {
              return e;
            }
            return e?.fileList;
          }}
        >
          <Dragger {...uploadProps} className="video-upload-dragger">
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持单个文件上传，文件类型：MP4, WebM, MOV, AVI, MKV, FLV, WMV，文件大小不超过2GB
            </p>
          </Dragger>
        </Form.Item>

        {uploading && (
          <Form.Item>
            <div style={{ marginBottom: 16 }}>
              <Text>上传进度</Text>
              <Progress 
                percent={uploadProgress} 
                status="active"
                strokeColor={{
                  from: '#108ee9',
                  to: '#87d068',
                }}
              />
            </div>
          </Form.Item>
        )}

        <Form.Item>
          <Space>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={uploading}
              icon={<UploadOutlined />}
            >
              {uploading ? '上传中...' : '开始上传'}
            </Button>
            <Button onClick={onCancel} disabled={uploading}>
              取消
            </Button>
          </Space>
        </Form.Item>

        <Alert
          message="提示"
          description="上传开始后，您可以关闭页面，视频将在后台继续处理。处理完成后可在视频列表中查看。"
          type="info"
          showIcon
        />
      </Form>
    </Modal>
  );
};

export default VideoUploadModal;