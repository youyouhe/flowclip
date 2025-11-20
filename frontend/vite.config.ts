import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        ws: true, // Enable WebSocket proxy for API connections
        timeout: 180000, // 3分钟代理超时
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Sending Request to the Target:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          });
        },
      },
      '/minio': {
        target: 'http://minio:9000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio/, ''),
      },
      '/minio-console': {
        target: 'http://minio:9001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio-console/, ''),
      },
    },
  },
  build: {
    // 添加时间戳到文件名，强制浏览器重新加载
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        chunkFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        assetFileNames: `assets/[name]-[hash]-${Date.now()}.[ext]`
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://backend:8001',
        changeOrigin: true,
        ws: true, // Enable WebSocket proxy for API connections
        timeout: 180000, // 3分钟代理超时
      },
      '/minio': {
        target: 'http://minio:9000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio/, ''),
      },
      '/minio-console': {
        target: 'http://minio:9001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio-console/, ''),
      },
    },
  },
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'react-calendar-timeline', 'moment'],
  },
})