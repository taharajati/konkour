import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API_PORT: where the backend listens (default 8000)
const api = `http://localhost:${process.env.API_PORT || 8000}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',     // IPv4: "localhost" can resolve to ::1 only on Windows
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': { target: api, rewrite: p => p.replace(/^\/api/, '') },
      '/static': api,
    },
  },
})
