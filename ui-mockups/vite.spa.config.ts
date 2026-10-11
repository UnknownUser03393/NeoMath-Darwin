import path from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/postcss";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));
const spaRoot = path.resolve(rootDir, "spa");
const outDir = path.resolve(
  rootDir,
  "../desktop/src/neomath/ui/notebook",
);

/**
 * Client-only AOT build for the desktop shell.
 * Runtime needs no Node — Python serves the static files + MathCore API.
 */
export default defineConfig({
  root: spaRoot,
  base: "./",
  publicDir: path.resolve(rootDir, "public"),
  plugins: [react()],
  resolve: {
    alias: {
      "@": rootDir,
    },
  },
  css: {
    postcss: {
      plugins: [tailwindcss()],
    },
  },
  build: {
    outDir,
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    target: "es2022",
    rollupOptions: {
      input: path.resolve(spaRoot, "index.html"),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },
    },
  },
});
