import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En Docker el backend se llama "backend"; fuera de Docker usa localhost.
const target = process.env.API_URL ?? "http://backend:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Las librerías pesadas van en archivos propios: el navegador las guarda en caché y no se re-descargan en cada despliegue.
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return "react";
          if (id.includes("framer-motion") || id.includes("motion-dom") || id.includes("motion-utils")) return "motion";
          if (/node_modules[\\/](recharts|d3-|victory-vendor|recharts-scale|decimal\.js-light)/.test(id)) return "charts";
          return undefined;
        },
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true }, // necesario para recarga en caliente en Docker/Windows
    proxy: { "/api": { target, changeOrigin: true } },
  },
});
