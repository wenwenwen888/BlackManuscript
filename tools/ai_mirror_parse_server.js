/**
 * 本地 / Edge 共用的镜像查询解析服务。
 * - 本地：node tools/ai_mirror_parse_server.js （读取 .env.local）
 * - 线上：EdgeOne 边缘函数转发到同源 /api/mirror-parse
 *
 * 密钥只放服务端，不进 site/public。
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
    const k = m[1];
    let v = m[2];
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    if (!process.env[k]) process.env[k] = v;
  }
}

loadEnvFile(path.join(ROOT, ".env.local"));
loadEnvFile(path.join(ROOT, ".env"));

const PORT = Number(process.env.AI_PROXY_PORT || 8788);
const BASE = (process.env.AI_BASE_URL || "https://coding.92onegame.com/v1").replace(/\/$/, "");
const MODEL = process.env.AI_MODEL || "auto";
const API_KEY = process.env.AI_API_KEY || "";

const SYSTEM = `你是「嘲讽日报」镜像搜索解析器。站点左栏=外媒嘲讽中国，右栏=中媒嘲讽海外。
用户输入一句话，你要判断主体偏国内还是海外，并给出应对侧检索方案。
只输出 JSON，不要 markdown。字段：
{
  "leaning": "domestic" | "overseas" | "unknown",
  "target_side": "left" | "right",
  "topic_hint": "股票|政治|经济|社会|科技|军事|外交|文化|环境|电影|娱乐|其他|",
  "query_entities": ["用户侧实体"],
  "counterpart_entities": ["对侧对照实体，如华为→特斯拉"],
  "keywords": ["用于匹配标题摘要的中文关键词，5~12个"],
  "explanation": "一句话说明为何这样镜像"
}
规则：
- 国内主体（华为/比亚迪/A股/城投/解放军…）→ leaning=domestic, target_side=right（去找海外对照）
- 海外主体（特斯拉/美军/美联储/好莱坞…）→ leaning=overseas, target_side=left（去找国内对照）
- keywords 要覆盖议题（如智驾、车祸、自动驾驶）与对侧实体名`;

export async function parseMirrorQuery(q) {
  if (!API_KEY) {
    const err = new Error("AI_API_KEY missing");
    err.code = "NO_KEY";
    throw err;
  }
  const resp = await fetch(`${BASE}/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      temperature: 0.2,
      messages: [
        { role: "system", content: SYSTEM },
        { role: "user", content: String(q || "").slice(0, 200) },
      ],
    }),
  });
  if (!resp.ok) {
    const t = await resp.text();
    const err = new Error(`LLM HTTP ${resp.status}: ${t.slice(0, 200)}`);
    err.code = "LLM_HTTP";
    throw err;
  }
  const data = await resp.json();
  const content = data?.choices?.[0]?.message?.content || "";
  const jsonText = extractJson(content);
  const plan = JSON.parse(jsonText);
  return normalizePlan(plan);
}

function extractJson(text) {
  const s = String(text || "").trim();
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) return fence[1].trim();
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start >= 0 && end > start) return s.slice(start, end + 1);
  return s;
}

function normalizePlan(plan) {
  const leaning = ["domestic", "overseas", "unknown"].includes(plan?.leaning)
    ? plan.leaning
    : "unknown";
  let target_side = plan?.target_side;
  if (target_side !== "left" && target_side !== "right") {
    target_side = leaning === "domestic" ? "right" : leaning === "overseas" ? "left" : null;
  }
  const arr = (v) => (Array.isArray(v) ? v.map((x) => String(x || "").trim()).filter(Boolean) : []);
  return {
    leaning,
    target_side,
    topic_hint: String(plan?.topic_hint || "").trim(),
    query_entities: arr(plan?.query_entities),
    counterpart_entities: arr(plan?.counterpart_entities),
    keywords: arr(plan?.keywords),
    explanation: String(plan?.explanation || "").trim(),
    source: "ai",
  };
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    sendJson(res, 204, {});
    return;
  }
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  if (req.method === "POST" && (url.pathname === "/api/mirror-parse" || url.pathname === "/")) {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    let q = "";
    try {
      const body = JSON.parse(raw || "{}");
      q = String(body.q || body.query || "").trim();
    } catch {
      sendJson(res, 400, { error: "invalid json" });
      return;
    }
    if (!q) {
      sendJson(res, 400, { error: "empty query" });
      return;
    }
    try {
      const plan = await parseMirrorQuery(q);
      sendJson(res, 200, plan);
    } catch (e) {
      sendJson(res, 502, { error: String(e.message || e), code: e.code || "FAIL" });
    }
    return;
  }
  sendJson(res, 404, { error: "not found" });
});

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (!API_KEY) {
    console.error("Missing AI_API_KEY. Create .env.local at repo root.");
    process.exit(1);
  }
  server.listen(PORT, "127.0.0.1", () => {
    console.log(`[ai-mirror-parse] http://127.0.0.1:${PORT}/api/mirror-parse`);
  });
}
