import { fileURLToPath, URL } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// O backend publica apenas em 127.0.0.1:8000; dentro do compose o host é `backend`.
const API_TARGET = process.env.VITE_PROXY_TARGET ?? 'http://backend:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    // O hot reload precisa de polling quando o código vem de um bind mount.
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
      '/ws': { target: API_TARGET, ws: true },
    },
  },
  preview: { host: '0.0.0.0', port: 3000, strictPort: true },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // O renderizador WebGL do Pixi é indivisível e passa de 500 kB sozinho.
    chunkSizeWarningLimit: 600,
    rolldownOptions: {
      output: {
        // Separar Pixi e React mantém o chunk da aplicação em dezenas de kB.
        codeSplitting: {
          groups: [
            { name: 'pixi', test: /node_modules[/\\]pixi\.js/ },
            { name: 'react', test: /node_modules[/\\](react|react-dom|scheduler)[/\\]/ },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/types/**',
        // Precisam de um contexto WebGL real: jsdom não instancia o Pixi. A lógica
        // destacável do canvas vive em `engine/layoutMath.ts`, que é coberta.
        'src/engine/AgentSprite.ts',
        'src/engine/ChatBubble.ts',
        'src/engine/OfficeRenderer.ts',
        'src/engine/textures.ts',
        'src/engine/palette.ts',
        'src/components/OfficeCanvas.tsx',
      ],
    },
  },
});
