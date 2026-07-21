/**
 * EdgeOne Pages Function
 * 路径：/functions/api/mirror-parse.js → https://域名/api/mirror-parse
 * （EdgeOne Pages 认 functions/，不是 edge-functions/）
 *
 * 控制台配置环境变量（勿写进仓库），改完后需重新部署：
 *   AI_API_KEY   = 你的 key
 *   AI_BASE_URL  = https://coding.92onegame.com/v1
 *   AI_MODEL     = auto
 */

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
- 国内主体 → leaning=domestic, target_side=right
- 海外主体 → leaning=overseas, target_side=left`;

function jsonResp(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "POST, OPTIONS",
      "access-control-allow-headers": "content-type",
    },
  });
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

async function handlePost(request, env) {
  const API_KEY = (env && env.AI_API_KEY) || "";
  const BASE = String((env && env.AI_BASE_URL) || "https://coding.92onegame.com/v1").replace(/\/$/, "");
  const MODEL = (env && env.AI_MODEL) || "auto";
  if (!API_KEY) {
    return jsonResp(500, { error: "AI_API_KEY not configured on edge" });
  }

  let q = "";
  try {
    const body = await request.json();
    q = String(body.q || body.query || "").trim();
  } catch {
    return jsonResp(400, { error: "invalid json" });
  }
  if (!q) return jsonResp(400, { error: "empty query" });

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
        { role: "user", content: q.slice(0, 200) },
      ],
    }),
  });

  if (!resp.ok) {
    const t = await resp.text();
    return jsonResp(502, { error: `LLM HTTP ${resp.status}`, detail: t.slice(0, 200) });
  }

  const data = await resp.json();
  const content = data?.choices?.[0]?.message?.content || "";
  try {
    return jsonResp(200, normalizePlan(JSON.parse(extractJson(content))));
  } catch {
    return jsonResp(502, { error: "bad model json", detail: String(content).slice(0, 300) });
  }
}

export function onRequestOptions() {
  return jsonResp(204, {});
}

export async function onRequestPost(context) {
  return handlePost(context.request, context.env || {});
}

export async function onRequest(context) {
  const method = context.request.method;
  if (method === "OPTIONS") return onRequestOptions();
  if (method === "POST") return onRequestPost(context);
  return jsonResp(405, { error: "POST only" });
}
