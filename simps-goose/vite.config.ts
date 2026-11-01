import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  build: { target: 'es2020', chunkSizeWarningLimit: 2000, assetsInlineLimit: 0 },
  server: { port: 5173 },
});
