import { defineConfig } from "vite";

// Game art lives in ../assets (single copy, logged in docs/ASSETS.md).
export default defineConfig({
  base: "./",
  publicDir: "../assets",
  server: { port: 5173 },
});
