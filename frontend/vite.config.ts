import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The build emits directly into the backend package. FastAPI mounts that
// directory, so the container serves API and UI from one origin - no CORS, one
// Traefik route.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    // In dev the API runs separately on :8000. Proxying keeps frontend code
    // identical between dev and production - it always calls same-origin paths.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
