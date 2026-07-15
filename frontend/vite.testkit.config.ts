import path from "path";
import { defineConfig } from "vite";

// testkit 独立构建:单文件 IIFE,由 harness 读入后经 WebviewWindow.eval 注入
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // lib 模式不替换 process.env.NODE_ENV(为库消费者保留);testkit 引入 React 后
  // 直接跑在 WebView,必须静态替换,否则 IIFE 顶层 ReferenceError
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
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
