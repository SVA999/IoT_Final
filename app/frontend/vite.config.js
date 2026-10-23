import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // En desarrollo local, /api va a la API (docker compose la expone solo en red interna:
    // para probar en local, publicar el 8000 o ajustar este target)
    proxy: { '/api': { target: 'http://localhost:8000', ws: true } },
  },
})
