import path from "path";
import { defineConfig } from "vite";

// testkit 独立构建:单文件 IIFE,由 harness 读入后经 WebviewWindow.eval 注入
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, "src/testkit/index.ts"),
      formats: ["iife"],
      name: "PyshadeTestkitModule",
      fileName: () => "testkit.js",
    },
    outDir: "dist-testkit",
    emptyOutDir: true,
    minify: false,
  },
});
