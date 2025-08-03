import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../hooks/useAuth';
import { apiService } from '../services/apiService';
import { DownloadProgressManager } from '../services/websocketService';
import './VideoManagementPage.css';

const VideoManagementPage = () => {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloadingVideos, setDownloadingVideos] = useState(new Set());
  const [progressData, setProgressData] = useState({});
  
  const { user, token } = useAuth();
  const progressManagerRef = useRef(null);
  const wsRef = useRef(null);

  // 初始化进度管理器
  useEffect(() => {
    if (token) {
      progressManagerRef.current = new DownloadProgressManager();
      
      // 监听进度更新
      progressManagerRef.current.on('progressUpdate', (data) => {
        console.log('收到进度更新:', data);
        setProgressData(prev => ({
          ...prev,
          [data.video_id]: data
        }));
      });

      progressManagerRef.current.on('downloadComplete', (data) => {
        console.log('下载完成:', data);
        setDownloadingVideos(prev => {
          const newSet = new Set(prev);
          newSet.delete(data.video_id);
          return newSet;
        });
        
        // 刷新视频列表
        loadVideos();
      });

      progressManagerRef.current.on('downloadFailed', (data) => {
        console.error('下载失败:', data);
        setDownloadingVideos(prev => {
          const newSet = new Set(prev);
          newSet.delete(data.video_id);
          return newSet;
        });
        
        setError(`下载失败: ${data.error}`);
      });

      progressManagerRef.current.on('connected', () => {
        console.log('WebSocket连接已建立');
      });

      progressManagerRef.current.on('error', (data) => {
        console.error('WebSocket错误:', data);
      });

      progressManagerRef.current.on('subscribed', (data) => {
        console.log('已订阅视频进度:', data);
      });

      return () => {
        if (progressManagerRef.current) {
          progressManagerRef.current.disconnect();
        }
      };
    }
  }, [token]);

  // 加载视频列表
  const loadVideos = async () => {
    try {
      setLoading(true);
      const response = await apiService.get('/api/v1/videos', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setVideos(response.data.videos || []);
      
      // 识别正在下载的视频
      const downloading = response.data.videos.filter(v => 
        v.status === 'downloading' || v.status === 'processing'
      ).map(v => v.id);
      
      setDownloadingVideos(new Set(downloading));
      
      // 为正在下载的视频初始化WebSocket连接
      downloading.forEach(videoId => {
        if (progressManagerRef.current) {
          progressManagerRef.current.initialize(token, videoId);
        }
      });
      
    } catch (err) {
      setError(err.message || '加载视频失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVideos();
  }, [token]);

  // 开始下载视频
  const handleDownload = async (url) => {
    try {
      setError(null);
      const response = await apiService.post('/api/v1/videos/download', {
        url: url,
        project_id: 1 // 默认项目
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      const { video_id } = response.data;
      console.log('下载任务已启动，video_id:', video_id);
      setDownloadingVideos(prev => new Set(prev).add(video_id));
      
      // 初始化进度追踪
      if (progressManagerRef.current) {
        console.log('初始化WebSocket连接...');
        await progressManagerRef.current.initialize(token, video_id);
        console.log('WebSocket连接初始化完成');
      }
      
    } catch (err) {
      console.error('下载失败:', err);
      setError(err.message || '下载失败');
    }
  };

  // 删除视频
  const handleDelete = async (videoId) => {
    try {
      await apiService.delete(`/api/v1/videos/${videoId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      loadVideos();
    } catch (err) {
      setError(err.message || '删除失败');
    }
  };

  // 获取进度显示
  const getProgressDisplay = (video) => {
    const progress = progressData[video.id];
    if (progress) {
      return {
        progress: progress.download_progress || 0,
        status: progress.processing_message || '处理中...',
        stage: progress.processing_stage || 'unknown'
      };
    }
    
    if (video.status === 'downloading') {
      return {
        progress: video.download_progress || 0,
        status: video.processing_message || '下载中...',
        stage: 'download'
      };
    }
    
    return null;
  };

  // 获取状态颜色
  const getStatusColor = (status) => {
    const colors = {
      'pending': '#ff9800',
      'downloading': '#2196f3',
      'processing': '#9c27b0',
      'completed': '#4caf50',
      'failed': '#f44336',
      'ready': '#4caf50'
    };
    return colors[status] || '#666';
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <div className="video-management-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>加载视频中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-management-page">
      <div className="page-header">
        <h1>视频管理</h1>
        <div className="header-actions">
          <button 
            className="refresh-btn" 
            onClick={loadVideos}
            disabled={loading}
          >
            刷新
          </button>
        </div>
      </div>

      {error && (
        <div className="error-message">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="video-grid">
        {videos.map(video => {
          const progress = getProgressDisplay(video);
          const isDownloading = downloadingVideos.has(video.id);
          
          return (
            <div key={video.id} className="video-card">
              <div className="video-thumbnail">
                {video.thumbnail_url ? (
                  <img src={video.thumbnail_url} alt={video.title} />
                ) : (
                  <div className="thumbnail-placeholder">
                    <span>无缩略图</span>
                  </div>
                )}
              </div>
              
              <div className="video-info">
                <h3>{video.title}</h3>
                <p className="video-url">{video.url}</p>
                
                <div className="video-meta">
                  <span className="video-duration">
                    时长: {video.duration || '未知'}
                  </span>
                  <span className="video-size">
                    大小: {formatFileSize(video.file_size)}
                  </span>
                </div>

                <div className="video-status">
                  <span 
                    className="status-badge" 
                    style={{ backgroundColor: getStatusColor(video.status) }}
                  >
                    {video.status}
                  </span>
                </div>

                {progress && (
                  <div className="progress-section">
                    <div className="progress-info">
                      <span>{progress.status}</span>
                      <span>{progress.progress.toFixed(1)}%</span>
                    </div>
                    <div className="progress-bar">
                      <div 
                        className="progress-fill" 
                        style={{ width: `${progress.progress}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>

              <div className="video-actions">
                {video.status === 'completed' ? (
                  <>
                    <button 
                      className="action-btn view-btn"
                      onClick={() => window.location.href = `/videos/${video.id}`}
                    >
                      查看详情
                    </button>
                    <button 
                      className="action-btn delete-btn"
                      onClick={() => handleDelete(video.id)}
                    >
                      删除
                    </button>
                  </>
                ) : isDownloading ? (
                  <button 
                    className="action-btn downloading-btn"
                    disabled
                  >
                    下载中...
                  </button>
                ) : (
                  <button 
                    className="action-btn retry-btn"
                    onClick={() => handleDownload(video.url)}
                  >
                    重新下载
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {videos.length === 0 && !error && (
        <div className="empty-state">
          <h3>暂无视频</h3>
          <p>开始添加视频进行下载和处理</p>
        </div>
      )}
    </div>
  );
};

export default VideoManagementPage;