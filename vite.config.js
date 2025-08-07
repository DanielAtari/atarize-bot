import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'static', // הפוך את שורש הפרויקט לשורש הפרונטאנד
  build: {
    outDir: 'dist', // תכתוב את ה-build לתוך static/dist
    emptyOutDir: true,
  },
  plugins: [react()],
  server: {
    port: 3000,
    host: true
  }
});
