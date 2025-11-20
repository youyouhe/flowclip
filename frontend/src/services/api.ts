import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://backend:8001';

// 处理代理路径，避免重复的 /api
const getBaseURL = () => {
  console.log('🔍 Debug - API_BASE_URL:', API_BASE_URL);
  
  if (API_BASE_URL.startsWith('/')) {
    // 相对路径，需要完整的 /api/v1 前缀
    const baseURL = '/api/v1';
    console.log('🔍 Debug - Using relative baseURL:', baseURL);
    return baseURL;
  } else {
    // 绝对路径，需要完整的 /api/v1
    const baseURL = `${API_BASE_URL}/api/v1`;
    console.log('🔍 Debug - Using absolute baseURL:', baseURL);
    return baseURL;
  }
};

const baseURL = getBaseURL();
console.log('🔍 Debug - Final API baseURL:', baseURL);

const api = axios.create({
  baseURL: baseURL,
  timeout: 120000, // 设置为120秒
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

// 响应拦截器处理错误和编码
api.interceptors.response.use(
  (response) => {
    // 确保响应数据被正确解码为UTF-8
    if (response.data && typeof response.data === 'string') {
      try {
        response.data = JSON.parse(response.data);
      } catch (e) {
        console.warn('Failed to parse response data as JSON:', e);
      }
    }
    return response;
  },
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
  login: (username: string, password: string) => {
    return api.post('/auth/login', {
      username,
      password,
    });
  },
  register: (userData: any) =>
    api.post('/auth/register', userData),
  getCurrentUser: () =>
    api.get('/auth/me'),
};

// 项目相关API
export const projectAPI = {
  getProjects: (params?: any) =>
    api.get('/projects/', { params }),
  getProject: (id: number) =>
    api.get(`/projects/${id}`),
  createProject: (data: any) =>
    api.post('/projects/', data),
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
    api.get('/videos/', { params }),
  getActiveVideos: () =>
    api.get('/videos/active'),
  getVideo: (id: number) =>
    api.get(`/videos/${id}`),
  createVideo: (data: any) =>
    api.post('/videos/', data),
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
  uploadVideo: (formData: FormData) =>
    api.post('/videos/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 5分钟超时
    }),
  uploadChunk: (formData: FormData) =>
    api.post('/videos/upload-chunk', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 5分钟超时
    }),
  getVideoDownloadUrl: (id: number, expiry: number = 3600) =>
    api.get(`/videos/${id}/download-url?expiry=${expiry}`),
  
  // 视频流端点 - 用于播放视频
  getVideoStreamUrl: (id: number, token: string) =>
    api.get(`/videos/${id}/stream?token=${token}`),
  
  
  // 通用MinIO资源URL获取
  getMinioResourceUrl: (objectPath: string, expiry: number = 3600) =>
    api.get(`/minio/minio-url?object_path=${encodeURIComponent(objectPath)}&expiry=${expiry}`),
  
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
  
  // 新增：根据路径获取缩略图URL
  getThumbnailUrlByPath: (path: string) =>
    api.get(`/resources/thumbnail-url?path=${encodeURIComponent(path)}`),
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
    }, {
      timeout: 180000, // 3分钟超时，给LLM更多处理时间
    }),
  updateSystemPrompt: (systemPrompt: string) =>
    api.post('/llm/system-prompt', { system_prompt: systemPrompt }),
  getCurrentSystemPrompt: () =>
    api.get('/llm/system-prompt'),
  getAvailableModels: () =>
    api.get('/llm/models', {
      timeout: 60000, // 1分钟超时
    }),
  testLongRequest: () => {
    console.log('🔍 [API] 准备发送测试请求...', new Date().toISOString());
    return api.get('/llm/test-long-request', {
      timeout: 180000, // 3分钟超时
    });
  },
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
  getSliceSrtContent: (sliceId: number) =>
    api.get(`/video-slice/slice-srt-content/${sliceId}`),
  getSubSliceSrtContent: (subSliceId: number) =>
    api.get(`/video-slice/sub-slice-srt-content/${subSliceId}`),
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

// CapCut相关API
export const capcutAPI = {
  exportSlice: (sliceId: number, draftFolder: string) =>
    api.post(`/capcut/export-slice/${sliceId}`, { draft_folder: draftFolder }),
  getStatus: () =>
    api.get('/capcut/status'),
};

// Jianying相关API
export const jianyingAPI = {
  exportSlice: (sliceId: number, draftFolder: string) =>
    api.post(`/jianying/export-slice-jianying/${sliceId}`, { draft_folder: draftFolder }),
  getStatus: () =>
    api.get('/jianying/status'),
};

// ASR相关API
export const asrAPI = {
  getStatus: () =>
    api.get('/asr/status'),
  // 测试ASR服务 (通过后端代理)
  testAsrService: async (file: File, modelType: string = 'whisper', asrApiKey?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_type', modelType);

    // 如果提供了asr_api_key，添加到表单数据中
    if (asrApiKey) {
      formData.append('asr_api_key', asrApiKey);
    }

    console.log('🔧 Testing ASR service through backend proxy:', { modelType, hasApiKey: !!asrApiKey });

    try {
      const response = await api.post('/system/test-asr', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5分钟超时
      });

      console.log('🔧 ASR service test response:', response.data);
      return response;
    } catch (error) {
      console.error('🔧 ASR service test error:', error);
      throw error;
    }
  },
};

// 资源管理相关API
export const resourceAPI = {
  // 资源管理
  getResources: (params: any) =>
    api.get('/resources/', { params }),
  getResource: (id: number) =>
    api.get(`/resources/${id}`),
  createResource: (data: any) =>
    api.post('/resources', data),
  updateResource: (id: number, data: any) =>
    api.put(`/resources/${id}`, data),
  deleteResource: (id: number) =>
    api.delete(`/resources/${id}`),
  uploadResource: (formData: FormData) =>
    api.post('/resources/upload', formData),
  toggleResourceActiveStatus: (id: number, IsActive: boolean) =>
    api.put(`/resources/${id}/activate`, { is_active: IsActive }),
  
  // 标签管理
  getResourceTags: (params?: any) =>
    api.get('/resources/tags', { params }),
  createResourceTag: (data: any) =>
    api.post('/resources/tags', data),
  deleteResourceTag: (id: number) =>
    api.delete(`/resources/tags/${id}`),
  getResourceViewUrl: (id: number) =>
    api.get(`/resources/${id}/view-url`),
  getResourceDownloadUrl: (id: number) =>
    api.get(`/resources/${id}/download-url`),
};

// 系统配置相关API
export const systemConfigAPI = {
  getSystemConfigs: () =>
    api.get('/system/system-config'),
  updateSystemConfig: (data: any) =>
    api.post('/system/system-config', data),
  updateSystemConfigs: (data: any) =>
    api.post('/system/system-config/batch', data),
  checkServiceStatus: (serviceName: string) =>
    api.get(`/system/system-config/service-status/${serviceName}`),
};

// 仪表板相关API
export const dashboardAPI = {
  getDashboardStats: () =>
    api.get('/status/dashboard'),
  getRunningVideoIds: () =>
    api.get('/status/videos/running'),
};

export default api;