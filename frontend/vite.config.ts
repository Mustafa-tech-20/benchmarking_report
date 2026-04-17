import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? '/benchmarking/frontend/' : '/',
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    allowedHosts: ['td-dev-benchmark.m-devsecops.com', 'localhost'],
  },
  preview: {
    port: 3000,
    host: true,
    allowedHosts: ['td-dev-benchmark.m-devsecops.com', 'localhost'],
  }
}))
