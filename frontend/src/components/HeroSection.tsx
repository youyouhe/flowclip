import React from 'react';
import { Button } from 'antd';
import { PlusOutlined, RocketOutlined, ThunderboltOutlined, SafetyCertificateOutlined, GlobalOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const HeroSection: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      icon: <RocketOutlined className="text-3xl text-blue-600" />,
      title: "快速处理",
      description: "高效的YouTube视频下载和音频提取"
    },
    {
      icon: <ThunderboltOutlined className="text-3xl text-yellow-600" />,
      title: "智能切片",
      description: "基于AI的音频分割和字幕生成"
    },
    {
      icon: <SafetyCertificateOutlined className="text-3xl text-green-600" />,
      title: "安全可靠",
      description: "企业级数据处理和存储方案"
    },
    {
      icon: <GlobalOutlined className="text-3xl text-purple-600" />,
      title: "云端同步",
      description: "支持多设备访问和协作"
    }
  ];

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 gradient-bg"></div>
      
      <div className="relative z-10 text-center text-white px-4 max-w-6xl mx-auto hero-section">
        <div className="mb-8 slide-in-up">
          <h1 className="text-5xl md:text-7xl font-bold mb-6 text-gradient hero-title">
            Video slicing tool
          </h1>
          <p className="text-xl md:text-2xl mb-8 text-blue-100 max-w-3xl mx-auto hero-subtitle">
            智能化的视频内容分析工具，支持音频提取、自动切片、字幕生成和AI对话
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <Button 
              size="large"
              icon={<PlusOutlined />}
              onClick={() => navigate('/projects')}
              className="btn-primary-modern px-8 py-4 text-lg h-auto"
            >
              开始创建项目
            </Button>
            <Button 
              size="large"
              onClick={() => navigate('/videos')}
              className="glass-effect text-white px-8 py-4 text-lg h-auto border-white/30 hover:bg-white/20 transition-all duration-300"
            >
              管理视频
            </Button>
          </div>
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
  );
};

export default HeroSection;