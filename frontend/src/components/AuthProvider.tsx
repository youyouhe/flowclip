import React, { createContext, useContext, useEffect, useState } from 'react';
import { Spin, message } from 'antd';
import axios from 'axios';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: any) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored token
    const token = localStorage.getItem('token');
    if (token) {
      // TODO: Validate token and get user info
      // For now, we'll just set a mock user
      setUser({
        id: 1,
        email: 'user@example.com',
        username: 'user',
        fullName: 'User',
        isActive: true,
        createdAt: new Date().toISOString(),
      });
    }
    setLoading(false);
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      const response = await axios.post(`${API_BASE_URL}/api/v1/auth/login`, formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      
      const { access_token } = response.data;
      localStorage.setItem('token', access_token);
      
      // 获取用户信息
      const userResponse = await axios.get(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: {
          'Authorization': `Bearer ${access_token}`,
        },
      });
      
      setUser({
        id: userResponse.data.id,
        email: userResponse.data.email,
        username: userResponse.data.username,
        fullName: userResponse.data.full_name,
        isActive: userResponse.data.is_active,
        createdAt: new Date().toISOString(),
      });
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '登录失败');
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('token');
  };

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://192.168.8.107:8001';

  const register = async (userData: any) => {
    try {
      console.log('Registering with:', userData);
      console.log('API URL:', API_BASE_URL);
      const response = await axios.post(`${API_BASE_URL}/api/v1/auth/register`, userData);
      console.log('Registration response:', response.data);
      const { access_token } = response.data;
      localStorage.setItem('token', access_token);
      
      // 使用注册返回的数据，跳过获取用户信息的请求
      console.log('Registration successful, using registration data');
      setUser({
        id: response.data.id,
        email: response.data.email,
        username: response.data.username,
        fullName: response.data.full_name,
        isActive: true,
        createdAt: response.data.created_at || new Date().toISOString(),
      });
    } catch (error: any) {
      console.error('Registration error:', error);
      console.error('Error response:', error.response);
      throw new Error(error.response?.data?.detail || error.message || '注册失败');
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthProvider;