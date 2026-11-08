import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/gpu/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ready': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
      '/assets': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    // Additive second page: the FieldLoop GPU bench runner (served at /gpu/bench.html).
    rollupOptions: { input: { main: 'index.html', bench: 'bench.html' } },
    emptyOutDir: true,
    sourcemap: true,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'benchmarks/**/*.test.ts'],
  },
})
