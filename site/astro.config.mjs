import { defineConfig } from "astro/config";

// 静态站点构建，部署到 GitHub Pages / EdgeOne Pages 均可
// base 通过环境变量 ASTRO_BASE 控制：
//   根路径（EdgeOne / 自定义域名）: 不设，默认 /
//   GitHub Pages 项目站点（子路径）: workflow 里设 ASTRO_BASE=/BlackManuscript/
export default defineConfig({
  site: "https://wenwenwen888.github.io",
  base: process.env.ASTRO_BASE || "/",
  output: "static",
  trailingSlash: "ignore",
  build: {
    inlineStylesheets: "auto",
  },
  vite: {
    server: {
      proxy: {
        // 本地：先开 node tools/ai_mirror_search_server.js
        "/api/mirror-search": {
          target: "http://127.0.0.1:8788",
          changeOrigin: true,
        },
        "/api/mirror-parse": {
          target: "http://127.0.0.1:8788",
          changeOrigin: true,
        },
      },
    },
  },
});
