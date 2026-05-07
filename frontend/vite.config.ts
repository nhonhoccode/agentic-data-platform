import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "../app/ui/static/dist",
    emptyOutDir: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // Only split heavy dependencies that are lazy-loaded.
        // Keep React + Radix + lucide in the main bundle to avoid circular chunks.
        manualChunks: (id: string) => {
          if (id.includes("node_modules")) {
            if (id.includes("plotly")) return "plotly";
            if (
              id.includes("react-markdown") ||
              id.includes("remark-") ||
              id.includes("react-syntax-highlighter") ||
              id.includes("refractor") ||
              id.includes("highlight.js")
            ) {
              return "markdown";
            }
          }
          return undefined;
        },
      },
    },
  },
  base: "/ui/static/dist/",
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ui/proxy": "http://localhost:8000",
    },
  },
});
