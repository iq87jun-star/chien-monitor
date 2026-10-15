/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // サブパス配信でも動くよう相対パスにする
  base: "./",
  test: {
    globals: true,
    include: ["tests/**/*.test.ts"],
  },
});
