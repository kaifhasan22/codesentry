import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolveApiBaseUrl } from './src/api/baseUrl.js'

export default defineConfig(({ command, mode }) => {
  // Validate the same public variables used by the browser before building.
  resolveApiBaseUrl({ ...loadEnv(mode, process.cwd(), 'VITE_'), ...process.env, PROD: command === 'build' })
  return {
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  }
})
