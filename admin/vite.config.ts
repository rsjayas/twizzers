import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The built app is served by the backend under /admin/ (hash routing, so no
// server-side fallback is needed). In development, API calls go to the backend.
export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  server: { proxy: { '/admin/api': process.env.ADMIN_API_URL ?? 'http://localhost:8000' } },
});
