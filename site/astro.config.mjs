import { defineConfig } from "astro/config";

// 静态站点构建，部署到 Cloudflare Pages / Vercel / GitHub Pages 均可
export default defineConfig({
  site: "https://example.com",
  output: "static",
  trailingSlash: "ignore",
  build: {
    // 每日数据文件作为静态资源输出，便于直接访问 JSON 归档
    inlineStylesheets: "auto",
  },
});
