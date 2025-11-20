import React, { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, Select, Space, message, Spin, Typography, Row, Col, Switch, Tag, Divider, Modal, Alert, InputNumber, DatePicker } from 'antd';
import { SendOutlined, RobotOutlined, VideoCameraOutlined, SettingOutlined, ClearOutlined, ScissorOutlined, SearchOutlined, ClearOutlined as ClearFiltersOutlined, ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import { llmAPI } from '../services/api';
import { videoAPI } from '../services/api';
import { projectAPI } from '../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  videoContextUsed?: boolean;
}

interface Video {
  id: number;
  title: string;
  project_id: number;
  status: string;
}

interface Project {
  id: number;
  name: string;
}

const LLMChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [videos, setVideos] = useState<Video[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [useSrtContext, setUseSrtContext] = useState(true);
  const [customSystemPrompt, setCustomSystemPrompt] = useState('');
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  const [currentSystemPrompt, setCurrentSystemPrompt] = useState('');
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [sliceModalVisible, setSliceModalVisible] = useState(false);
  const [lastLLMResponse, setLastLLMResponse] = useState('');
  
  // 筛选状态
  const [filters, setFilters] = useState({
    project_id: undefined as number | undefined,
    status: undefined as string | undefined,
    search: '',
    start_date: undefined as string | undefined,
    end_date: undefined as string | undefined,
    min_duration: undefined as number | undefined,
    max_duration: undefined as number | undefined,
    min_file_size: undefined as number | undefined,
    max_file_size: undefined as number | undefined,
  });
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadVideos();
    loadProjects();
    loadCurrentSystemPrompt();
  }, []);

  useEffect(() => {
    loadVideos();
  }, [filters]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadVideos = async () => {
    try {
      setVideosLoading(true);
      // 构建查询参数
      const params: any = { srt_processed: true };
      if (filters.project_id) params.project_id = filters.project_id;
      if (filters.status) params.status = filters.status;
      if (filters.search) params.search = filters.search;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.min_duration !== undefined) params.min_duration = filters.min_duration;
      if (filters.max_duration !== undefined) params.max_duration = filters.max_duration;
      if (filters.min_file_size !== undefined) params.min_file_size = filters.min_file_size;
      if (filters.max_file_size !== undefined) params.max_file_size = filters.max_file_size;
      
      const response = await videoAPI.getVideos(params);
      // 处理分页响应格式
      const videosData = response.data.videos || response.data;
      
      setVideos(videosData);
    } catch (error) {
      message.error('加载视频列表失败');
    } finally {
      setVideosLoading(false);
    }
  };
  
  const loadProjects = async () => {
    try {
      const response = await projectAPI.getProjects();
      setProjects(response.data);
    } catch (error) {
      message.error('获取项目列表失败');
    }
  };
  
  const handleFilterChange = (key: string, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };
  
  const handleDateRangeChange = (dates: any, dateStrings: [string, string]) => {
    setFilters(prev => ({
      ...prev,
      start_date: dateStrings[0],
      end_date: dateStrings[1]
    }));
  };
  
  const clearFilters = () => {
    setFilters({
      project_id: undefined,
      status: undefined,
      search: '',
      start_date: undefined,
      end_date: undefined,
      min_duration: undefined,
      max_duration: undefined,
      min_file_size: undefined,
      max_file_size: undefined,
    });
  };

  const loadCurrentSystemPrompt = async () => {
    try {
      const response = await llmAPI.getCurrentSystemPrompt();
      setCurrentSystemPrompt(response.data.system_prompt);
    } catch (error) {
      console.error('加载系统提示词失败:', error);
    }
  };

  const handleTestLongRequest = async () => {
    console.log('开始测试长时间请求...');
    setLoading(true);
    
    try {
      const response = await llmAPI.testLongRequest();
      console.log('长时间请求测试成功:', response.data);
      message.success(`测试成功! 处理时间: ${response.data.processing_time_seconds}秒`);
    } catch (error: any) {
      console.error('长时间请求测试失败:', error);
      console.error('错误详情:', {
        code: error.code,
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        timeout: error.code === 'ECONNABORTED'
      });
      
      let errorMessage = '测试失败';
      if (error.code === 'ECONNABORTED') {
        errorMessage = '测试超时，请求被中断';
      } else if (error.response?.data?.detail) {
        errorMessage = `测试失败: ${error.response.data.detail}`;
      } else if (error.message) {
        errorMessage = `网络错误: ${error.message}`;
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await llmAPI.chat(
        inputMessage,
        selectedVideo || undefined,
        useCustomPrompt ? customSystemPrompt : undefined,
        useSrtContext && selectedVideo !== null
      );

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
        videoContextUsed: response.data.video_context_used
      };

      setMessages(prev => [...prev, assistantMessage]);
      
      // 保存LLM响应用于可能的切片操作
      setLastLLMResponse(response.data.response);

      // 显示使用统计信息
      if (response.data.usage) {
        console.log('Token使用情况:', response.data.usage);
      }

    } catch (error: any) {
      console.error('LLM对话失败:', error);
      console.error('错误详情:', {
        code: error.code,
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        timeout: error.code === 'ECONNABORTED'
      });
      
      let errorMessage = '对话失败';
      if (error.code === 'ECONNABORTED') {
        errorMessage = '请求超时，请稍后重试';
      } else if (error.response?.data?.detail) {
        errorMessage = `对话失败: ${error.response.data.detail}`;
      } else if (error.message) {
        errorMessage = `网络错误: ${error.message}`;
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const copyJsonToClipboard = async () => {
    if (!lastLLMResponse) {
      message.warning('没有可复制的LLM响应内容');
      return;
    }

    try {
      // 首先尝试验证JSON格式
      let jsonContent = lastLLMResponse;

      // 检查是否包含```json内容，如果是，则提取
      if (lastLLMResponse.includes('```json') && lastLLMResponse.includes('```')) {
        const jsonStart = lastLLMResponse.indexOf('```json');
        const jsonEnd = lastLLMResponse.indexOf('```', jsonStart + 7);
        if (jsonEnd !== -1) {
          jsonContent = lastLLMResponse.substring(jsonStart + 7, jsonEnd).trim();
        }
      }

      // 验证JSON格式
      try {
        JSON.parse(jsonContent);
      } catch (e) {
        message.error('响应内容不是有效的JSON格式，无法复制');
        return;
      }

      // 复制到剪贴板
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(jsonContent);
        message.success('JSON内容已复制到剪贴板');
      } else {
        // 降级方法
        const textArea = document.createElement('textarea');
        textArea.value = jsonContent;
        textArea.style.position = 'absolute';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        message.success('JSON内容已复制到剪贴板');
      }
    } catch (error) {
      console.error('复制JSON失败:', error);
      message.error('复制JSON内容失败');
    }
  };

  const clearChat = () => {
    setMessages([]);
    message.success('对话已清空');
  };

  const handleUpdateSystemPrompt = async () => {
    try {
      await llmAPI.updateSystemPrompt(customSystemPrompt);
      setCurrentSystemPrompt(customSystemPrompt);
      message.success('系统提示词已更新');
      setSettingsVisible(false);
    } catch (error) {
      message.error('更新系统提示词失败');
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div className="llm-chat">
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card 
            title={
              <Space>
                <RobotOutlined />
                AI视频分析助手
                {useSrtContext && selectedVideo && (
                  <Tag color="green">视频上下文模式</Tag>
                )}
              </Space>
            }
            extra={
              <Space>
                <Button
                  icon={<CopyOutlined />}
                  onClick={copyJsonToClipboard}
                  disabled={!lastLLMResponse}
                  type="default"
                >
                  复制JSON
                </Button>
                <Button
                  icon={<ClearOutlined />}
                  onClick={clearChat}
                  disabled={messages.length === 0}
                >
                  清空对话
                </Button>
                <Button 
                  icon={<ScissorOutlined />} 
                  onClick={() => setSliceModalVisible(true)}
                  disabled={!lastLLMResponse || !selectedVideo}
                >
                  切片管理
                </Button>
                <Button 
                  icon={<SettingOutlined />} 
                  onClick={() => setSettingsVisible(true)}
                >
                  设置
                </Button>
                <Button 
                  type="dashed"
                  onClick={handleTestLongRequest}
                  loading={loading}
                  title="测试60秒长时间请求，用于诊断网络连接问题"
                >
                  网络测试
                </Button>
              </Space>
            }
            className="chat-card"
          >
            <div className="chat-messages" style={{ 
              height: '500px', 
              overflowY: 'auto',
              padding: '16px',
              backgroundColor: '#f5f5f5',
              borderRadius: '8px'
            }}>
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 mt-8">
                  <RobotOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
                  <Title level={4}>开始与AI助手对话</Title>
                  <Text>输入您的问题，AI助手将基于视频内容为您解答</Text>
                </div>
              ) : (
                messages.map((message, index) => (
                  <div
                    key={index}
                    className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
                    style={{
                      marginBottom: '16px',
                      display: 'flex',
                      justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start'
                    }}
                  >
                    <div
                      style={{
                        maxWidth: '80%',
                        padding: '12px 16px',
                        borderRadius: '12px',
                        backgroundColor: message.role === 'user' ? '#1890ff' : '#ffffff',
                        color: message.role === 'user' ? '#ffffff' : '#000000',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                      }}
                    >
                      <div style={{ marginBottom: '4px' }}>
                        <Text strong style={{ color: message.role === 'user' ? '#ffffff' : '#1890ff' }}>
                          {message.role === 'user' ? '您' : 'AI助手'}
                        </Text>
                        <Text type="secondary" style={{ 
                          fontSize: '12px', 
                          marginLeft: '8px',
                          color: message.role === 'user' ? '#e6f7ff' : '#999999'
                        }}>
                          {formatTime(message.timestamp)}
                        </Text>
                        {message.videoContextUsed && (
                          <Tag color="green" style={{ marginLeft: '8px', fontSize: '10px' }}>
                            视频上下文
                          </Tag>
                        )}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                        {message.content}
                      </div>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input" style={{ marginTop: '16px' }}>
              <Space.Compact style={{ width: '100%' }}>
                <TextArea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="输入您的问题..."
                  rows={3}
                  disabled={loading}
                  style={{ resize: 'none' }}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSendMessage}
                  loading={loading}
                  disabled={!inputMessage.trim()}
                  style={{ height: '72px' }}
                >
                  发送
                </Button>
              </Space.Compact>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="控制面板" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              {/* 筛选器 */}
              <div style={{ marginBottom: '16px' }}>
                <Row gutter={[16, 16]}>
                  <Col span={24}>
                    <Select
                      placeholder="选择项目"
                      value={filters.project_id}
                      onChange={(value) => handleFilterChange('project_id', value)}
                      style={{ width: '20%', marginRight: '8px' }}
                      allowClear
                    >
                      {projects.map(project => (
                        <Option key={project.id} value={project.id}>
                          {project.name}
                        </Option>
                      ))}
                    </Select>
                    <Select
                      placeholder="视频状态"
                      value={filters.status}
                      onChange={(value) => handleFilterChange('status', value)}
                      style={{ width: '20%', marginRight: '8px' }}
                      allowClear
                    >
                      <Select.Option value="pending">等待中</Select.Option>
                      <Select.Option value="downloading">下载中</Select.Option>
                      <Select.Option value="downloaded">已下载</Select.Option>
                      <Select.Option value="processing">处理中</Select.Option>
                      <Select.Option value="completed">已完成</Select.Option>
                      <Select.Option value="failed">失败</Select.Option>
                    </Select>
                    <InputNumber
                      placeholder="最小时长(秒)"
                      value={filters.min_duration}
                      onChange={(value) => handleFilterChange('min_duration', value)}
                      style={{ width: '12%', marginRight: '8px' }}
                    />
                    <InputNumber
                      placeholder="最大时长(秒)"
                      value={filters.max_duration}
                      onChange={(value) => handleFilterChange('max_duration', value)}
                      style={{ width: '12%', marginRight: '8px' }}
                    />
                    <InputNumber
                      placeholder="最小大小(MB)"
                      value={filters.min_file_size}
                      onChange={(value) => handleFilterChange('min_file_size', value)}
                      style={{ width: '12%', marginRight: '8px' }}
                    />
                    <InputNumber
                      placeholder="最大大小(MB)"
                      value={filters.max_file_size}
                      onChange={(value) => handleFilterChange('max_file_size', value)}
                      style={{ width: '12%', marginRight: '8px' }}
                    />
                  </Col>
                </Row>
                <Row gutter={[16, 16]} style={{ marginTop: '8px' }}>
                  <Col span={24}>
                    <DatePicker.RangePicker
                      style={{ width: '40%', marginRight: '8px' }}
                      onChange={handleDateRangeChange}
                      placeholder={['开始日期', '结束日期']}
                    />
                    <Input
                      placeholder="搜索视频标题"
                      value={filters.search}
                      onChange={(e) => handleFilterChange('search', e.target.value)}
                      onPressEnter={loadVideos}
                      style={{ width: '30%', marginRight: '8px' }}
                    />
                    <Button
                      type="primary"
                      icon={<SearchOutlined />}
                      onClick={loadVideos}
                      loading={videosLoading}
                      style={{ marginRight: '8px' }}
                    >
                      搜索
                    </Button>
                    <Button
                      icon={<ClearFiltersOutlined />}
                      onClick={clearFilters}
                      style={{ marginRight: '8px' }}
                    >
                      清除
                    </Button>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={loadVideos}
                      loading={videosLoading}
                    >
                      刷新
                    </Button>
                  </Col>
                </Row>
              </div>

              <div>
                <Text strong>选择视频：</Text>
                <Select
                  value={selectedVideo}
                  onChange={setSelectedVideo}
                  placeholder="选择视频文件"
                  style={{ width: '100%', marginTop: '8px' }}
                  loading={videosLoading}
                  allowClear
                >
                  {videos.map((video) => (
                    <Option key={video.id} value={video.id}>
                      {video.title}
                    </Option>
                  ))}
                </Select>
              </div>

              <div>
                <Text strong>使用SRT上下文：</Text>
                <div style={{ marginTop: '8px' }}>
                  <Switch
                    checked={useSrtContext}
                    onChange={setUseSrtContext}
                    disabled={!selectedVideo}
                  />
                  <Text type="secondary" style={{ marginLeft: '8px' }}>
                    {selectedVideo ? '基于视频字幕内容分析' : '请先选择视频'}
                  </Text>
                </div>
              </div>

              <div>
                <Text strong>使用自定义提示词：</Text>
                <div style={{ marginTop: '8px' }}>
                  <Switch
                    checked={useCustomPrompt}
                    onChange={setUseCustomPrompt}
                  />
                </div>
              </div>

              {useCustomPrompt && (
                <div>
                  <Text strong>自定义系统提示词：</Text>
                  <TextArea
                    value={customSystemPrompt}
                    onChange={(e) => setCustomSystemPrompt(e.target.value)}
                    placeholder="输入自定义系统提示词..."
                    rows={4}
                    style={{ marginTop: '8px', fontSize: '12px' }}
                  />
                </div>
              )}

              <Divider />

              <div>
                <Text strong>当前系统提示词：</Text>
                <div 
                  style={{ 
                    marginTop: '8px', 
                    padding: '8px', 
                    backgroundColor: '#f5f5f5', 
                    borderRadius: '4px',
                    fontSize: '12px',
                    maxHeight: '100px',
                    overflowY: 'auto'
                  }}
                >
                  {currentSystemPrompt || '加载中...'}
                </div>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 设置模态框 */}
      <Modal
        title="系统提示词设置"
        open={settingsVisible}
        onOk={handleUpdateSystemPrompt}
        onCancel={() => setSettingsVisible(false)}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>修改系统提示词（将在下次对话中生效）：</Text>
          <TextArea
            value={customSystemPrompt || currentSystemPrompt}
            onChange={(e) => setCustomSystemPrompt(e.target.value)}
            rows={6}
            placeholder="输入系统提示词..."
          />
        </Space>
      </Modal>

      {/* 切片管理引导模态框 */}
      <Modal
        title="切片管理"
        open={sliceModalVisible}
        onCancel={() => setSliceModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setSliceModalVisible(false)}>
            取消
          </Button>,
          <Button key="slice-management" type="primary" onClick={() => {
            window.open('/dashboard/slice-management', '_blank');
            setSliceModalVisible(false);
          }}>
            进入切片管理
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            message="视频切片管理"
            description="您可以基于LLM的分析结果对视频进行切片操作。在切片管理页面中，您可以："
            type="info"
            showIcon
          />
          
          <ul>
            <li>验证和保存LLM生成的JSON数据</li>
            <li>基于时间戳切割视频</li>
            <li>管理切片结果和子切片</li>
            <li>预览和下载切片文件</li>
          </ul>
          
          <Alert
            message="当前状态"
            description={`已选择视频：${selectedVideo ? videos.find(v => v.id === selectedVideo)?.title || '未知' : '无'}\n最新LLM响应：${lastLLMResponse ? '已获取' : '无'}`}
            type="warning"
            showIcon
          />
          
          <div>
            <Text strong>最新的LLM响应预览：</Text>
            <div style={{ 
              maxHeight: '200px', 
              overflow: 'auto', 
              marginTop: '8px',
              padding: '8px',
              backgroundColor: '#f5f5f5',
              borderRadius: '4px',
              fontFamily: 'monospace',
              fontSize: '12px'
            }}>
              {lastLLMResponse ? (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {lastLLMResponse.length > 500 
                    ? lastLLMResponse.substring(0, 500) + '...' 
                    : lastLLMResponse}
                </pre>
              ) : (
                <Text type="secondary">暂无LLM响应</Text>
              )}
            </div>
          </div>
        </Space>
      </Modal>
    </div>
  );
};

export default LLMChat;