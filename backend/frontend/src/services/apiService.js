import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const apiService = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证token
apiService.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
apiService.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token过期，清除本地存储
      localStorage.removeItem('authToken');
      // 可以在这里重定向到登录页
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 视频相关API
export const videoApi = {
  // 获取视频列表
  getVideos: async (params = {}) => {
    const response = await apiService.get('/api/v1/videos', { params });
    return response.data;
  },

  // 获取单个视频详情
  getVideo: async (videoId) => {
    const response = await apiService.get(`/api/v1/videos/${videoId}`);
    return response.data;
  },

  // 下载视频
  downloadVideo: async (url, projectId = 1) => {
    const response = await apiService.post('/api/v1/videos/download', {
      url,
      project_id: projectId
    });
    return response.data;
  },

  // 获取视频进度
  getVideoProgress: async (videoId) => {
    const response = await apiService.get(`/api/v1/videos/${videoId}/progress`);
    return response.data;
  },

  // 删除视频
  deleteVideo: async (videoId) => {
    const response = await apiService.delete(`/api/v1/videos/${videoId}`);
    return response.data;
  },

  // 获取视频切片
  getVideoSlices: async (videoId) => {
    const response = await apiService.get(`/api/v1/videos/${videoId}/slices`);
    return response.data;
  },

  // 创建视频切片
  createVideoSlice: async (videoId, data) => {
    const response = await apiService.post(`/api/v1/videos/${videoId}/slices`, data);
    return response.data;
  }
};

// 项目相关API
export const projectApi = {
  // 获取项目列表
  getProjects: async () => {
    const response = await apiService.get('/api/v1/projects');
    return response.data;
  },

  // 创建项目
  createProject: async (data) => {
    const response = await apiService.post('/api/v1/projects', data);
    return response.data;
  },

  // 获取项目详情
  getProject: async (projectId) => {
    const response = await apiService.get(`/api/v1/projects/${projectId}`);
    return response.data;
  }
};

// 认证相关API
export const authApi = {
  // 用户登录
  login: async (credentials) => {
    const response = await apiService.post('/api/v1/auth/login', credentials);
    return response.data;
  },

  // 用户注册
  register: async (userData) => {
    const response = await apiService.post('/api/v1/auth/register', userData);
    return response.data;
  },

  // 获取用户信息
  getProfile: async () => {
    const response = await apiService.get('/api/v1/auth/profile');
    return response.data;
  }
};

export default apiService;