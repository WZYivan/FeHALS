import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发环境将 /api 与 /ws 代理到 FastAPI 后端（后端端口跟随 BACKEND_PORT，默认 8000）
const backendPort = process.env.BACKEND_PORT || 8000

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: `http://localhost:${backendPort}`, changeOrigin: true },
      '/ws': { target: `ws://localhost:${backendPort}`, ws: true },
      '/static': { target: `http://localhost:${backendPort}`, changeOrigin: true },
    },
  },
})
