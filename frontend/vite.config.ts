import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Development: /api is proxied to the backend project (cd ../backend && uvicorn advisor.api:app --port 8080).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": env.API_PROXY_TARGET || "http://localhost:8080" },
    },
  };
});
