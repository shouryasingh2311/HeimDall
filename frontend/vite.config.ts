import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: ['.', ...['theme.css', 'theme.js'].map(file =>
        fileURLToPath(new URL(`../backend/collector/static/${file}`, import.meta.url)),
      )],
    },
  },
})
