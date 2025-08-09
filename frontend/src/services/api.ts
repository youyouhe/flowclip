import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://192.168.8.107:8001';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
});

// 请求拦截器添加token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 认证相关API
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  register: (userData: any) =>
    api.post('/auth/register', userData),
  getCurrentUser: () =>
    api.get('/auth/me'),
};

// 项目相关API
export const projectAPI = {
  getProjects: (params?: any) =>
    api.get('/projects', { params }),
  getProject: (id: number) =>
    api.get(`/projects/${id}`),
  createProject: (data: any) =>
    api.post('/projects', data),
  updateProject: (id: number, data: any) =>
    api.put(`/projects/${id}`, data),
  deleteProject: (id: number) =>
    api.delete(`/projects/${id}`),
  getProjectVideos: (projectId: number) =>
    api.get(`/projects/${projectId}/videos`),
};

// 视频相关API
export const videoAPI = {
  getVideos: (params?: any) =>
    api.get('/videos', { params }),
  getActiveVideos: () =>
    api.get('/videos/active'),
  getVideo: (id: number) =>
    api.get(`/videos/${id}`),
  createVideo: (data: any) =>
    api.post('/videos', data),
  updateVideo: (id: number, data: any) =>
    api.put(`/videos/${id}`, data),
  deleteVideo: (id: number) =>
    api.delete(`/videos/${id}`),
  downloadVideo: (url: string, projectId: number, quality: string) =>
    api.post(`/videos/download?quality=${quality}`, { url, project_id: projectId }),
  downloadVideoWithCookies: (formData: FormData, quality: string = 'best') =>
    api.post(`/videos/download?quality=${quality}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }),
  getVideoDownloadUrl: (id: number, expiry: number = 3600) =>
    api.get(`/videos/${id}/download-url?expiry=${expiry}`),
  
    extractAudio: (videoId: number) =>
    api.post(`/videos/${videoId}/extract-audio`),
    generateSrt: (videoId: number) =>
    api.post(`/videos/${videoId}/generate-srt`),
  getTaskStatus: (videoId: number, taskId: string) =>
    api.get(`/videos/${videoId}/task-status/${taskId}`),
  getAudioDownloadUrl: (videoId: number, expiry: number = 3600) =>
    api.get(`/videos/${videoId}/audio-download-url?expiry=${expiry}`),
  getSrtDownloadUrl: (videoId: number, expiry: number = 3600) =>
    api.get(`/videos/${videoId}/srt-download-url?expiry=${expiry}`),
  getSrtContent: (videoId: number) =>
    api.get(`/videos/${videoId}/srt-content`),
  getThumbnailDownloadUrl: (videoId: number, expiry: number = 3600) =>
    api.get(`/videos/${videoId}/thumbnail-download-url?expiry=${expiry}`),
  getProcessingStatus: (videoId: number) =>
    api.get(`/videos/${videoId}/processing-status`),
};

// LLM相关API
export const llmAPI = {
  chat: (message: string, videoId?: number, systemPrompt?: string, useSrtContext: boolean = false) =>
    api.post('/llm/chat', {
      message,
      video_id: videoId,
      system_prompt: systemPrompt,
      use_srt_context: useSrtContext
    }),
  updateSystemPrompt: (systemPrompt: string) =>
    api.post('/llm/system-prompt', { system_prompt: systemPrompt }),
  getCurrentSystemPrompt: () =>
    api.get('/llm/system-prompt'),
  getAvailableModels: () =>
    api.get('/llm/models'),
};

// 视频切片相关API
export const videoSliceAPI = {
  validateSliceData: (data: any) =>
    api.post('/video-slice/validate-slice-data', data),
  processSlices: (data: any) =>
    api.post('/video-slice/process-slices', data),
  getVideoAnalyses: (videoId: number) =>
    api.get(`/video-slice/video-analyses/${videoId}`),
  getVideoSlices: (videoId: number) =>
    api.get(`/video-slice/video-slices/${videoId}`),
  getSliceDetail: (sliceId: number) =>
    api.get(`/video-slice/slice-detail/${sliceId}`),
  getSliceDownloadUrl: (sliceId: number, expiry: number = 3600) =>
    api.get(`/video-slice/slice-download-url/${sliceId}?expiry=${expiry}`),
  getSubSliceDownloadUrl: (subSliceId: number, expiry: number = 3600) =>
    api.get(`/video-slice/sub-slice-download-url/${subSliceId}?expiry=${expiry}`),
  getSliceSubSlices: (sliceId: number) =>
    api.get(`/video-slice/slice-sub-slices/${sliceId}`),
  deleteAnalysis: (analysisId: number) =>
    api.delete(`/video-slice/analysis/${analysisId}`),
  deleteSlice: (sliceId: number) =>
    api.delete(`/video-slice/slice/${sliceId}`),
  deleteSubSlice: (subSliceId: number) =>
    api.delete(`/video-slice/sub-slice/${subSliceId}`),
};

// 日志管理相关API
export const logAPI = {
  // 获取处理日志列表
  getProcessingLogs: (params: {
    video_id?: number;
    task_id?: number;
    task_type?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
    level?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value.toString());
      }
    });
    return api.get(`/processing/logs?${queryParams.toString()}`);
  },

  // 获取特定任务的所有日志
  getTaskLogs: (taskId: number) =>
    api.get(`/processing/logs/task/${taskId}`),

  // 获取视频的日志汇总
  getVideoLogsSummary: (videoId: number) =>
    api.get(`/processing/logs/video/${videoId}`),

  // 获取日志统计信息
  getLogsStatistics: (params: {
    video_id?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value.toString());
      }
    });
    return api.get(`/processing/logs/statistics?${queryParams.toString()}`);
  },

  // 删除特定日志
  deleteLog: (logId: number) =>
    api.delete(`/processing/logs/${logId}`),

  // 删除任务的所有日志
  deleteTaskLogs: (taskId: number) =>
    api.delete(`/processing/logs/task/${taskId}`),

  // 删除视频的所有日志
  deleteVideoLogs: (videoId: number) =>
    api.delete(`/processing/logs/video/${videoId}`),
};

// Dashboard相关API
export const dashboardAPI = {
  getDashboardStats: () =>
    api.get('/status/dashboard'),
  getRunningVideoIds: () =>
    api.get('/status/videos/running'),
};

export default api;