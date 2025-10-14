import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_URL || 'http://localhost:8000'
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src')
      }
    },
    server: {
      // 开发环境通过 Vite 代理到后端，目标由 VITE_API_URL 指定
      host: true,
      allowedHosts: ['assx.top'],
      proxy: {
        '/api': {
          target,
          changeOrigin: true
          // 不进行 rewrite，后端本身以 /api 为前缀
        }
      }
    }
  }
})
