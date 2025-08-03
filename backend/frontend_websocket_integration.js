/**
 * 下载页面WebSocket进度更新集成
 * 文件：frontend_websocket_integration.js
 */

class DownloadProgressManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.videoId = null;
        this.userId = null;
        this.token = null;
        this.reconnectInterval = 3000;
        this.maxReconnectAttempts = 5;
        this.reconnectAttempts = 0;
        this.progressCallbacks = new Set();
    }

    /**
     * 初始化WebSocket连接
     * @param {string} token - 用户认证token
     * @param {number} videoId - 视频ID
     */
    async initialize(token, videoId) {
        this.token = token;
        this.videoId = videoId;
        
        try {
            await this.connect();
            this.subscribeToVideo(videoId);
        } catch (error) {
            console.error('WebSocket初始化失败:', error);
            // 回退到轮询
            this.startPolling(videoId);
        }
    }

    /**
     * 建立WebSocket连接
     */
    async connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(`ws://localhost:8001/ws/progress/${this.token}`);
                
                this.ws.onopen = () => {
                    console.log('WebSocket连接已建立');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    resolve();
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleProgressUpdate(data);
                    } catch (error) {
                        console.error('解析WebSocket消息失败:', error);
                    }
                };
                
                this.ws.onclose = (event) => {
                    console.log('WebSocket连接关闭:', event.code);
                    this.isConnected = false;
                    this.scheduleReconnect();
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket错误:', error);
                    reject(error);
                };
                
            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * 订阅特定视频的进度
     * @param {number} videoId 
     */
    subscribeToVideo(videoId) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                type: 'subscribe',
                video_id: videoId
            };
            this.ws.send(JSON.stringify(message));
            console.log(`已订阅视频 ${videoId} 的进度更新`);
        }
    }

    /**
     * 处理进度更新
     * @param {Object} data 
     */
    handleProgressUpdate(data) {
        if (data.type === 'progress_update') {
            this.notifyProgressCallbacks(data);
            this.updateUI(data);
        }
    }

    /**
     * 更新UI显示
     * @param {Object} progressData 
     */
    updateUI(progressData) {
        const { video_id, download_progress, processing_message, processing_stage, status } = progressData;
        
        // 更新进度条
        const progressBar = document.querySelector(`#progress-${video_id} .progress-bar`);
        if (progressBar) {
            progressBar.style.width = `${download_progress}%`;
            progressBar.setAttribute('aria-valuenow', download_progress);
        }
        
        // 更新进度文本
        const progressText = document.querySelector(`#progress-${video_id} .progress-text`);
        if (progressText) {
            progressText.textContent = `${download_progress.toFixed(1)}%`;
        }
        
        // 更新状态消息
        const statusMessage = document.querySelector(`#progress-${video_id} .status-message`);
        if (statusMessage) {
            statusMessage.textContent = processing_message || '正在处理...';
        }
        
        // 更新阶段指示器
        const stageIndicator = document.querySelector(`#progress-${video_id} .stage-indicator`);
        if (stageIndicator) {
            stageIndicator.textContent = this.getStageText(processing_stage);
        }
        
        // 完成状态处理
        if (status === 'completed') {
            this.handleDownloadComplete(video_id);
        } else if (status === 'failed') {
            this.handleDownloadFailed(video_id, progressData.processing_error);
        }
    }

    /**
     * 获取阶段文本描述
     * @param {string} stage 
     * @returns {string}
     */
    getStageText(stage) {
        const stageMap = {
            'preparing': '准备中',
            'download': '下载中',
            'merging': '合并中',
            'converting': '转换中',
            'completed': '已完成',
            'failed': '失败'
        };
        return stageMap[stage] || stage;
    }

    /**
     * 处理下载完成
     * @param {number} videoId 
     */
    handleDownloadComplete(videoId) {
        console.log(`视频 ${videoId} 下载完成`);
        
        // 显示完成消息
        const completeMessage = document.querySelector(`#progress-${videoId} .complete-message`);
        if (completeMessage) {
            completeMessage.style.display = 'block';
            completeMessage.textContent = '下载完成！';
        }
        
        // 隐藏进度条，显示完成按钮
        const progressContainer = document.querySelector(`#progress-${videoId}`);
        if (progressContainer) {
            progressContainer.classList.add('completed');
        }
        
        // 触发完成回调
        this.emit('downloadComplete', { videoId });
    }

    /**
     * 处理下载失败
     * @param {number} videoId 
     * @param {string} error 
     */
    handleDownloadFailed(videoId, error) {
        console.error(`视频 ${videoId} 下载失败:`, error);
        
        const errorMessage = document.querySelector(`#progress-${videoId} .error-message`);
        if (errorMessage) {
            errorMessage.style.display = 'block';
            errorMessage.textContent = `下载失败: ${error}`;
        }
        
        this.emit('downloadFailed', { videoId, error });
    }

    /**
     * 添加进度回调
     * @param {Function} callback 
     */
    onProgress(callback) {
        this.progressCallbacks.add(callback);
    }

    /**
     * 通知回调函数
     * @param {Object} data 
     */
    notifyProgressCallbacks(data) {
        this.progressCallbacks.forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error('进度回调错误:', error);
            }
        });
    }

    /**
     * 轮询回退方案
     * @param {number} videoId 
     */
    startPolling(videoId) {
        console.log('使用轮询模式获取进度');
        
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/v1/videos/${videoId}/progress`, {
                    headers: {
                        'Authorization': `Bearer ${this.token}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.handleProgressUpdate({
                        type: 'progress_update',
                        ...data
                    });
                }
                
                // 如果下载完成，停止轮询
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(pollInterval);
                }
                
            } catch (error) {
                console.error('轮询进度失败:', error);
            }
        }, 2000);
    }

    /**
     * 重连机制
     */
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`WebSocket重连尝试 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.connect().catch(() => {
                    // 重连失败，启动轮询
                    this.startPolling(this.videoId);
                });
            }, this.reconnectInterval);
        } else {
            console.log('WebSocket重连失败，切换到轮询模式');
            this.startPolling(this.videoId);
        }
    }

    /**
     * 断开连接
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.isConnected = false;
    }

    /**
     * 事件系统
     */
    emit(event, data) {
        window.dispatchEvent(new CustomEvent(`download:${event}`, { detail: data }));
    }

    on(event, callback) {
        window.addEventListener(`download:${event}`, callback);
    }
}

// 使用示例
// ===============================

// 初始化进度管理器
const progressManager = new DownloadProgressManager();

// 页面加载时初始化
window.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('authToken'); // 或从cookie获取
    const videoId = window.videoId || getVideoIdFromUrl(); // 从页面获取
    
    if (token && videoId) {
        await progressManager.initialize(token, videoId);
    }
});

// HTML结构示例
/*
<div id="progress-123" class="download-progress-container">
    <div class="progress-bar-container">
        <div class="progress-bar" style="width: 0%" role="progressbar"></div>
    </div>
    <div class="progress-info">
        <span class="progress-text">0.0%</span>
        <span class="stage-indicator">准备中</span>
    </div>
    <div class="status-message">正在开始下载...</div>
    <div class="complete-message" style="display: none;">下载完成！</div>
    <div class="error-message" style="display: none; color: red;"></div>
</div>
*/

// 集成到现有前端框架
export default DownloadProgressManager;