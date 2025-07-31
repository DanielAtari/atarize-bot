export default defineConfig({
  root: '.', // הפוך את שורש הפרויקט לשורש הפרונטאנד
  build: {
    outDir: 'static/dist', // תכתוב את ה-build לתוך static/dist
    emptyOutDir: true,
  },
  plugins: [react()],
});
