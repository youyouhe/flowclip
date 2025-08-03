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
  getProjects: () =>
    api.get('/projects'),
  getProject: (id: number) =>
    api.get(`/projects/${id}`),
  createProject: (data: any) =>
    api.post('/projects', data),
  updateProject: (id: number, data: any) =>
    api.put(`/projects/${id}`, data),
  deleteProject: (id: number) =>
    api.delete(`/projects/${id}`),
};

// 视频相关API
export const videoAPI = {
  getVideos: () =>
    api.get('/videos'),
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
  splitAudio: (videoId: number) =>
    api.post(`/videos/${videoId}/split-audio`),
  generateSrt: (videoId: number, splitFiles?: any[]) =>
    api.post(`/videos/${videoId}/generate-srt`, { split_files: splitFiles }),
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
  getSliceSubSlices: (sliceId: number) =>
    api.get(`/video-slice/slice-sub-slices/${sliceId}`),
  deleteAnalysis: (analysisId: number) =>
    api.delete(`/video-slice/analysis/${analysisId}`),
  deleteSlice: (sliceId: number) =>
    api.delete(`/video-slice/slice/${sliceId}`),
  deleteSubSlice: (subSliceId: number) =>
    api.delete(`/video-slice/sub-slice/${subSliceId}`),
};

// Dashboard相关API
export const dashboardAPI = {
  getDashboardStats: () =>
    api.get('/status/dashboard'),
};

export default api;