/**
 * 以 content collection 为唯一数据源，构建/开发前同步到 public/ 供客户端 fetch。
 * 用法：node scripts/copy-articles.mjs
 */
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "src", "content", "daily", "articles.json");
const destDir = join(root, "public");
const dest = join(destDir, "articles.json");

if (!existsSync(src)) {
  console.error(`[copy-articles] 缺少数据源: ${src}`);
  process.exit(1);
}

mkdirSync(destDir, { recursive: true });
copyFileSync(src, dest);
console.log(`[copy-articles] ${src} → ${dest}`);
