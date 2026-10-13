import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En Docker el backend se llama "backend"; fuera de Docker usa localhost.
const target = process.env.API_URL ?? "http://backend:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true }, // necesario para recarga en caliente en Docker/Windows
    proxy: { "/api": { target, changeOrigin: true } },
  },
});
