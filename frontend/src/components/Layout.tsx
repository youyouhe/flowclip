import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu } from 'antd';
import { ProjectOutlined, VideoCameraOutlined, DashboardOutlined, FileTextOutlined, LogoutOutlined, RobotOutlined, ScissorOutlined, HomeOutlined, VideoCameraAddOutlined, PictureOutlined, SettingOutlined } from '@ant-design/icons';
import { useAuth } from './AuthProvider';

const { Header, Sider, Content } = AntLayout;

const Layout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '首页',
    },
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/dashboard/projects',
      icon: <ProjectOutlined />,
      label: '项目管理',
    },
    {
      key: '/dashboard/videos',
      icon: <VideoCameraOutlined />,
      label: '视频管理',
    },
    {
      key: '/dashboard/llm-chat',
      icon: <RobotOutlined />,
      label: 'AI助手',
    },
    {
      key: '/dashboard/slice-management',
      icon: <ScissorOutlined />,
      label: '切片管理',
    },
    {
      key: '/dashboard/capcut',
      icon: <VideoCameraAddOutlined />,
      label: 'CapCut导出',
    },
    {
      key: '/dashboard/resource-management',
      icon: <PictureOutlined />,
      label: '资源管理',
    },
    {
      key: '/dashboard/logs',
      icon: <FileTextOutlined />,
      label: '日志管理',
    },
    {
      key: '/dashboard/system-config',
      icon: <SettingOutlined />,
      label: '系统配置',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
    } else {
      navigate(key);
    }
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ color: 'white', fontSize: '18px', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)' }}>
        <div>FlowClip</div>
      </Header>
      <AntLayout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>
        <Content style={{ margin: '0', overflow: 'initial', background: '#f5f5f5' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;