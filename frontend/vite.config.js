import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'  

export default defineConfig({
  plugins: [react()],
  
  
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  css: {
    postcss: './postcss.config.js',
  },
  
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // rewrite not needed if backend uses /api prefix
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  define: {
    'process.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || 'http://localhost:8000/api'),
  },
})