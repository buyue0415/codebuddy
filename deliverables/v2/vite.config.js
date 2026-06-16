import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: parseInt(env.VITE_PORT || '5173', 10),
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET || 'http://127.0.0.1:8766',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
    },
  }
})
