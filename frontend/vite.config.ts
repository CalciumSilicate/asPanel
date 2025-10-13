import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    // 不使用 Vite 代理；请通过 .env 的 VITE_API_URL 直连后端
    allowedHosts: ['*']
  }
})
