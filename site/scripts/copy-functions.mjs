/**
 * 构建后把 Pages Functions 拷进 dist，避免 EdgeOne 只发布输出目录时丢函数。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const siteRoot = path.resolve(__dirname, "..");
const dist = path.join(siteRoot, "dist");
const srcCandidates = [
  path.join(siteRoot, "functions"),
  path.resolve(siteRoot, "..", "functions"),
];

const src = srcCandidates.find((p) => fs.existsSync(p));
if (!src) {
  console.warn("[copy-functions] no functions/ found, skip");
  process.exit(0);
}
if (!fs.existsSync(dist)) {
  console.warn("[copy-functions] dist/ missing, skip");
  process.exit(0);
}

function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const ent of fs.readdirSync(from, { withFileTypes: true })) {
    const a = path.join(from, ent.name);
    const b = path.join(to, ent.name);
    if (ent.isDirectory()) copyDir(a, b);
    else fs.copyFileSync(a, b);
  }
}

copyDir(src, path.join(dist, "functions"));
console.log("[copy-functions] copied", src, "->", path.join(dist, "functions"));
