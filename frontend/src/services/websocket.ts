/**
 * WebSocket服务 - 用于实时进度更新
 */
class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000;
  private listeners: Map<string, Function[]> = new Map();
  private token: string | null = null;
  private isConnected = false;

  /**
   * 初始化WebSocket连接
   */
  connect(token: string): void {
    console.log('🔌 [WebSocket] Attempting to connect with token:', token ? `${token.substring(0, 20)}...` : 'null');
    console.log('🔌 [WebSocket] Current connection state:', this.ws?.readyState);
    console.log('🔌 [WebSocket] Is connected flag:', this.isConnected);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('🔌 [WebSocket] Already connected, skipping');
      return;
    }

    this.token = token;
    // 直接连接到后端WebSocket地址，绕过Vite代理
    const wsUrl = `ws://192.168.8.107:8001/api/v1/ws/progress/${token}`;
    
    console.log('🔌 [WebSocket] Connection URL:', wsUrl);
    console.log('🔌 [WebSocket] Ready state before connection:', this.ws?.readyState);
    console.log('🔌 [WebSocket] Browser WebSocket support:', typeof WebSocket !== 'undefined');
    
    // 检查WebSocket URL格式
    try {
      const urlObj = new URL(wsUrl);
      console.log('🔌 [WebSocket] URL validation:');
      console.log('   - Protocol:', urlObj.protocol);
      console.log('   - Host:', urlObj.host);
      console.log('   - Path:', urlObj.pathname);
      console.log('   - Token length:', urlObj.pathname.split('/').pop()?.length || 0);
    } catch (error) {
      console.error('❌ [WebSocket] Invalid WebSocket URL:', error);
    }
    
    try {
      this.ws = new WebSocket(wsUrl);
      console.log('🔌 [WebSocket] WebSocket object created');
      
      this.ws.onopen = () => {
        console.log('✅ [WebSocket] Connected successfully!');
        console.log('🔌 [WebSocket] Ready state:', this.ws?.readyState);
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connected');
      };
      
      this.ws.onmessage = (event) => {
        console.log('📨 [WebSocket] Raw message received:', event.data);
        try {
          const data = JSON.parse(event.data);
          console.log('📨 [WebSocket] Parsed message:', data);
          console.log('📨 [WebSocket] Message type:', data.type);
          this.handleMessage(data);
        } catch (error) {
          console.error('❌ [WebSocket] Failed to parse message:', error);
          console.error('❌ [WebSocket] Raw message that failed to parse:', event.data);
        }
      };
      
      this.ws.onclose = (event) => {
        console.log('🔌 [WebSocket] Connection closed:');
        console.log('   - Code:', event.code);
        console.log('   - Reason:', event.reason);
        console.log('   - Was clean:', event.wasClean);
        this.isConnected = false;
        this.emit('disconnected');
        this.handleReconnect();
      };
      
      this.ws.onerror = (error) => {
        console.error('❌ [WebSocket] Error occurred:', error);
        console.error('❌ [WebSocket] Ready state:', this.ws?.readyState);
        console.error('❌ [WebSocket] Buffered amount:', this.ws?.bufferedAmount);
        this.emit('error', error);
      };
      
      // 监听连接状态变化
      
    } catch (error) {
      console.error('❌ [WebSocket] Failed to create WebSocket connection:', error);
      console.error('❌ [WebSocket] Error type:', typeof error);
      console.error('❌ [WebSocket] Error message:', (error as Error).message);
      this.handleReconnect();
    }
  }

  /**
   * 处理WebSocket消息
   */
  private handleMessage(data: any): void {
    switch (data.type) {
      case 'progress_update':
        this.emit('progress_update', data);
        break;
      case 'log_update':
        this.emit('log_update', data);
        break;
      case 'pong':
        this.emit('pong', data);
        break;
      case 'error':
        this.emit('error', data);
        break;
      default:
        console.log('Unhandled WebSocket message type:', data.type);
    }
  }

  /**
   * 订阅视频进度更新
   */
  subscribeVideoProgress(videoId: number): void {
    console.log('📡 [WebSocket] Attempting to subscribe to video progress:', videoId);
    console.log('📡 [WebSocket] WebSocket ready state:', this.ws?.readyState);
    console.log('📡 [WebSocket] WebSocket connected:', this.isConnected);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'subscribe',
        video_id: videoId
      };
      const messageStr = JSON.stringify(message);
      console.log('📡 [WebSocket] Sending subscribe message:', messageStr);
      
      try {
        this.ws.send(messageStr);
        console.log('✅ [WebSocket] Subscribe message sent successfully for video:', videoId);
      } catch (error) {
        console.error('❌ [WebSocket] Failed to send subscribe message:', error);
      }
    } else {
      console.warn('⚠️ [WebSocket] Cannot subscribe - WebSocket not connected');
      console.warn('⚠️ [WebSocket] Ready state:', this.ws?.readyState);
      console.warn('⚠️ [WebSocket] Connected flag:', this.isConnected);
    }
  }

  /**
   * 发送心跳
   */
  sendPing(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type: 'ping' });
      console.log('💓 [WebSocket] Sending ping:', message);
      this.ws.send(message);
    } else {
      console.warn('💓 [WebSocket] Cannot send ping - WebSocket not connected');
    }
  }

  /**
   * 请求所有视频的最新状态更新
   */
  requestStatusUpdate(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ type: 'request_status_update' });
      console.log('🔄 [WebSocket] Requesting status update:', message);
      this.ws.send(message);
    } else {
      console.warn('🔄 [WebSocket] Cannot request status update - WebSocket not connected');
    }
  }

  /**
   * 处理重连
   */
  private handleReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.token) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      setTimeout(() => {
        this.connect(this.token!);
      }, this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1));
    } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('max_reconnect_reached');
    }
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
    }
  }

  /**
   * 事件监听
   */
  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  /**
   * 移除事件监听
   */
  off(event: string, callback: Function): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      const index = eventListeners.indexOf(callback);
      if (index > -1) {
        eventListeners.splice(index, 1);
      }
    }
  }

  /**
   * 触发事件
   */
  private emit(event: string, data?: any): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      eventListeners.forEach(callback => callback(data));
    }
  }

  /**
   * 获取连接状态
   */
  get connected(): boolean {
    return this.isConnected;
  }
}

// 创建单例实例
export const wsService = new WebSocketService();

// 心跳定时器
let heartbeatInterval: number | null = null;

/**
 * 启动心跳
 */
export const startHeartbeat = (): void => {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }
  
  heartbeatInterval = setInterval(() => {
    if (wsService.connected) {
      wsService.sendPing();
    }
  }, 10000); // 每10秒发送一次心跳
};

/**
 * 停止心跳
 */
export const stopHeartbeat = (): void => {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
};

export default WebSocketService;
