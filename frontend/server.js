/**
 * 静态文件服务器 - 生产环境前端服务
 * 替代 Vite preview，提供更好的性能和控制
 */

const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = 3000;

// API 代理中间件
const apiProxy = createProxyMiddleware({
  target: 'http://localhost:8001',
  changeOrigin: true,
  ws: true, // 支持 WebSocket
  secure: false,
  timeout: 30000,
  // 移除 pathRewrite，因为前端已经生成正确的 /api/v1 路径
  onProxyReq: (proxyReq, req, res) => {
    console.log(`Proxying: ${req.method} ${req.url} -> http://localhost:8001${proxyReq.path}`);
  },
  onError: (err, req, res) => {
    console.error('Proxy error:', err);
    if (!res.headersSent) {
      // 检查是否为HTTP响应对象（WebSocket代理错误时res可能不是标准HTTP响应）
      if (typeof res.status === 'function') {
        res.status(502).json({
          error: 'Backend service unavailable',
          message: 'The backend service is not responding'
        });
      } else {
        // WebSocket连接错误，发送错误信息
        if (res.socket && res.socket.readyState === 1) { // WebSocket.OPEN
          res.socket.send(JSON.stringify({
            error: 'Backend service unavailable',
            message: 'The backend service is not responding'
          }));
        }
      }
    }
  }
});

// 日志中间件
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.url}`);
  next();
});

// API 代理路由
app.use('/api', apiProxy);

// 静态文件服务
const staticDir = path.join(__dirname, 'dist');

// 检查 dist 目录是否存在
if (!fs.existsSync(staticDir)) {
  console.error('Error: dist directory not found. Please run "npm run build" first.');
  process.exit(1);
}

// 缓存控制
app.use(express.static(staticDir, {
  maxAge: '1y', // 静态文件缓存 1 年
  etag: true,
  lastModified: true,
  setHeaders: (res, filePath) => {
    // HTML 文件不缓存，确保更新
    if (path.extname(filePath) === '.html') {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
      res.setHeader('Expires', '0');
    }
    // JS/CSS 文件设置长期缓存
    else if (['.js', '.css'].includes(path.extname(filePath))) {
      res.setHeader('Cache-Control', 'public, max-age=31536000');
    }
  }
}));

// SPA 路由处理 - 所有非 API 路由都返回 index.html
app.get('*', (req, res, next) => {
  // 如果是 API 请求，跳过
  if (req.path.startsWith('/api')) {
    return next();
  }

  // 如果是静态文件请求且有扩展名，跳过
  if (path.extname(req.path)) {
    return next();
  }

  // 返回 index.html
  const indexPath = path.join(staticDir, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).json({ error: 'Frontend not built' });
  }
});

// 错误处理中间件
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// 启动服务器
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Frontend server running on http://0.0.0.0:${PORT}`);
  console.log(`📁 Serving static files from: ${staticDir}`);
  console.log(`🔄 Proxying API requests to: http://localhost:8001`);
  console.log(`🔌 WebSocket proxy enabled for /api/* routes`);
});

// 优雅关闭
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  process.exit(0);
});