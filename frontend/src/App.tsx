import { StrictMode } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { Toaster } from 'react-hot-toast';
import Layout from './components/Layout';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProjectDetail from './pages/ProjectDetail';
import Videos from './pages/Videos';
import VideoDetail from './pages/VideoDetail';
import LLMChat from './pages/LLMChat';
import SliceManagement from './pages/SliceManagement';
import CapCut from './pages/CapCut';
import ResourceManagement from './pages/ResourceManagement';
import Logs from './pages/Logs';
import Login from './pages/Login';
import Register from './pages/Register';
import AuthProvider from './components/AuthProvider';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <AuthProvider>
        <Router>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }>
              <Route index element={<Dashboard />} />
              <Route path="projects" element={<Projects />} />
              <Route path="projects/:id" element={<ProjectDetail />} />
              <Route path="videos" element={<Videos />} />
              <Route path="videos/:id" element={<VideoDetail />} />
              <Route path="llm-chat" element={<LLMChat />} />
              <Route path="slice-management" element={<SliceManagement />} />
              <Route path="capcut" element={<CapCut />} />
              <Route path="resource-management" element={<ResourceManagement />} />
              <Route path="logs" element={<Logs />} />
            </Route>
          </Routes>
        </Router>
        <Toaster position="top-right" />
      </AuthProvider>
    </ConfigProvider>
  );
}

export default App;