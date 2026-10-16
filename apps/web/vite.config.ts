import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Destino do proxy da API. Dentro do Docker Compose, `api` é o nome do serviço da API.
// Fora do Docker, use API_PROXY_TARGET=http://localhost:8000.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://api:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Falha em vez de trocar de porta sozinho (a porta é publicada pelo Compose).
    strictPort: true,
    proxy: {
      // Imita o rewrite do Firebase Hosting em produção:
      // /api/healthz  ->  <apiTarget>/healthz  (o prefixo /api é removido)
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
