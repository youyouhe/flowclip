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
        target: 'http://backend:8001',
        changeOrigin: true,
        ws: true, // Enable WebSocket proxy for API connections
        rewrite: (path) => path.replace(/^\/api/, ''),
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
    include: ['react', 'react-dom', 'react-router-dom'],
  },
})