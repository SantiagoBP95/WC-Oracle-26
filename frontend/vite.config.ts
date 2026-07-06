import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, las llamadas a /api se reenvían al backend (Servidor A) local.
// En producción, Caddy (Servidor B) hace el mismo reverse-proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
