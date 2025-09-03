import React from 'react';
import { Button, Card, Row, Col, Typography } from 'antd';
import { PlusOutlined, PlayCircleOutlined, RocketOutlined, ThunderboltOutlined, SafetyCertificateOutlined, GlobalOutlined, DashboardOutlined, ProjectOutlined, VideoCameraOutlined, RobotOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import Terminal from '../components/Terminal';

const { Title, Paragraph } = Typography;

const Landing: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      icon: <RocketOutlined className="text-4xl text-blue-500" />,
      title: "快速处理",
      description: "高效的YouTube视频下载和音频提取，支持批量处理"
    },
    {
      icon: <ThunderboltOutlined className="text-4xl text-cyan-500" />,
      title: "智能切片",
      description: "基于AI的音频分割和字幕生成，精确识别语音片段"
    },
    {
      icon: <SafetyCertificateOutlined className="text-4xl text-teal-500" />,
      title: "安全可靠",
      description: "企业级数据处理和存储方案，保障数据安全"
    },
    {
      icon: <GlobalOutlined className="text-4xl text-indigo-500" />,
      title: "云端同步",
      description: "支持多设备访问和协作，随时随地管理项目"
    }
  ];

  const capabilities = [
    {
      icon: <DashboardOutlined className="text-3xl text-blue-600" />,
      title: "数据统计",
      description: "实时查看项目进度和任务状态"
    },
    {
      icon: <ProjectOutlined className="text-3xl text-cyan-600" />,
      title: "项目管理",
      description: "灵活的项目组织和管理功能"
    },
    {
      icon: <VideoCameraOutlined className="text-3xl text-sky-600" />,
      title: "视频处理",
      description: "支持多种视频格式和处理方式"
    },
    {
      icon: <RobotOutlined className="text-3xl text-indigo-600" />,
      title: "AI助手",
      description: "智能问答和内容分析功能"
    }
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="relative min-h-screen flex flex-col justify-start overflow-hidden pt-20">
        <div className="absolute inset-0 gradient-bg"></div>
        
        <div className="relative z-10 text-center text-white px-4 max-w-6xl mx-auto hero-section">
          {/* Main Title at Top */}
          <div className="mb-8 slide-in-up">
            <h1 className="text-4xl md:text-6xl font-bold mb-4 text-gradient hero-title">
              FlowClip
            </h1>
            <p className="text-lg md:text-xl mb-6 text-blue-100 max-w-3xl mx-auto hero-subtitle">
              智能化的视频内容分析工具，支持音频提取、自动切片、字幕生成和AI对话
            </p>
          </div>

          {/* Terminal Component */}
          <div className="mb-8">
            <Terminal />
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <Button 
              size="large"
              icon={<PlusOutlined />}
              onClick={() => navigate('/dashboard/projects')}
              className="btn-primary-modern px-8 py-4 text-lg h-auto"
            >
              开始创建项目
            </Button>
            <Button 
              size="large"
              onClick={() => navigate('/dashboard')}
              className="glass-effect text-white px-8 py-4 text-lg h-auto border-white/30 hover:bg-white/20 transition-all duration-300"
            >
              进入仪表盘
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            {features.map((feature, index) => (
              <div 
                key={index}
                className="feature-card glass-effect rounded-xl p-6 text-white"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className="flex justify-center mb-4 floating">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-blue-100">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center mb-16">
            <Title level={2} className="text-4xl font-bold mb-4">
              强大功能，助力高效工作
            </Title>
            <Paragraph className="text-lg text-gray-600 max-w-2xl mx-auto">
              我们的平台提供全方位的视频处理解决方案，让您的工作更加高效便捷
            </Paragraph>
          </div>

          <Row gutter={[32, 32]} className="mb-16">
            {capabilities.map((capability, index) => (
              <Col xs={24} sm={12} lg={6} key={index}>
                <Card className="h-full hover:shadow-lg transition-all duration-300 border-0 shadow-md">
                  <div className="text-center mb-4">
                    {capability.icon}
                  </div>
                  <Title level={4} className="text-center mb-2">
                    {capability.title}
                  </Title>
                  <Paragraph className="text-center text-gray-600">
                    {capability.description}
                  </Paragraph>
                </Card>
              </Col>
            ))}
          </Row>

          <div className="text-center">
            <Title level={3} className="mb-4">
              准备开始了吗？
            </Title>
            <Paragraph className="text-gray-600 mb-8">
              立即注册账户，体验强大的视频分析功能
            </Paragraph>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button 
                type="primary" 
                size="large"
                icon={<PlusOutlined />}
                onClick={() => navigate('/dashboard/projects')}
                className="btn-primary-modern px-8 py-3 h-auto"
              >
                创建项目
              </Button>
              <Button 
                size="large"
                onClick={() => navigate('/dashboard')}
                className="px-8 py-3 h-auto"
              >
                查看演示
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 gradient-bg-2">
        <div className="max-w-4xl mx-auto px-4 text-center text-white">
          <Title level={2} className="text-4xl font-bold mb-4 text-white">
            开启您的视频分析之旅
          </Title>
          <Paragraph className="text-lg mb-8 text-blue-100">
            专业的工具，专业的服务，让视频内容分析变得简单高效
          </Paragraph>
          <Button 
            type="primary" 
            size="large"
            icon={<PlayCircleOutlined />}
            onClick={() => navigate('/dashboard')}
            className="bg-white text-blue-800 border-0 px-8 py-3 h-auto hover:bg-gray-100 transition-all duration-300"
          >
            立即开始
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Landing;