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
    if (topic === currentTopic) return;
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
      if (!topic || topic === currentTopic) return;

      // 更新激活态
      typeFilter.querySelectorAll(".chip").forEach((c) => c.classList.remove("chip--active"));
      target.classList.add("chip--active");

      switchFilter(topic);

      // 滚回顶部
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // === 分享按钮事件委托（卡片是动态插入的，用委托）===
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".share-btn");
    if (!btn) return;
    e.preventDefault();
    let item = null;
    if (btn.dataset.h2h != null && headToHeadList.length) {
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
