/**
 * 本地实时镜像搜索代理（密钥只在服务端）
 * 用法：node tools/ai_mirror_search_server.js
 * 读取仓库根目录 .env.local
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!m) continue;
    let v = m[2];
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    if (!process.env[m[1]]) process.env[m[1]] = v;
  }
}

loadEnvFile(path.join(ROOT, ".env.local"));
loadEnvFile(path.join(ROOT, ".env"));

const PORT = Number(process.env.AI_PROXY_PORT || 8788);

// 复用边缘函数同款逻辑：动态加载为模块较麻烦，这里直接读文件执行导出不现实。
// 改为内联调用同一实现文件（Edge 用 export，Node 用 createRequire 不行）。
// 最稳：把核心写成 tools/lib，两边 import。为加快落地，本文件直接 import 边缘函数代码路径不可行（无 node 兼容层）。
// 因此把边缘函数里的 handle 逻辑在本地再挂一遍：通过 child 方式太重。
// 采用：把 functions/api/mirror-search.js 复制逻辑 —— 用动态 import（ESM）直接加载。

const modPath = path.join(ROOT, "functions", "api", "mirror-search.js");

async function loadHandler() {
  const mod = await import("file://" + modPath.replace(/\\/g, "/"));
  return mod;
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

const env = {
  AI_API_KEY: process.env.AI_API_KEY || "",
  AI_BASE_URL: process.env.AI_BASE_URL || "https://coding.92onegame.com/v1",
  AI_MODEL: process.env.AI_MODEL || "auto",
};

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    sendJson(res, 204, {});
    return;
  }
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  if (req.method === "POST" && (url.pathname === "/api/mirror-search" || url.pathname === "/")) {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    try {
      const mod = await loadHandler();
      const request = new Request("http://local/api/mirror-search", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: raw || "{}",
      });
      const response = await mod.onRequestPost({ request, env });
      const text = await response.text();
      res.writeHead(response.status, {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store",
      });
      res.end(text);
    } catch (e) {
      sendJson(res, 502, { error: String(e.message || e) });
    }
    return;
  }
  sendJson(res, 404, { error: "not found" });
});

if (!env.AI_API_KEY) {
  console.warn("[warn] AI_API_KEY missing — will use heuristic query planning only");
}
server.listen(PORT, "127.0.0.1", () => {
  console.log(`[ai-mirror-search] http://127.0.0.1:${PORT}/api/mirror-search`);
});
