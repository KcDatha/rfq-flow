import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/rfqs": "http://localhost:8000",
      "/review-queue": "http://localhost:8000",
      "/review": "http://localhost:8000",
      "/catalog": "http://localhost:8000",
    },
  },
});
