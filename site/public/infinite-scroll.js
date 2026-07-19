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
  let loadedIndex = 0;
  let leftCount = 0;
  let rightCount = 0;
  let loading = false;
  let done = false;
  let currentTopic = "全部";
  let observer = null;

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

  // globalIndex: 该 item 在 filteredItems 里的下标，用于分享按钮定位
  function renderCard(item, globalIndex) {
    const quoteHtml = item.quote_cn
      ? `<blockquote class="quote">
           <span class="quote-mark">"</span>${escapeHtml(item.quote_cn)}<span class="quote-mark">"</span>
         </blockquote>`
      : "";

    return `
      <article class="news-card news-card--entering" data-topic="${escapeAttr(item.topic)}">
        <div class="source-bar">
          <span class="flag">${flag(item.source_country)}</span>
          <span class="media">${escapeHtml(item.source)}</span>
          <span class="sep">·</span>
          <span class="topic-tag">${escapeHtml(item.topic)}</span>
          <a class="source-link" href="${escapeAttr(item.source_url)}" target="_blank" rel="noopener noreferrer">原文 ↗</a>
        </div>
        <a class="title" href="${escapeAttr(item.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title_cn)}</a>
        <p class="summary">${escapeHtml(item.summary_cn)}</p>
        ${quoteHtml}
        <div class="meta">
          <span class="absurdity">
            荒诞指数 <span class="absurdity-meter">${stars(item.absurdity)}</span> ${item.absurdity}/10
          </span>
          <button class="share-btn" data-idx="${globalIndex}" type="button" aria-label="分享这张卡片">分享</button>
        </div>
      </article>
    `;
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

    // 重新计算 filteredItems
    if (topic === "全部") {
      filteredItems = allItems;
    } else {
      filteredItems = allItems.filter((it) => it.topic === topic);
    }

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
      allItems = data.items || [];
      filteredItems = allItems;
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
    const idx = parseInt(btn.dataset.idx, 10);
    if (isNaN(idx) || !filteredItems[idx]) return;
    if (window.SatireDaily && window.SatireDaily.openShareModal) {
      window.SatireDaily.openShareModal(filteredItems[idx]);
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
