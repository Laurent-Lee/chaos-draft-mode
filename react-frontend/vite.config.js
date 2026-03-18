import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://54.145.3.50:5050',
      '/elixir.svg': 'http://54.145.3.50:5050',
    },
  },
})
