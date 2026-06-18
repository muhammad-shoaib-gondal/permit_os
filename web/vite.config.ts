import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/cases": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 600_000,
        proxyTimeout: 600_000,
      },
      "/health": "http://127.0.0.1:8000",
      "/disclaimer": "http://127.0.0.1:8000",
      "/audit": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 120_000,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
