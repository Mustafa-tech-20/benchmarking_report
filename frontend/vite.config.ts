import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,  // Expose to network (needed for Docker)
  },
  preview: {
    port: 3000,
    host: true  // Expose to network (needed for Docker)
  }
})
