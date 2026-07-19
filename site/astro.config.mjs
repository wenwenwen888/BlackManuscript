import { defineConfig } from "astro/config";

// 静态站点构建，部署到 GitHub Pages / EdgeOne Pages 均可
// base 通过环境变量 ASTRO_BASE 控制：
//   GitHub Pages（子路径）: 不设，默认 /BlackManuscript/
//   EdgeOne / 自定义域名（根路径）: 设 ASTRO_BASE=/
export default defineConfig({
  site: "https://wenwenwen888.github.io",
  base: process.env.ASTRO_BASE || "/BlackManuscript/",
  output: "static",
  trailingSlash: "ignore",
  build: {
    // 每日数据文件作为静态资源输出，便于直接访问 JSON 归档
    inlineStylesheets: "auto",
  },
});
