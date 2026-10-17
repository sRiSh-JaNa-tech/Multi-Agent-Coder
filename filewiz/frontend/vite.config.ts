import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const authTarget = env.VITE_AUTH_TARGET || 'http://localhost:4000';
  const backendTarget = env.VITE_BACKEND_TARGET || env.VITE_PROXY_TARGET || 'http://localhost:3000';

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      proxy: {
        '/auth': {
          target: authTarget,
          changeOrigin: true
        },
        '/compress': {
          target: backendTarget,
          changeOrigin: true
        },
        '/peek': {
          target: backendTarget,
          changeOrigin: true
        },
        '/split': {
          target: backendTarget,
          changeOrigin: true
        },
        '/redaction': {
          target: backendTarget,
          changeOrigin: true
        },
        '/encrypt': {
          target: backendTarget,
          changeOrigin: true
        },
        '/repair': {
          target: backendTarget,
          changeOrigin: true
        },
        '/convert': {
          target: backendTarget,
          changeOrigin: true
        },
        '/temp': {
          target: backendTarget,
          changeOrigin: true
        }
      }
    }
  };
})
