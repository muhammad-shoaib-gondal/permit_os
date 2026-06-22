import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function redirectAppTrailingSlash(): Plugin {
  return {
    name: "redirect-app-trailing-slash",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const pathname = req.url?.split("?")[0] ?? "";
        if (pathname === "/app") {
          const query = req.url?.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
          res.writeHead(301, { Location: `/app/${query}` });
          res.end();
          return;
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), redirectAppTrailingSlash()],
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
    rollupOptions: {
      input: {
        landing: path.resolve(__dirname, "index.html"),
        app: path.resolve(__dirname, "app/index.html"),
      },
    },
  },
});
