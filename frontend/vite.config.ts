import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Parse VITE_ALLOWED_HOSTS from environment variable (comma-separated)
const allowedHosts = process.env.VITE_ALLOWED_HOSTS
  ? process.env.VITE_ALLOWED_HOSTS.split(',').map(h => h.trim())
  : ['localhost']

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: allowedHosts,
    watch: {
      usePolling: true, // For Docker
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
