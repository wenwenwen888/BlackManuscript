/* 嘲讽日报 - 无限滚动 + 类型筛选
 * 从 /articles.json 拉全部文章，按 10 条/批 append 到左右栏
 * 左右交替的 items 按 side 字段分发到对应栏
 * 类型筛选：点击 chip 后只渲染对应 topic 的文章，重置已加载并清空 DOM
 */
(function () {
  "use strict";

  const leftBody = document.getElementById("left-body");
  const rightBody = document.getElementById("right-body");
  const leftEmpty = document.getElementById("left-empty");
  const rightEmpty = document.getElementById("right-empty");
  const sentinel = document.getElementById("infinite-sentinel");
  const loader = document.getElementById("infinite-loader");
  const end = document.getElementById("infinite-end");
  const counter = document.getElementById("counter");
  const typeFilter = document.getElementById("type-filter");

  if (!leftBody || !rightBody || !sentinel) return;

  const BATCH_SIZE = 10;
  let allItems = [];
  let filteredItems = [];  // 按当前筛选过滤后的列表
  let headToHeadList = []; // [{ left, right, note }, ...] 最多 5 组
  let reportDate = "";     // 日报日期 YYYY-MM-DD
  let loadedIndex = 0;
  let leftCount = 0;
  let rightCount = 0;
  let loading = false;
  let done = false;
  let currentTopic = "全部";
  let observer = null;

  const h2hSection = document.getElementById("head-to-head");
  const h2hList = document.getElementById("h2h-list");
  const h2hNote = document.getElementById("h2h-note");
  const dateBar = document.getElementById("date-bar");

  // === 镜像搜索元素 ===
  const searchBar = document.getElementById("search-bar");
  const searchInput = document.getElementById("search-input");
  const searchClearBtn = document.getElementById("search-clear");
  const searchResults = document.getElementById("search-results");
  const searchSummary = document.getElementById("search-summary");
  const searchList = document.getElementById("search-list");
  const searchBack = document.getElementById("search-results-back");
  const versusGrid = document.querySelector(".versus-grid");
  let searchResultsItems = [];
  let searchActive = false;

  function normalizeHeadToHead(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.filter((p) => p && p.left && p.right).slice(0, 5);
    if (raw.left && raw.right) return [raw];
    return [];
  }

  function latestPublished(items) {
    let best = "";
    for (const it of items) {
      const p = it.published || "";
      if (p && p > best) best = p;
    }
    return best;
  }

  function sortByNewest(items) {
    // 保持左右交替观感：先按日期降序分组，再交替
    const left = items
      .filter((it) => it.side === "left")
      .sort((a, b) => (b.published || "").localeCompare(a.published || ""));
    const right = items
      .filter((it) => it.side === "right")
      .sort((a, b) => (b.published || "").localeCompare(a.published || ""));
    const out = [];
    const n = Math.max(left.length, right.length);
    for (let i = 0; i < n; i++) {
      if (i < left.length) out.push(left[i]);
      if (i < right.length) out.push(right[i]);
    }
    return out;
  }

  function h2hUrlSet() {
    const s = new Set();
    headToHeadList.forEach((p) => {
      if (p.left && p.left.source_url) s.add(p.left.source_url);
      if (p.right && p.right.source_url) s.add(p.right.source_url);
    });
    return s;
  }

  function itemsForTopic(topic) {
    if (topic === "全部") {
      // 全部：主列表去掉已在对擂展示的，避免重复
      const skip = h2hUrlSet();
      return allItems.filter((it) => !skip.has(it.source_url));
    }
    return sortByNewest(allItems.filter((it) => it.topic === topic));
  }

  function updateDateBar() {
    if (!dateBar) return;
    const day = reportDate || latestPublished(allItems);
    if (day) {
      dateBar.textContent = `羊毛群嘲讽日报 · ${day} · 借嘴说话，左右对擂`;
    } else {
      dateBar.textContent = "羊毛群嘲讽日报 · 借嘴说话，左右对擂";
    }
  }

  function updateTopicChips() {
    if (!typeFilter) return;
    const counts = {};
    allItems.forEach((it) => {
      counts[it.topic] = (counts[it.topic] || 0) + 1;
    });
    let needReset = false;
    typeFilter.querySelectorAll(".chip").forEach((chip) => {
      const topic = chip.dataset.topic;
      if (!topic) return;
      if (topic === "全部") {
        chip.textContent = "全部";
        chip.disabled = false;
        chip.classList.remove("chip--empty");
        return;
      }
      const n = counts[topic] || 0;
      chip.textContent = topic;
      chip.disabled = n === 0;
      chip.classList.toggle("chip--empty", n === 0);
      if (n === 0 && currentTopic === topic) needReset = true;
    });
    if (needReset) {
      typeFilter.querySelectorAll(".chip").forEach((c) => c.classList.remove("chip--active"));
      const allChip = typeFilter.querySelector('.chip[data-topic="全部"]');
      if (allChip) allChip.classList.add("chip--active");
      // 直接重置状态，避免递归
      currentTopic = "全部";
      filteredItems = itemsForTopic("全部");
    }
  }

  // 国旗 emoji 映射
  const FLAGS = {
    cn: "🇨🇳", uk: "🇬🇧", us: "🇺🇸", de: "🇩🇪", fr: "🇫🇷", jp: "🇯🇵",
    ru: "🇷🇺", eu: "🇪🇺", in: "🇮🇳", ir: "🇮🇷", kr: "🇰🇷", au: "🇦🇺",
    ca: "🇨🇦", hk: "🇭🇰",
  };
  const flag = (c) => FLAGS[c] || "🌐";

  const stars = (n) => {
    const filled = Math.ceil(n / 2);
    return "★".repeat(filled) + "☆".repeat(5 - filled);
  };

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  // globalIndex: 该 item 在 filteredItems 里的下标，用于分享按钮定位；h2h 卡片用负下标占位
  function renderCard(item, globalIndex, extraClass) {
    const quoteHtml = item.quote_cn
      ? `<blockquote class="quote">
           <span class="quote-mark">"</span>${escapeHtml(item.quote_cn)}<span class="quote-mark">"</span>
         </blockquote>`
      : "";
    const shareBtn =
      globalIndex >= 0
        ? `<button class="share-btn" data-idx="${globalIndex}" type="button" aria-label="分享这张卡片">分享</button>`
        : `<button class="share-btn" data-h2h="${globalIndex}" type="button" aria-label="分享这张卡片">分享</button>`;
    const cls = extraClass
      ? `news-card news-card--entering ${extraClass}`
      : "news-card news-card--entering";

    return `
      <article class="${cls}" data-topic="${escapeAttr(item.topic)}">
        <div class="source-bar">
          <span class="flag">${flag(item.source_country)}</span>
          <span class="media">${escapeHtml(item.source)}</span>
          ${item.published ? `<span class="sep">·</span><span class="pub-date">${escapeHtml(item.published)}</span>` : ""}
          <span class="sep">·</span>
          <span class="topic-tag">${escapeHtml(item.topic)}</span>
          <a class="source-link" href="${escapeAttr(item.source_url)}" target="_blank" rel="noopener noreferrer">${(item.source_url || "").includes("bing.com/search") ? "相关报道 ↗" : "原文 ↗"}</a>
        </div>
        <a class="title" href="${escapeAttr(item.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title_cn)}</a>
        <p class="summary">${escapeHtml(item.summary_cn)}</p>
        ${quoteHtml}
        <div class="meta">
          <span class="absurdity">
            荒诞指数 <span class="absurdity-meter">${stars(item.absurdity)}</span> ${item.absurdity}/10
          </span>
          ${shareBtn}
        </div>
      </article>
    `;
  }

  function renderHeadToHead() {
    if (!h2hSection || !h2hList) return;
    // 仅在「全部」时显示今日对擂
    if (currentTopic !== "全部" || headToHeadList.length === 0) {
      h2hSection.hidden = true;
      h2hList.innerHTML = "";
      return;
    }
    if (h2hNote) {
      h2hNote.textContent = `同议题左右互搏 · 共 ${headToHeadList.length} 组`;
    }
    const blocks = headToHeadList.map((pair, pi) => {
      const note = escapeHtml(pair.note || `对擂 ${pi + 1}`);
      return `
        <div class="head-to-head__pair" data-h2h-pair="${pi}">
          <div class="head-to-head__pair-note">${note}</div>
          <div class="head-to-head__grid">
            <div class="head-to-head__side head-to-head__side--left">
              ${renderCard(pair.left, -(pi * 2 + 1), "news-card--h2h")}
            </div>
            <div class="head-to-head__vs" aria-hidden="true">VS</div>
            <div class="head-to-head__side head-to-head__side--right">
              ${renderCard(pair.right, -(pi * 2 + 2), "news-card--h2h")}
            </div>
          </div>
        </div>`;
    });
    h2hList.innerHTML = blocks.join("");
    h2hSection.hidden = false;
    requestAnimationFrame(() => {
      h2hSection.querySelectorAll(".news-card--entering").forEach((el) => {
        el.classList.remove("news-card--entering");
        void el.offsetWidth;
        el.classList.add("news-card--visible");
      });
    });
  }

  // 渲染一批（最多 BATCH_SIZE 条），从 filteredItems 取
  function renderBatch() {
    const batch = filteredItems.slice(loadedIndex, loadedIndex + BATCH_SIZE);
    if (batch.length === 0) {
      finish();
      return;
    }

    if (leftEmpty) leftEmpty.remove();
    if (rightEmpty) rightEmpty.remove();

    const leftHtml = [];
    const rightHtml = [];
    batch.forEach((item, i) => {
      const gi = loadedIndex + i;  // 在 filteredItems 里的全局下标，供分享按钮定位
      if (item.side === "left") {
        leftHtml.push(renderCard(item, gi));
        leftCount++;
      } else {
        rightHtml.push(renderCard(item, gi));
        rightCount++;
      }
    });

    leftBody.insertAdjacentHTML("beforeend", leftHtml.join(""));
    rightBody.insertAdjacentHTML("beforeend", rightHtml.join(""));

    requestAnimationFrame(() => {
      document.querySelectorAll(".news-card--entering").forEach((el) => {
        el.classList.remove("news-card--entering");
        void el.offsetWidth;
        el.classList.add("news-card--visible");
      });
    });

    loadedIndex += batch.length;
    updateCounter();

    if (loadedIndex >= filteredItems.length) {
      finish();
    }
  }

  function updateCounter() {
    if (!counter) return;
    counter.textContent = `${currentTopic !== "全部" ? currentTopic + " · " : ""}已加载 ${loadedIndex} / ${filteredItems.length} 条（左 ${leftCount} / 右 ${rightCount}）`;
  }

  function finish() {
    if (done) return;
    done = true;
    loader.hidden = true;
    sentinel.style.display = "none";
    end.hidden = false;
    if (counter) {
      counter.textContent = `${currentTopic !== "全部" ? currentTopic + " · " : ""}全部 ${filteredItems.length} 条 · 左 ${leftCount} / 右 ${rightCount}`;
    }
    if (observer) observer.disconnect();
  }

  // 切换筛选：清空 DOM + 重置计数 + 重新计算 filteredItems
  function switchFilter(topic) {
    if (topic === currentTopic && !searchActive) return;
    // 搜索态下点 chip：先退出搜索 UI（下方会重新渲染主列表）
    if (searchActive) {
      searchActive = false;
      searchResultsItems = [];
      if (searchResults) searchResults.hidden = true;
      if (searchList) searchList.innerHTML = "";
      if (searchClearBtn) searchClearBtn.hidden = true;
      if (searchInput) searchInput.value = "";
      if (versusGrid) versusGrid.style.display = "";
      if (sentinel) sentinel.style.display = "";
    }
    currentTopic = topic;

    // 更新 URL hash（刷新可恢复筛选状态）
    if (topic === "全部") {
      history.replaceState(null, "", location.pathname + location.search);
    } else {
      history.replaceState(null, "", "#topic=" + encodeURIComponent(topic));
    }

    // 清空 DOM
    leftBody.innerHTML = "";
    rightBody.innerHTML = "";
    leftCount = 0;
    rightCount = 0;
    loadedIndex = 0;
    done = false;
    loader.hidden = true;
    end.hidden = true;
    sentinel.style.display = "";

    // 重新计算 filteredItems（筛选后仍按最新日期左右交替）
    filteredItems = itemsForTopic(topic);

    renderHeadToHead();

    // 重新挂上 observer（如果之前断开过）
    if (!observer) setupObserver();
    else observer.observe(sentinel);

    // 渲染首批
    renderBatch();

    // 若筛选后为空
    if (filteredItems.length === 0) {
      leftBody.innerHTML = '<div class="empty">该类型暂无内容</div>';
      rightBody.innerHTML = '<div class="empty">该类型暂无内容</div>';
      finish();
    }
  }

  // === 镜像搜索：国内外实体同义词表 ===
  // 搜国内词 → 扩展到海外实体；搜海外词 → 扩展到国内实体
  const DOMESTIC_TO_OVERSEAS = {
    "华为": ["特斯拉", "苹果"],
    "比亚迪": ["特斯拉"],
    "小米": ["苹果"],
    "国产芯片": ["英特尔", "英伟达", "台积电"],
    "国产大模型": ["ChatGPT", "OpenAI"],
    "国产新能源": ["特斯拉"],
    "国产数据库": ["谷歌"],
    "解放军": ["美军"],
    "海军": ["美军"],
    "航母": ["美军", "北约"],
    "军演": ["美军"],
    "两会": ["国会", "议会"],
    "城投": ["华尔街"],
  };
  const OVERSEAS_TO_DOMESTIC = {
    "特斯拉": ["华为", "比亚迪", "国产新能源"],
    "苹果": ["华为", "小米"],
    "OpenAI": ["国产大模型"],
    "ChatGPT": ["国产大模型"],
    "英特尔": ["国产芯片"],
    "英伟达": ["国产芯片"],
    "美军": ["解放军", "海军"],
    "北约": ["解放军"],
    "好莱坞": ["国漫"],
    "硅谷": ["国产芯片", "国产大模型"],
    "美联储": ["央行"],
    "华尔街": ["城投"],
    "谷歌": ["国产大模型"],
  };

  function detectLeaning(q) {
    let domestic = false, overseas = false;
    for (const k in DOMESTIC_TO_OVERSEAS) if (q.includes(k)) domestic = true;
    for (const k in OVERSEAS_TO_DOMESTIC) if (q.includes(k)) overseas = true;
    if (domestic && !overseas) return "domestic";
    if (overseas && !domestic) return "overseas";
    return "unknown";
  }

  function expandQuery(q, leaning) {
    const terms = new Set([q]);
    const apply = (map) => {
      for (const k in map) if (q.includes(k)) map[k].forEach((t) => terms.add(t));
    };
    if (leaning === "domestic") apply(DOMESTIC_TO_OVERSEAS);
    else if (leaning === "overseas") apply(OVERSEAS_TO_DOMESTIC);
    else { apply(DOMESTIC_TO_OVERSEAS); apply(OVERSEAS_TO_DOMESTIC); }
    return [...terms];
  }

  function itemMatchesAny(item, terms) {
    const hay = (item.title_cn || "") + (item.summary_cn || "") + (item.quote_cn || "");
    return terms.some((t) => t && hay.includes(t));
  }

  // 镜像搜索核心：输入 Q → 返回对侧镜像结果
  function runMirrorSearch(q) {
    q = (q || "").trim();
    if (!q) return null;
    const leaning = detectLeaning(q);
    // 检测 Q 中包含的实体词（同义词表 key），用于直接命中与镜像兜底
    const entityTerms = [];
    for (const k in DOMESTIC_TO_OVERSEAS) if (q.includes(k)) entityTerms.push(k);
    for (const k in OVERSEAS_TO_DOMESTIC) if (q.includes(k)) entityTerms.push(k);
    const directTerms = entityTerms.length > 0 ? [q, ...entityTerms] : [q];
    const expanded = expandQuery(q, leaning);
    // 直接命中：Q 本身或任一实体词
    const directMatches = allItems.filter((it) => itemMatchesAny(it, directTerms));
    // 扩展词命中（不含直接命中）
    const expandedMatches = allItems.filter(
      (it) => !itemMatchesAny(it, directTerms) && itemMatchesAny(it, expanded)
    );
    // 目标栏：国内词→右(海外)，海外词→左(国内)，未知→直接命中较多的对侧
    let targetSide = null;
    if (leaning === "domestic") targetSide = "right";
    else if (leaning === "overseas") targetSide = "left";
    else {
      const lc = directMatches.filter((it) => it.side === "left").length;
      const rc = directMatches.filter((it) => it.side === "right").length;
      if (lc > rc) targetSide = "right";
      else if (rc > lc) targetSide = "left";
    }
    // 镜像兜底：每个直接命中按 mirror_issue 找对侧，topic 兜底；每命中最多 5 条
    const mirrorMap = new Map();
    for (const dm of directMatches) {
      const mi = dm.mirror_issue;
      let cands = mi
        ? allItems.filter((it) => it.side !== dm.side && it.mirror_issue === mi)
        : [];
      if (cands.length === 0) {
        cands = allItems.filter((it) => it.side !== dm.side && it.topic === dm.topic);
      }
      cands.slice(0, 5).forEach((it) => mirrorMap.set(it.source_url, it));
    }
    // 合并：扩展命中 + 镜像 + 直接命中里落在目标栏的
    const result = new Map();
    expandedMatches.forEach((it) => result.set(it.source_url, it));
    mirrorMap.forEach((it, url) => result.set(url, it));
    directMatches
      .filter((it) => targetSide && it.side === targetSide)
      .forEach((it) => result.set(it.source_url, it));
    let arr = [...result.values()];
    if (targetSide) {
      const filtered = arr.filter((it) => it.side === targetSide);
      if (filtered.length > 0) arr = filtered;
    }
    // 限制结果数，避免过宽查询返回过多
    const MAX_RESULTS = 24;
    if (arr.length > MAX_RESULTS) arr = arr.slice(0, MAX_RESULTS);
    return { items: arr, leaning, targetSide, directCount: directMatches.length };
  }

  // 搜索卡片：复用 renderCard 视觉，分享按钮用 data-search-idx 定位
  function renderSearchCard(item, idx) {
    const html = renderCard(item, -9999, "news-card--search");
    return html.replace('data-h2h="-9999"', 'data-search-idx="' + idx + '"');
  }

  function showSearchResults(query) {
    const res = runMirrorSearch(query);
    if (!res) return;
    searchResultsItems = res.items;
    searchActive = true;

    // 隐藏主列表
    if (h2hSection) h2hSection.hidden = true;
    if (versusGrid) versusGrid.style.display = "none";
    if (sentinel) sentinel.style.display = "none";
    if (loader) loader.hidden = true;
    if (end) end.hidden = true;
    if (counter) counter.textContent = "";
    if (observer) observer.disconnect();
    if (searchClearBtn) searchClearBtn.hidden = false;

    const targetLabel =
      res.targetSide === "right" ? "镜像海外"
      : res.targetSide === "left" ? "镜像国内"
      : "镜像结果";

    if (res.items.length === 0) {
      if (searchSummary) {
        searchSummary.innerHTML =
          `未找到「<span class="q">${escapeHtml(query)}</span>」的镜像新闻，换个关键词试试`;
      }
      if (searchList) {
        searchList.innerHTML =
          '<div class="search-results__empty">无结果 · 可尝试：华为 / 特斯拉 / 美军 / 城投 / 国产芯片 / 好莱坞</div>';
      }
    } else {
      if (searchSummary) {
        const tagCls = res.targetSide === "left" ? "tag tag--left" : "tag";
        searchSummary.innerHTML =
          `搜索「<span class="q">${escapeHtml(query)}</span>」` +
          `<span class="${tagCls}">${targetLabel}</span> · ${res.items.length} 条`;
      }
      if (searchList) {
        searchList.innerHTML = res.items
          .map((it, i) => renderSearchCard(it, i))
          .join("");
        requestAnimationFrame(() => {
          searchList.querySelectorAll(".news-card--entering").forEach((el) => {
            el.classList.remove("news-card--entering");
            void el.offsetWidth;
            el.classList.add("news-card--visible");
          });
        });
      }
    }
    if (searchResults) searchResults.hidden = false;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function clearSearch() {
    if (!searchActive) return;
    searchActive = false;
    searchResultsItems = [];
    if (searchResults) searchResults.hidden = true;
    if (searchList) searchList.innerHTML = "";
    if (searchInput) searchInput.value = "";
    if (searchClearBtn) searchClearBtn.hidden = true;
    if (versusGrid) versusGrid.style.display = "";
    if (sentinel) sentinel.style.display = "";
    // 重新渲染当前筛选
    leftBody.innerHTML = "";
    rightBody.innerHTML = "";
    leftCount = 0;
    rightCount = 0;
    loadedIndex = 0;
    done = false;
    loader.hidden = true;
    end.hidden = true;
    filteredItems = itemsForTopic(currentTopic);
    renderHeadToHead();
    if (!observer) setupObserver();
    else observer.observe(sentinel);
    renderBatch();
  }

  async function loadInitial() {
    try {
      const resp = await fetch((window.__BASE__ || "/") + "articles.json");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      reportDate = data.date || "";
      headToHeadList = normalizeHeadToHead(data.head_to_head);
      // 过滤假链，按最新日期优先左右交替
      allItems = sortByNewest(
        (data.items || []).filter((it) => {
          const u = (it.source_url || "").toLowerCase();
          return u && !u.includes("example.com") && !u.includes("example.org");
        })
      );
      filteredItems = itemsForTopic("全部");
      updateDateBar();
      updateTopicChips();

      if (allItems.length === 0) {
        if (leftEmpty) leftEmpty.textContent = "暂无有效新闻，请稍后再来";
        if (rightEmpty) rightEmpty.textContent = "暂无有效新闻，请稍后再来";
        return;
      }

      // 读 URL hash 恢复筛选状态（刷新页面不丢失筛选）
      const hashMatch = location.hash.match(/^#topic=(.+)$/);
      if (hashMatch) {
        const topic = decodeURIComponent(hashMatch[1]);
        const chip = typeFilter && typeFilter.querySelector('.chip[data-topic="' + topic + '"]');
        if (chip && topic !== "全部") {
          typeFilter.querySelectorAll(".chip").forEach((c) => c.classList.remove("chip--active"));
          chip.classList.add("chip--active");
          switchFilter(topic);
          return;
        }
      }

      renderHeadToHead();
      renderBatch();
      setupObserver();
    } catch (e) {
      console.error("[infinite] 加载 articles.json 失败", e);
      if (leftEmpty) leftEmpty.textContent = "加载失败，请刷新";
      if (rightEmpty) rightEmpty.textContent = "加载失败，请刷新";
    }
  }

  function setupObserver() {
    if (observer) return;
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !loading && !done) {
            loadNext();
          }
        }
      },
      { rootMargin: "400px 0px" }
    );
    observer.observe(sentinel);
  }

  async function loadNext() {
    if (loading || done) return;
    loading = true;
    loader.hidden = false;
    await new Promise((r) => requestAnimationFrame(r));
    renderBatch();
    loading = false;
    loader.hidden = true;
  }

  // 绑定 chip 点击
  if (typeFilter) {
    typeFilter.addEventListener("click", (e) => {
      const target = e.target.closest(".chip");
      if (!target) return;
      const topic = target.dataset.topic;
      if (!topic) return;
      if (topic === currentTopic && !searchActive) return;

      // 更新激活态
      typeFilter.querySelectorAll(".chip").forEach((c) => c.classList.remove("chip--active"));
      target.classList.add("chip--active");

      switchFilter(topic);

      // 滚回顶部
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // === 镜像搜索事件绑定 ===
  if (searchBar) {
    searchBar.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = (searchInput && searchInput.value ? searchInput.value : "").trim();
      if (q) showSearchResults(q);
    });
  }
  if (searchClearBtn) {
    searchClearBtn.addEventListener("click", () => {
      if (searchActive) {
        clearSearch();
      } else {
        if (searchInput) { searchInput.value = ""; searchInput.focus(); }
        searchClearBtn.hidden = true;
      }
    });
  }
  if (searchBack) {
    searchBack.addEventListener("click", () => clearSearch());
  }
  // 搜索框输入时实时显示/隐藏清除按钮
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      if (searchInput.value && !searchActive) {
        if (searchClearBtn) searchClearBtn.hidden = false;
      } else if (!searchInput.value && !searchActive) {
        if (searchClearBtn) searchClearBtn.hidden = true;
      }
    });
  }

  // === 分享按钮事件委托（卡片是动态插入的，用委托）===
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".share-btn");
    if (!btn) return;
    e.preventDefault();
    let item = null;
    if (btn.dataset.searchIdx != null) {
      const idx = parseInt(btn.dataset.searchIdx, 10);
      if (!isNaN(idx)) item = searchResultsItems[idx];
    } else if (btn.dataset.h2h != null && headToHeadList.length) {
      const code = parseInt(btn.dataset.h2h, 10);
      // 负下标编码：-(pair*2+1)=left, -(pair*2+2)=right
      const n = Math.abs(code);
      const pairIdx = Math.floor((n - 1) / 2);
      const isLeft = (n % 2) === 1;
      const pair = headToHeadList[pairIdx];
      if (pair) item = isLeft ? pair.left : pair.right;
    } else {
      const idx = parseInt(btn.dataset.idx, 10);
      if (!isNaN(idx)) item = filteredItems[idx];
    }
    if (!item) return;
    if (window.SatireDaily && window.SatireDaily.openShareModal) {
      window.SatireDaily.openShareModal(item);
    } else {
      console.warn("[share] share.js 未加载，无法分享");
    }
  });

  // === 回到顶部按钮（左右各一个）===
  const bttLeft = document.getElementById("back-to-top-left");
  const bttRight = document.getElementById("back-to-top-right");
  const SHOW_THRESHOLD = 400;

  function toggleBackToTop() {
    const show = window.scrollY > SHOW_THRESHOLD;
    if (bttLeft) bttLeft.hidden = !show;
    if (bttRight) bttRight.hidden = !show;
  }

  window.addEventListener("scroll", toggleBackToTop, { passive: true });
  window.addEventListener("resize", toggleBackToTop, { passive: true });
  toggleBackToTop();

  [bttLeft, bttRight].forEach((b) => {
    if (!b) return;
    b.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  // 启动
  loadInitial();
})();
