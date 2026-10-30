/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy /api and /media to Django so cookies are same-origin (no CORS/SameSite headaches)
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', globals: false, include: ['src/**/*.test.{ts,tsx}'], setupFiles: ['src/test-setup.ts'] },
  server: { proxy: { '/api': 'http://localhost:8000', '/media': 'http://localhost:8000' } },
})
