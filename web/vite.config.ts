import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // 5174/8010 so DocMitra can run alongside thinkgas-platform (5173/8000).
    port: 5174,
    proxy: { "/api": "http://localhost:8010" },
  },
});
