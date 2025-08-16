import React, { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, Select, Space, message, Spin, Typography, Row, Col, Switch, Tag, Divider, Modal, Alert } from 'antd';
import { SendOutlined, RobotOutlined, VideoCameraOutlined, SettingOutlined, ClearOutlined, ScissorOutlined } from '@ant-design/icons';
import { llmAPI } from '../services/api';
import { videoAPI } from '../services/api';

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

const LLMChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<number | null>(null);
  const [useSrtContext, setUseSrtContext] = useState(true);
  const [customSystemPrompt, setCustomSystemPrompt] = useState('');
  const [useCustomPrompt, setUseCustomPrompt] = useState(false);
  const [currentSystemPrompt, setCurrentSystemPrompt] = useState('');
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [videosLoading, setVideosLoading] = useState(false);
  const [sliceModalVisible, setSliceModalVisible] = useState(false);
  const [lastLLMResponse, setLastLLMResponse] = useState('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadVideos();
    loadCurrentSystemPrompt();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadVideos = async () => {
    try {
      setVideosLoading(true);
      // 只获取SRT处理成功的视频
      const response = await videoAPI.getVideos({ srt_processed: true });
      // 处理分页响应格式
      const videosData = response.data.videos || response.data;
      
      setVideos(videosData);
    } catch (error) {
      message.error('加载视频列表失败');
    } finally {
      setVideosLoading(false);
    }
  };

  const loadCurrentSystemPrompt = async () => {
    try {
      const response = await llmAPI.getCurrentSystemPrompt();
      setCurrentSystemPrompt(response.data.system_prompt);
    } catch (error) {
      console.error('加载系统提示词失败:', error);
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
      message.error(`对话失败: ${error.response?.data?.detail || error.message}`);
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
        <Col xs={24} lg={18}>
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
                        maxWidth: '70%',
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

        <Col xs={24} lg={6}>
          <Card title="控制面板" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
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