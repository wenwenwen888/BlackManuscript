/**
 * EdgeOne Pages Function：实时镜像搜索
 * 路径：/functions/api/mirror-search.js → POST /api/mirror-search
 *
 * 流程：用户词 → LLM 生成对侧检索词 → Bing/Google 新闻 RSS 实时抓取 → 返回结果卡片
 *
 * 环境变量（控制台配置，改完需重新部署）：
 *   AI_API_KEY / AI_BASE_URL / AI_MODEL
 */

const SYSTEM = `你是「嘲讽日报」实时镜像搜索规划器。
左栏=外媒嘲讽中国；右栏=中媒嘲讽海外。
用户输入后，你要规划「对侧」新闻检索词（不是站内库检索）。
只输出 JSON：
{
  "leaning": "domestic" | "overseas" | "unknown",
  "target_side": "left" | "right",
  "topic_hint": "股票|政治|经济|社会|科技|军事|外交|文化|环境|电影|娱乐|其他",
  "explanation": "一句话说明镜像逻辑",
  "queries": [
    { "q": "检索词", "lang": "zh" | "en", "market": "zh-CN" | "en-US" }
  ]
}
规则：
- 国内主体（哪吒/华为/A股…）→ leaning=domestic, target_side=right
  queries 用中文搜「海外对照话题」或英文搜外媒相关报道（如 Nezha / Chinese animation / Hollywood）
- 海外主体（特斯拉/美军/好莱坞…）→ leaning=overseas, target_side=left
  queries 用中文搜中媒对该海外话题的批评/嘲讽报道
- queries 给 2~4 条，短而可搜，覆盖实体+议题`;

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

function decodeEntities(s) {
  return String(s || "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => {
      try {
        return String.fromCodePoint(parseInt(h, 16));
      } catch {
        return " ";
      }
    })
    .replace(/&#(\d+);/g, (_, n) => {
      try {
        return String.fromCodePoint(Number(n));
      } catch {
        return " ";
      }
    });
}

function stripHtml(s) {
  let t = String(s || "");
  t = t.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1");
  // Bing 等源常把 HTML 实体编码后再塞进 description，需先解码再剥标签，多轮处理
  for (let i = 0; i < 4; i++) {
    t = decodeEntities(t);
    t = t.replace(/<script[\s\S]*?<\/script>/gi, " ");
    t = t.replace(/<style[\s\S]*?<\/style>/gi, " ");
    t = t.replace(/<[^>]+>/g, " ");
  }
  return t.replace(/\s+/g, " ").trim();
}

function truncate(s, n) {
  const t = String(s || "").trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 1).trim() + "…";
}

function makeSpicyQuote(title, side, i) {
  // 自然短评，不再硬套「——现场如此」收束
  const domestic = [
    "票房数字会说话，叙事更会化妆。",
    "热闹是真的，追问常常迟到。",
    "标题先高潮，细节后补课。",
    "胜利声明很满，账本未必同步。",
    "流量到了，问题还在排队。",
    "掌声整齐时，最该听沉默。",
    "神话好写，复盘难写。",
    "热搜有保质期，争议没有。",
  ];
  const overseas = [
    "外媒镜头很利，语境常常裁切。",
    "立场先入座，事实后入座。",
    "批评很响亮，对照很选择性。",
    "故事好卖，完整度另算。",
    "标题有锋芒，背景常缺席。",
    "叙事很忙，复杂性很闲。",
    "结论先到，材料后补。",
    "热闹的是议题，安静的是证据。",
  ];
  const pool = side === "left" ? overseas : domestic;
  return pool[i % pool.length];
}

async function spiceQuotesWithAi(items, env) {
  const API_KEY = (env && env.AI_API_KEY) || "";
  if (!API_KEY || items.length === 0) return items;
  const BASE = String((env && env.AI_BASE_URL) || "https://coding.92onegame.com/v1").replace(/\/$/, "");
  const MODEL = (env && env.AI_MODEL) || "auto";
  const sample = items.slice(0, 12);
  const payload = sample.map((it, i) => `${i + 1}. ${it.title_cn}`).join("\n");
  try {
    const resp = await fetch(`${BASE}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.7,
        messages: [
          {
            role: "system",
            content:
              "你是嘲讽日报的辣评写手。根据每条新闻标题，写一句自然、口语化的中文讽刺短评。要求：12~28字；像人随口吐槽；不要用「——现场如此」「——账本如此」这类固定收束；不要加括号标签如「中媒镜像」；不要引号；只输出 JSON 字符串数组，顺序与输入一致。",
          },
          { role: "user", content: payload },
        ],
      }),
    });
    if (!resp.ok) return items;
    const data = await resp.json();
    const content = data?.choices?.[0]?.message?.content || "";
    const arr = JSON.parse(extractJson(content));
    if (!Array.isArray(arr)) return items;
    return items.map((it, i) => {
      let q = i < arr.length && arr[i] ? String(arr[i]).trim() : "";
      q = q.replace(/^["「『]|["」』]$/g, "").trim();
      // 清掉旧模板尾巴
      q = q.replace(/（[^）]*镜像[^）]*）/g, "").replace(/——[^。]*如此。?/g, "").trim();
      if (!q || q.length < 6) return it;
      return { ...it, quote_cn: q.slice(0, 40) };
    });
  } catch {
    return items;
  }
}

function tagText(block, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, "i");
  const m = block.match(re);
  return m ? stripHtml(m[1]) : "";
}

function parseRss(xml) {
  const items = [];
  const chunks = String(xml || "").split(/<item[\s>]/i).slice(1);
  for (const chunk of chunks) {
    const title = tagText(chunk, "title");
    let link = tagText(chunk, "link");
    if (!link) {
      const gu = chunk.match(/<guid[^>]*>([\s\S]*?)<\/guid>/i);
      if (gu) link = stripHtml(gu[1]);
    }
    // 先取原始 description，再清洗；尽量抽出媒体名
    const rawDesc = (() => {
      const m = chunk.match(/<description[^>]*>([\s\S]*?)<\/description>/i);
      return m ? m[1] : "";
    })();
    let summary = stripHtml(rawDesc);
    let source = tagText(chunk, "source");
    if (!source) {
      const font = rawDesc.match(/<font[^>]*>([\s\S]*?)<\/font>/i);
      if (font) source = stripHtml(font[1]);
    }
    if (!source) {
      try {
        source = new URL(link).hostname.replace(/^www\./, "");
      } catch {
        source = "web";
      }
    }
    // Bing 跳转链：展示名不要用 bing.com
    if (/bing\.com/i.test(source)) source = "Bing News";
    if (/news\.google\.com/i.test(source)) source = "Google News";
    const pub = tagText(chunk, "pubDate");
    if (!title || !link) continue;
    items.push({
      title: truncate(title, 80),
      link,
      summary: truncate(summary, 140) || "点击查看原文报道。",
      pub,
      source: truncate(source, 32),
    });
  }
  return items;
}

function guessCountry(host, targetSide) {
  const h = String(host || "").toLowerCase();
  if (/bbc\.|theguardian\.|reuters\.|apnews\.|nytimes\.|cnn\.|dw\.|ft\.|bloomberg\.|cnbc\.|politico\./.test(h)) {
    if (/bbc\./.test(h)) return "uk";
    if (/dw\./.test(h)) return "de";
    return "us";
  }
  if (/huanqiu\.|guancha\.|people\.|xinhua\.|cctv\.|cgtn\.|thepaper\.|sina\.|163\.|qq\.|sohu\./.test(h)) return "cn";
  return targetSide === "left" ? "us" : "cn";
}

function toYmd(pub) {
  if (!pub) return "";
  const d = new Date(pub);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10);
}

async function fetchBingNews(q) {
  const url =
    "https://www.bing.com/news/search?q=" +
    encodeURIComponent(q) +
    "&format=RSS&setlang=zh-hans";
  const resp = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (compatible; SatireDailyBot/1.0; +https://www.yangmaoqun.fun)",
      Accept: "application/rss+xml, application/xml, text/xml, */*",
    },
  });
  if (!resp.ok) throw new Error("bing " + resp.status);
  return parseRss(await resp.text());
}

async function fetchGoogleNews(q, hl) {
  const lang = hl === "en" ? "en-US" : "zh-CN";
  const url =
    "https://news.google.com/rss/search?q=" +
    encodeURIComponent(q) +
    "&hl=" +
    (hl === "en" ? "en-US" : "zh-CN") +
    "&gl=" +
    (hl === "en" ? "US" : "CN") +
    "&ceid=" +
    (hl === "en" ? "US:en" : "CN:zh-Hans");
  const resp = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (compatible; SatireDailyBot/1.0; +https://www.yangmaoqun.fun)",
      Accept: "application/rss+xml, application/xml, text/xml, */*",
    },
  });
  if (!resp.ok) throw new Error("gnews " + resp.status);
  return parseRss(await resp.text());
}

function heuristicPlan(q) {
  const domesticHints = ["哪吒", "华为", "比亚迪", "小米", "A股", "沪指", "城投", "解放军", "国漫", "主旋律"];
  const overseasHints = ["特斯拉", "苹果", "美军", "北约", "好莱坞", "迪士尼", "漫威", "OpenAI", "美联储", "华尔街"];
  let domestic = domesticHints.some((k) => q.includes(k));
  let overseas = overseasHints.some((k) => q.includes(k));
  if (!domestic && !overseas) {
    // 默认按国内词处理，去找海外镜像
    domestic = true;
  }
  if (domestic && !overseas) {
    return {
      leaning: "domestic",
      target_side: "right",
      topic_hint: q.includes("哪吒") || q.includes("电影") ? "电影" : "其他",
      explanation: "国内主体 → 实时检索海外/对照侧新闻",
      queries: [
        { q: q + " 海外 外媒", lang: "zh" },
        { q: q + " Hollywood OR Disney OR Western media", lang: "en" },
        { q: q, lang: "en" },
      ],
    };
  }
  if (overseas && !domestic) {
    return {
      leaning: "overseas",
      target_side: "left",
      topic_hint: "其他",
      explanation: "海外主体 → 实时检索中媒相关批评报道",
      queries: [
        { q: q + " 中国 评论", lang: "zh" },
        { q: q + " 外媒 双标", lang: "zh" },
        { q: q, lang: "zh" },
      ],
    };
  }
  return {
    leaning: "unknown",
    target_side: "right",
    topic_hint: "其他",
    explanation: "混合主体，优先检索对侧新闻",
    queries: [
      { q: q, lang: "zh" },
      { q: q, lang: "en" },
    ],
  };
}

async function planWithAi(q, env) {
  const API_KEY = (env && env.AI_API_KEY) || "";
  if (!API_KEY) return { ...heuristicPlan(q), source: "heuristic" };
  const BASE = String((env && env.AI_BASE_URL) || "https://coding.92onegame.com/v1").replace(/\/$/, "");
  const MODEL = (env && env.AI_MODEL) || "auto";
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
  if (!resp.ok) return { ...heuristicPlan(q), source: "heuristic" };
  const data = await resp.json();
  const content = data?.choices?.[0]?.message?.content || "";
  try {
    const plan = JSON.parse(extractJson(content));
    const leaning = ["domestic", "overseas", "unknown"].includes(plan.leaning) ? plan.leaning : "unknown";
    let target_side = plan.target_side;
    if (target_side !== "left" && target_side !== "right") {
      target_side = leaning === "domestic" ? "right" : leaning === "overseas" ? "left" : "right";
    }
    const queries = Array.isArray(plan.queries)
      ? plan.queries
          .map((x) => ({
            q: String(x?.q || "").trim(),
            lang: x?.lang === "en" ? "en" : "zh",
          }))
          .filter((x) => x.q)
          .slice(0, 4)
      : [];
    if (queries.length === 0) return { ...heuristicPlan(q), source: "heuristic" };
    return {
      leaning,
      target_side,
      topic_hint: String(plan.topic_hint || "").trim() || "其他",
      explanation: String(plan.explanation || "").trim(),
      queries,
      source: "ai",
    };
  } catch {
    return { ...heuristicPlan(q), source: "heuristic" };
  }
}

async function liveSearch(plan) {
  const seen = new Set();
  const out = [];
  const jobs = (plan.queries || []).slice(0, 4).map(async (query) => {
    const rows = [];
    try {
      rows.push(...(await fetchBingNews(query.q)));
    } catch {
      /* ignore */
    }
    try {
      rows.push(...(await fetchGoogleNews(query.q, query.lang)));
    } catch {
      /* ignore */
    }
    return rows;
  });
  const batches = await Promise.all(jobs);
  for (const rows of batches) {
    for (const row of rows) {
      const key = row.link;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(row);
      if (out.length >= 16) return out;
    }
  }
  return out;
}

function toCards(rows, plan) {
  const side = plan.target_side === "left" ? "left" : "right";
  return rows.slice(0, 16).map((row, i) => {
    const host = (() => {
      try {
        return new URL(row.link).hostname.replace(/^www\./, "");
      } catch {
        return row.source || "web";
      }
    })();
    const title = truncate(stripHtml(row.title), 80);
    const summary = truncate(stripHtml(row.summary), 140) || "点击查看原文报道。";
    return {
      side,
      title_cn: title,
      summary_cn: summary,
      quote_cn: makeSpicyQuote(title, side, i),
      source: truncate(stripHtml(row.source || host), 32),
      source_url: row.link,
      source_country: guessCountry(host, side),
      published: toYmd(row.pub),
      topic: plan.topic_hint || "其他",
      absurdity: 4 + (i % 4),
      mirror_issue: "live_search",
      live: true,
      rank: i + 1,
    };
  });
}

async function handlePost(request, env) {
  let q = "";
  try {
    const body = await request.json();
    q = String(body.q || body.query || "").trim();
  } catch {
    return jsonResp(400, { error: "invalid json" });
  }
  if (!q) return jsonResp(400, { error: "empty query" });

  const plan = await planWithAi(q, env || {});
  const rows = await liveSearch(plan);
  let items = toCards(rows, plan);
  items = await spiceQuotesWithAi(items, env || {});
  return jsonResp(200, {
    q,
    leaning: plan.leaning,
    target_side: plan.target_side,
    topic_hint: plan.topic_hint,
    explanation: plan.explanation,
    plan_source: plan.source,
    queries: plan.queries,
    items,
    source: "live",
  });
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
