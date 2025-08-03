/**
 * WebSocket服务 - 实时进度追踪
 * 连接后端WebSocket端点，接收Celery下载任务进度
 */

class DownloadProgressManager {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.isConnected = false;
    this.subscribedVideos = new Set();
    this.eventListeners = {};
    this.pingInterval = null;
    this.pollingInterval = null;
    this.isPolling = false;
  }

  /**
   * 初始化WebSocket连接
   * @param {string} token - 用户认证token
   * @param {number} videoId - 视频ID
   */
  async initialize(token, videoId) {
    console.log('初始化WebSocket连接:', { token: token ? '已提供' : '未提供', videoId });
    
    this.token = token;
    this.videoId = videoId;
    
    if (!token || !videoId) {
      console.error('Token或videoId不能为空');
      return;
    }

    // 如果已连接，只需订阅新视频
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket已连接，直接订阅视频:', videoId);
      this.subscribeVideo(videoId);
      return;
    }

    console.log('建立新的WebSocket连接...');
    await this.connect(token);
    this.subscribeVideo(videoId);
    console.log('WebSocket连接和订阅完成');
  }

  /**
   * 建立WebSocket连接
   */
  async connect(token) {
    const wsUrl = `ws://localhost:8001/api/v1/ws/progress/${token}`;
    console.log('尝试连接WebSocket:', wsUrl);
    
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
          console.log('WebSocket连接已建立');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          this.emit('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('解析消息失败:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket连接关闭:', event.code, event.reason);
          this.isConnected = false;
          this.stopHeartbeat();
          this.handleReconnect();
          reject(new Error(`WebSocket连接关闭: ${event.reason}`));
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket错误:', error);
          this.isConnected = false;
          reject(error);
        };

        // 设置连接超时
        setTimeout(() => {
          if (this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket连接超时');
            reject(new Error('WebSocket连接超时'));
          }
        }, 10000);

      } catch (error) {
        console.error('WebSocket连接失败:', error);
        this.handleReconnect();
        reject(error);
      }
    });
  }

  /**
   * 订阅特定视频的进度
   */
  subscribeVideo(videoId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket未连接，无法订阅');
      return;
    }

    if (this.subscribedVideos.has(videoId)) {
      console.log(`视频 ${videoId} 已订阅，跳过`);
      return; // 已订阅
    }

    this.subscribedVideos.add(videoId);
    
    const message = {
      type: 'subscribe',
      video_id: parseInt(videoId)
    };

    this.ws.send(JSON.stringify(message));
    console.log(`已订阅视频 ${videoId} 的进度`);
    this.emit('subscribed', { video_id: videoId });
  }

  /**
   * 处理接收到的消息
   */
  handleMessage(data) {
    switch (data.type) {
      case 'progress_update':
        this.emit('progressUpdate', data);
        break;
      case 'download_complete':
        this.emit('downloadComplete', data);
        break;
      case 'download_failed':
        this.emit('downloadFailed', data);
        break;
      case 'error':
        console.error('服务器错误:', data.message);
        this.emit('error', data);
        break;
      default:
        console.log('未知消息类型:', data.type);
    }
  }

  /**
   * 心跳机制
   */
  startHeartbeat() {
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // 每30秒发送一次心跳
  }

  stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * 重连机制
   */
  handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      
      setTimeout(async () => {
        if (this.token) {
          try {
            await this.connect(this.token);
            // 重连成功后重新订阅视频
            if (this.videoId && this.isConnected) {
              this.subscribeVideo(this.videoId);
            }
          } catch (error) {
            console.error('重连失败:', error);
          }
        }
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.log('重连失败，切换到轮询模式');
      this.startPolling();
    }
  }

  /**
   * 轮询模式（WebSocket失败时回退）
   */
  startPolling() {
    if (this.isPolling) return;
    
    this.isPolling = true;
    console.log('启动轮询模式');
    
    this.pollingInterval = setInterval(async () => {
      if (this.subscribedVideos.size === 0) return;
      
      for (const videoId of this.subscribedVideos) {
        try {
          const response = await fetch(`/api/v1/videos/${videoId}/progress`, {
            headers: {
              'Authorization': `Bearer ${this.token}`
            }
          });
          
          if (response.ok) {
            const data = await response.json();
            this.emit('progressUpdate', {
              video_id: parseInt(videoId),
              ...data
            });
          }
        } catch (error) {
          console.error('轮询失败:', error);
        }
      }
    }, 10000); // 每10秒轮询一次，降低频率
  }

  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    this.isPolling = false;
  }

  /**
   * 事件监听
   */
  on(event, callback) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  off(event, callback) {
    if (this.eventListeners[event]) {
      this.eventListeners[event] = this.eventListeners[event].filter(cb => cb !== callback);
    }
  }

  emit(event, data) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach(callback => callback(data));
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    this.stopHeartbeat();
    this.stopPolling();
    
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    this.isConnected = false;
    this.subscribedVideos.clear();
    this.eventListeners = {};
  }

  /**
   * 获取连接状态
   */
  getConnectionStatus() {
    if (this.isConnected) return 'connected';
    if (this.isPolling) return 'polling';
    return 'disconnected';
  }
}

// 单例实例
export const progressService = new DownloadProgressManager();

// 兼容类名
export { DownloadProgressManager };