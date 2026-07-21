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
核心：把用户查询「镜像」到对侧世界的同类新闻，绝不是原词换个语言再搜一遍。

只输出 JSON：
{
  "leaning": "domestic" | "overseas" | "unknown",
  "target_side": "left" | "right",
  "topic_hint": "股票|政治|经济|社会|科技|军事|外交|文化|环境|电影|娱乐|其他",
  "exclude_terms": ["必须排除的原侧实体，如华为"],
  "explanation": "一句话说明镜像：原词→对侧词",
  "queries": [
    { "q": "检索词（必须是对侧实体+同一议题）", "lang": "zh" | "en" }
  ]
}

硬性规则：
1) 国内主体 → leaning=domestic, target_side=right
   - 必须换成海外对照实体再搜，禁止 queries 里再出现华为/哪吒/比亚迪等原侧实体
   - 例：华为智驾撞人 → Tesla Autopilot crash / Waymo pedestrian accident / 特斯拉 自动驾驶 撞人
   - 例：哪吒票房 → Hollywood box office / Disney animation revenue / 好莱坞 票房
2) 海外主体 → leaning=overseas, target_side=left
   - 必须换成国内对照实体再搜，禁止 queries 只搜原海外实体本身
   - 例：特斯拉撞人 → 华为 智驾 事故 / 国产自动驾驶 撞人
3) queries 给 3~4 条：中英都要有，短而可搜，实体+议题齐全`;

/** 国内实体 → 海外对照检索词 */
const DOMESTIC_MIRROR = [
  {
    keys: ["华为", "乾崑", "问界"],
    topicKeys: ["智驾", "自动驾驶", "撞人", "车祸", "事故", "ADS"],
    topic: "科技",
    exclude: ["华为", "乾崑", "问界", "Huawei"],
    queries: [
      { q: "特斯拉 自动驾驶 撞人", lang: "zh" },
      { q: "特斯拉 Autopilot 事故", lang: "zh" },
      { q: "Waymo 无人车 撞人", lang: "zh" },
      { q: "Tesla Autopilot crash pedestrian", lang: "en" },
    ],
    explanation: "华为智驾事故 → 镜像特斯拉/Waymo 等海外智驾事故",
  },
  {
    keys: ["比亚迪"],
    topicKeys: ["智驾", "自动驾驶", "撞人", "车祸", "事故"],
    topic: "科技",
    exclude: ["比亚迪", "BYD"],
    queries: [
      { q: "特斯拉 智驾 事故", lang: "zh" },
      { q: "特斯拉 自动驾驶 撞人", lang: "zh" },
      { q: "Tesla Autopilot crash", lang: "en" },
    ],
    explanation: "比亚迪智驾议题 → 镜像特斯拉等海外电动车智驾事故",
  },
  {
    keys: ["哪吒", "国漫", "主旋律"],
    topicKeys: ["票房", "电影", "动画"],
    topic: "电影",
    exclude: ["哪吒", "国漫"],
    queries: [
      { q: "好莱坞 动画 票房", lang: "zh" },
      { q: "迪士尼 皮克斯 票房", lang: "zh" },
      { q: "Hollywood box office animation", lang: "en" },
      { q: "Disney Pixar box office", lang: "en" },
    ],
    explanation: "国产动画/哪吒 → 镜像好莱坞动画与票房新闻",
  },
  {
    keys: ["华为", "小米", "国产芯片", "国产大模型"],
    topicKeys: [],
    topic: "科技",
    exclude: ["华为", "小米", "Huawei", "Xiaomi"],
    queries: [
      { q: "特斯拉 争议", lang: "zh" },
      { q: "苹果 反垄断", lang: "zh" },
      { q: "OpenAI 安全争议", lang: "zh" },
      { q: "Tesla Autopilot controversy", lang: "en" },
    ],
    explanation: "国产科技主体 → 镜像苹果/特斯拉/OpenAI 等海外对照",
  },
];

/** 海外实体 → 国内对照检索词 */
const OVERSEAS_MIRROR = [
  {
    keys: ["特斯拉", "Tesla", "Waymo", "FSD", "Autopilot"],
    topicKeys: ["智驾", "自动驾驶", "撞人", "车祸", "事故", "crash"],
    topic: "科技",
    exclude: ["特斯拉", "Tesla", "Waymo", "Autopilot"],
    queries: [
      { q: "华为 智驾 事故", lang: "zh" },
      { q: "国产自动驾驶 撞人", lang: "zh" },
      { q: "问界 智驾 车祸", lang: "zh" },
      { q: "小鹏 自动驾驶 事故", lang: "zh" },
    ],
    explanation: "海外智驾事故 → 镜像国产智驾同类事故报道",
  },
  {
    keys: ["好莱坞", "迪士尼", "漫威", "皮克斯", "奥斯卡"],
    topicKeys: ["票房", "电影"],
    topic: "电影",
    exclude: ["好莱坞", "迪士尼", "漫威", "Hollywood", "Disney"],
    queries: [
      { q: "哪吒 票房", lang: "zh" },
      { q: "国产动画 票房", lang: "zh" },
      { q: "主旋律 电影 票房", lang: "zh" },
    ],
    explanation: "好莱坞电影话题 → 镜像国产动画/档期票房",
  },
];

function matchMirrorRule(q, rules) {
  let best = null;
  let bestScore = -1;
  for (const rule of rules) {
    const hitKey = rule.keys.some((k) => q.toLowerCase().includes(String(k).toLowerCase()));
    if (!hitKey) continue;
    const topicHits = (rule.topicKeys || []).filter((k) => q.toLowerCase().includes(String(k).toLowerCase())).length;
    const score = 10 + topicHits * 5;
    if (score > bestScore) {
      bestScore = score;
      best = rule;
    }
  }
  return best;
}

function heuristicPlan(q) {
  const raw = String(q || "").trim();
  const domesticHints = ["哪吒", "华为", "比亚迪", "小米", "A股", "沪指", "城投", "解放军", "国漫", "主旋律", "问界", "乾崑"];
  const overseasHints = ["特斯拉", "Tesla", "Waymo", "苹果", "美军", "北约", "好莱坞", "迪士尼", "漫威", "OpenAI", "美联储", "华尔街", "Autopilot", "FSD"];
  let domestic = domesticHints.some((k) => raw.includes(k));
  let overseas = overseasHints.some((k) => raw.toLowerCase().includes(String(k).toLowerCase()));

  const dRule = matchMirrorRule(raw, DOMESTIC_MIRROR);
  const oRule = matchMirrorRule(raw, OVERSEAS_MIRROR);

  // 优先命中具体镜像规则
  if (dRule && (!oRule || domestic)) {
    return {
      leaning: "domestic",
      target_side: "right",
      topic_hint: dRule.topic || "科技",
      exclude_terms: dRule.exclude || [],
      explanation: dRule.explanation,
      queries: dRule.queries,
      strong: true,
    };
  }
  if (oRule) {
    return {
      leaning: "overseas",
      target_side: "left",
      topic_hint: oRule.topic || "科技",
      exclude_terms: oRule.exclude || [],
      explanation: oRule.explanation,
      queries: oRule.queries,
      strong: true,
    };
  }

  if (!domestic && !overseas) domestic = true;

  if (domestic && !overseas) {
    // 泛化：抽议题词，拼海外实体，绝不原样复用国内主体词
    const issue = raw
      .replace(/华为|比亚迪|小米|哪吒|国产|问界|乾崑/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const issueEn = /撞人|车祸|事故/.test(raw)
      ? "crash accident"
      : /智驾|自动驾驶/.test(raw)
        ? "autonomous driving"
        : /票房/.test(raw)
          ? "box office"
          : "controversy";
    return {
      leaning: "domestic",
      target_side: "right",
      topic_hint: /电影|票房|哪吒/.test(raw) ? "电影" : "科技",
      exclude_terms: ["华为", "比亚迪", "小米", "哪吒", "Huawei"],
      explanation: "国内主体 → 检索海外对照实体的同类新闻",
      queries: [
        { q: `Tesla ${issueEn}`, lang: "en" },
        { q: `Waymo ${issueEn}`, lang: "en" },
        { q: `特斯拉 ${issue || "争议"}`.trim(), lang: "zh" },
        { q: `Hollywood ${issueEn}`, lang: "en" },
      ],
    };
  }
  if (overseas && !domestic) {
    const issue = raw
      .replace(/特斯拉|Tesla|Waymo|好莱坞|迪士尼|漫威|苹果|OpenAI|Autopilot|FSD/gi, " ")
      .replace(/\s+/g, " ")
      .trim();
    return {
      leaning: "overseas",
      target_side: "left",
      topic_hint: "其他",
      exclude_terms: ["特斯拉", "Tesla", "Waymo", "Hollywood"],
      explanation: "海外主体 → 检索国内对照实体的同类新闻",
      queries: [
        { q: `华为 ${issue || "争议"}`.trim(), lang: "zh" },
        { q: `国产 ${issue || "智驾"}`.trim(), lang: "zh" },
        { q: `哪吒 ${issue || "票房"}`.trim(), lang: "zh" },
      ],
    };
  }
  return {
    leaning: "unknown",
    target_side: "right",
    topic_hint: "其他",
    exclude_terms: [],
    explanation: "混合主体，优先检索对侧对照新闻",
    queries: [
      { q: "Tesla Autopilot crash", lang: "en" },
      { q: "特斯拉 自动驾驶 事故", lang: "zh" },
    ],
  };
}

function filterMirroredRows(rows, plan) {
  const excludes = (plan.exclude_terms || [])
    .map((x) => String(x || "").trim())
    .filter(Boolean);
  if (excludes.length === 0) return rows;
  const kept = rows.filter((row) => {
    const hay = `${row.title || ""} ${row.summary || ""} ${row.source || ""}`;
    return !excludes.some((ex) => hay.toLowerCase().includes(ex.toLowerCase()));
  });
  // 过滤过狠时回退，避免空结果
  return kept.length >= 3 ? kept : rows;
}
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

function looksEnglish(s) {
  const t = String(s || "");
  const letters = (t.match(/[A-Za-z]/g) || []).length;
  const cjk = (t.match(/[\u4e00-\u9fff]/g) || []).length;
  return letters >= 12 && letters > cjk * 2;
}

function makeSpicyQuote(title, side, i, topic) {
  const tech = [
    "智驾很忙，责任很闲。",
    "辅助驾驶一出事，说明书先逃遁。",
    "功能名很满，边界很空。",
    "宣传里全自动，事故里全人工。",
    "算法很自信，行人很脆弱。",
    "更新日志很长，问责名单很短。",
    "方向盘能放手，锅甩得更快。",
    "试点很热闹，复盘很安静。",
  ];
  const film = [
    "票房数字会说话，叙事更会化妆。",
    "神话好写，复盘难写。",
    "档期很满，口碑另算。",
    "热搜有保质期，争议没有。",
  ];
  const generic = [
    "热闹是真的，追问常常迟到。",
    "标题先高潮，细节后补课。",
    "立场先入座，事实后入座。",
    "叙事很忙，复杂性很闲。",
  ];
  const hay = `${title || ""} ${topic || ""}`;
  let pool = generic;
  if (/科技|智驾|自动驾驶|撞|事故|Tesla|Autopilot|Waymo|crash/i.test(hay)) pool = tech;
  else if (/电影|票房|动画|好莱坞|哪吒/i.test(hay)) pool = film;
  else if (side === "left") pool = generic;
  return pool[i % pool.length];
}

async function localizeCards(items, env, userQuery) {
  const API_KEY = (env && env.AI_API_KEY) || "";
  if (!API_KEY || !items.length) return items;

  const BASE = String((env && env.AI_BASE_URL) || "https://coding.92onegame.com/v1").replace(/\/$/, "");
  const MODEL = (env && env.AI_MODEL) || "auto";
  const payload = items
    .slice(0, 12)
    .map(
      (it, i) =>
        `${i + 1}.\n标题: ${it.title_cn}\n摘要: ${it.summary_cn}`
    )
    .join("\n\n");

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 14000);
  try {
    const resp = await fetch(BASE + "/chat/completions", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        temperature: 0.3,
        messages: [
          {
            role: "system",
            content:
              "你是嘲讽日报编辑。用户正在做镜像搜索。\n" +
              "对每条新闻输出中文：title（标题翻译/润色成自然中文）、summary（摘要翻译成中文，40~70字）、quote（一句贴题辣评，12~28字，口语讽刺，禁止票房套话除非真是电影票房新闻）。\n" +
              "只输出 JSON 数组，元素形如 {\"title\":\"\",\"summary\":\"\",\"quote\":\"\"}，顺序与输入一致。不要 markdown。",
          },
          {
            role: "user",
            content: `用户原查询：${userQuery}\n\n待处理新闻：\n${payload}`,
          },
        ],
      }),
      signal: ctrl.signal,
    });
    if (!resp.ok) return items;
    const data = await resp.json();
    const content = data?.choices?.[0]?.message?.content || "";
    const arr = JSON.parse(extractJson(content));
    if (!Array.isArray(arr)) return items;
    return items.map((it, i) => {
      const row = arr[i] || {};
      const title = truncate(stripHtml(row.title || it.title_cn), 80);
      const summary = truncate(stripHtml(row.summary || it.summary_cn), 140);
      let quote = stripHtml(row.quote || it.quote_cn);
      quote = quote.replace(/^["「『]|["」』]$/g, "").trim().slice(0, 40);
      return {
        ...it,
        title_cn: title || it.title_cn,
        summary_cn: summary || it.summary_cn,
        quote_cn: quote || it.quote_cn,
        translated: Boolean(row.title || row.summary),
      };
    });
  } catch {
    return items;
  } finally {
    clearTimeout(timer);
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

async function fetchBingNews(q, lang) {
  const setlang = lang === "en" ? "en-us" : "zh-hans";
  const cc = lang === "en" ? "US" : "CN";
  const url =
    "https://www.bing.com/news/search?q=" +
    encodeURIComponent(q) +
    "&format=RSS&setlang=" +
    setlang +
    "&cc=" +
    cc;
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

async function planWithAi(q, env) {
  const fallback = { ...heuristicPlan(q), source: "heuristic" };
  // 规则已能精准镜像（如华为智驾→特斯拉）时跳过 LLM，显著降延迟
  if (fallback.strong) return fallback;

  const API_KEY = (env && env.AI_API_KEY) || "";
  if (!API_KEY) return fallback;

  const BASE = String((env && env.AI_BASE_URL) || "https://coding.92onegame.com/v1").replace(/\/$/, "");
  const MODEL = (env && env.AI_MODEL) || "auto";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const resp = await fetch(BASE + "/chat/completions", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + API_KEY,
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
      signal: ctrl.signal,
    });
    if (!resp.ok) return fallback;
    const data = await resp.json();
    const content = data?.choices?.[0]?.message?.content || "";
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
          .slice(0, 3)
      : [];
    if (queries.length === 0) return fallback;
    const exclude_terms = Array.isArray(plan.exclude_terms)
      ? plan.exclude_terms.map((x) => String(x || "").trim()).filter(Boolean)
      : fallback.exclude_terms || [];
    const joined = queries.map((x) => x.q).join(" ");
    const leaked = exclude_terms.some((ex) => joined.toLowerCase().includes(ex.toLowerCase()));
    if (leaked) return fallback;
    return {
      leaning,
      target_side,
      topic_hint: String(plan.topic_hint || "").trim() || fallback.topic_hint || "其他",
      exclude_terms,
      explanation: String(plan.explanation || "").trim() || fallback.explanation,
      queries,
      source: "ai",
    };
  } catch {
    return fallback;
  } finally {
    clearTimeout(timer);
  }
}

async function liveSearch(plan) {
  const seen = new Set();
  const out = [];
  const queries = [...(plan.queries || [])].slice(0, 3);
  // 优先中文检索结果，英文源后面再翻译
  queries.sort((a, b) => (a.lang === "zh" ? 0 : 1) - (b.lang === "zh" ? 0 : 1));
  const jobs = queries.map(async (query) => {
    const rows = [];
    // 海外镜像优先英文 Bing；中文查询再用 Google
    try {
      rows.push(...(await fetchBingNews(query.q, query.lang)));
    } catch {
      /* ignore */
    }
    if (rows.length < 4) {
      try {
        rows.push(...(await fetchGoogleNews(query.q, query.lang)));
      } catch {
        /* ignore */
      }
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
      if (out.length >= 20) break;
    }
  }
  return filterMirroredRows(out, plan).slice(0, 12);
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
      quote_cn: makeSpicyQuote(title, side, i, plan.topic_hint),
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
  items = await localizeCards(items, env || {}, q);
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
