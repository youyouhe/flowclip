import React, { createContext, useContext, useEffect, useState } from 'react';
import { Spin, message } from 'antd';
import { authAPI } from '../services/api';
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
    // Check for stored token and get user info
    const token = localStorage.getItem('token');
    if (token) {
      authAPI.getCurrentUser()
        .then(response => {
          setUser({
            id: response.data.id,
            email: response.data.email,
            username: response.data.username,
            fullName: response.data.full_name,
            isActive: response.data.is_active,
            createdAt: response.data.created_at,
          });
        })
        .catch(error => {
          console.error('Failed to get user info:', error);
          localStorage.removeItem('token');
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      const response = await authAPI.login(username, password);
      
      const { access_token } = response.data;
      localStorage.setItem('token', access_token);
      
      // 获取用户信息
      const userResponse = await authAPI.getCurrentUser();
      
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

const register = async (userData: any) => {
    try {
      console.log('Registering with:', userData);
      console.log('API URL:', import.meta.env.VITE_API_URL);
      const response = await authAPI.register(userData);
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