import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/react/" : "/",
  plugins: [react()],
  build: {
    manifest: true,
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: "./src/test/setup.ts",
  },
}));
