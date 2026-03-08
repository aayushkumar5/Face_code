import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // REST API calls: /api/* → http://127.0.0.1:8000/api/*
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      // WebSocket: /ws/* → ws://127.0.0.1:8000/ws/*
      // rewriteWsOrigin: true is required on Windows to pass the origin header
      "/ws": {
        target: "http://127.0.0.1:8000",
        ws: true,
        rewriteWsOrigin: true,
      },
    },
  },
});
