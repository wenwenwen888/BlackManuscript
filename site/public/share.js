/* 嘲讽日报 - 分享功能
 *
 * 把卡片字段绘制为 Canvas 图片，弹出浮层供用户长按发送到微信。
 * 不依赖外部库（html2canvas 等），纯手绘 Canvas，输出可控。
 *
 * 微信分享现实：普通网页无法直接调起微信聊天发图（需公众号 + JSSDK + 备案域名）。
 * 本站境外部署走不通那条路，改用：生成图片 → 长按图片 → 微信内置"发送给朋友/保存"。
 * 因此弹层里必须用 <img> 而非 <canvas>（微信只能长按 img 触发菜单）。
 */
(function () {
  "use strict";

  var FLAGS = {
    cn: "🇨🇳", uk: "🇬🇧", us: "🇺🇸", de: "🇩🇪", fr: "🇫🇷", jp: "🇯🇵",
    ru: "🇷🇺", eu: "🇪🇺", "in": "🇮🇳", ir: "🇮🇷", kr: "🇰🇷", au: "🇦🇺",
    ca: "🇨🇦", hk: "🇭🇰",
  };
  function flag(c) { return FLAGS[c] || "🌐"; }
  function stars(n) {
    var f = Math.ceil(n / 2);
    return "★".repeat(f) + "☆".repeat(5 - f);
  }

  var COLORS = {
    left:  { accent: "#c0392b", bg: "#fdf2f0" },
    right: { accent: "#1e5f8e", bg: "#f0f5fa" },
    paper: "#fffefb",
    ink: "#1a1a1a",
    muted: "#6b6660",
    divider: "#e0dcd2",
    tagBg: "#efeae0", tagInk: "#5a5046",
  };

  var FONT_SERIF = '"Noto Serif SC", "Source Han Serif SC", "Songti SC", "宋体", serif';
  var FONT_SANS = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';

  // 中英混排按字符换行（对中文友好，英文单词可能被拆开但可接受）
  function wrapChars(ctx, text, maxWidth) {
    var chars = Array.from(text || "");
    var lines = [];
    var line = "";
    for (var i = 0; i < chars.length; i++) {
      var ch = chars[i];
      if (ch === "\n") {
        lines.push(line);
        line = "";
        continue;
      }
      var test = line + ch;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = ch;
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawShareCard(item) {
    var W = 750;
    var PAD = 44;
    var contentW = W - PAD * 2;
    var side = item.side === "right" ? "right" : "left";
    var c = COLORS[side];

    // 先用临时 ctx 量出各段高度
    var tmp = document.createElement("canvas").getContext("2d");

    tmp.font = "700 30px " + FONT_SERIF;
    var titleLines = wrapChars(tmp, item.title_cn || "", contentW).slice(0, 3);

    tmp.font = "400 20px " + FONT_SANS;
    var summaryLines = wrapChars(tmp, item.summary_cn || "", contentW).slice(0, 6);

    var quoteLines = [];
    if (item.quote_cn) {
      tmp.font = "600 22px " + FONT_SERIF;
      quoteLines = wrapChars(tmp, item.quote_cn, contentW - 48).slice(0, 3);
    }

    // 原文链接（底部小字，最多 2 行，超出截断加省略号）
    var urlLines = [];
    if (item.source_url) {
      tmp.font = "400 13px " + FONT_SANS;
      var allUrlLines = wrapChars(tmp, item.source_url, contentW);
      urlLines = allUrlLines.slice(0, 2);
      if (allUrlLines.length > 2 && urlLines.length === 2) {
        urlLines[1] = urlLines[1].slice(0, Math.max(0, urlLines[1].length - 1)) + "…";
      }
    }

    // 计算总高度
    var H = PAD + 8;       // 顶部色带 + padding
    H += 50;               // flag/source 行
    H += 20;               // 分隔线 + 间距
    H += titleLines.length * 40 + 12;
    H += summaryLines.length * 32 + 16;
    if (quoteLines.length) {
      H += 28 + quoteLines.length * 36 + 20;
    }
    H += 36;               // 荒诞指数行
    H += 24 + 10;          // 底部分隔 + 间距
    H += urlLines.length ? (urlLines.length * 18 + 10) : 0;  // 原文链接行
    H += 60;               // 水印两行
    H += PAD;
    if (H < 600) H = 600;

    var canvas = document.createElement("canvas");
    var dpr = window.devicePixelRatio || 1;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    var ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);

    // 背景
    ctx.fillStyle = COLORS.paper;
    ctx.fillRect(0, 0, W, H);

    // 顶部色带
    ctx.fillStyle = c.accent;
    ctx.fillRect(0, 0, W, 8);

    var y = PAD + 8 + 24;

    // 顶部行：国旗 + 来源 + 主题标签
    ctx.textBaseline = "middle";
    ctx.fillStyle = COLORS.ink;
    ctx.font = "400 36px " + FONT_SANS;
    var flagText = flag(item.source_country);
    ctx.fillText(flagText, PAD, y);
    var flagW = ctx.measureText(flagText).width;

    ctx.font = "700 24px " + FONT_SANS;
    ctx.fillText(item.source || "", PAD + flagW + 14, y + 2);

    // 主题标签（右对齐胶囊）
    var topicText = item.topic || "";
    ctx.font = "400 18px " + FONT_SANS;
    var tagTextW = ctx.measureText(topicText).width;
    var tagW = tagTextW + 28;
    var tagX = W - PAD - tagW;
    var tagY = y - 16;
    ctx.fillStyle = COLORS.tagBg;
    roundRect(ctx, tagX, tagY, tagW, 32, 4);
    ctx.fill();
    ctx.fillStyle = COLORS.tagInk;
    ctx.textAlign = "center";
    ctx.fillText(topicText, tagX + tagW / 2, y);
    ctx.textAlign = "left";

    y += 34;

    // 分隔线
    ctx.strokeStyle = COLORS.divider;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PAD, y);
    ctx.lineTo(W - PAD, y);
    ctx.stroke();
    y += 24;

    // 标题
    ctx.fillStyle = COLORS.ink;
    ctx.font = "700 30px " + FONT_SERIF;
    ctx.textBaseline = "top";
    for (var i = 0; i < titleLines.length; i++) {
      ctx.fillText(titleLines[i], PAD, y);
      y += 40;
    }
    y += 4;

    // 摘要
    ctx.fillStyle = COLORS.ink;
    ctx.font = "400 20px " + FONT_SANS;
    for (var j = 0; j < summaryLines.length; j++) {
      ctx.fillText(summaryLines[j], PAD, y);
      y += 32;
    }
    y += 12;

    // 金句块
    if (quoteLines.length) {
      var blockH = 28 + quoteLines.length * 36 + 20;
      var blockX = PAD;
      var blockY = y;
      var blockW = contentW;
      ctx.fillStyle = c.bg;
      roundRect(ctx, blockX, blockY, blockW, blockH, 6);
      ctx.fill();
      ctx.fillStyle = c.accent;
      ctx.fillRect(blockX, blockY, 4, blockH);

      ctx.fillStyle = COLORS.ink;
      ctx.font = "600 22px " + FONT_SERIF;
      ctx.textBaseline = "top";
      var qy = blockY + 24;
      for (var k = 0; k < quoteLines.length; k++) {
        ctx.fillText(quoteLines[k], blockX + 24, qy);
        qy += 36;
      }
      y = blockY + blockH + 16;
    }

    // 荒诞指数
    ctx.fillStyle = COLORS.muted;
    ctx.font = "400 18px " + FONT_SANS;
    ctx.textBaseline = "middle";
    var absText = "荒诞指数 " + stars(item.absurdity) + "  " + item.absurdity + "/10";
    ctx.fillText(absText, PAD, y + 12);
    y += 36;

    // 底部分隔线
    y += 10;
    ctx.strokeStyle = COLORS.divider;
    ctx.beginPath();
    ctx.moveTo(PAD, y);
    ctx.lineTo(W - PAD, y);
    ctx.stroke();
    y += 24;

    // 原文链接（小字，便于溯源）
    if (urlLines.length) {
      ctx.fillStyle = COLORS.muted;
      ctx.font = "400 13px " + FONT_SANS;
      ctx.textBaseline = "top";
      for (var u = 0; u < urlLines.length; u++) {
        ctx.fillText(urlLines[u], PAD, y);
        y += 18;
      }
      y += 10;
    }

    // 水印
    ctx.fillStyle = COLORS.ink;
    ctx.font = "700 20px " + FONT_SERIF;
    ctx.textBaseline = "top";
    ctx.fillText("羊毛群嘲讽日报", PAD, y);
    ctx.fillStyle = COLORS.muted;
    ctx.font = "400 14px " + FONT_SANS;
    ctx.fillText("长按图片发送给微信好友 · 立场归属原媒体", PAD, y + 28);

    return canvas;
  }

  function openShareModal(item) {
    var modal = document.getElementById("share-modal");
    if (!modal) return false;

    var holder = document.getElementById("share-image-holder");
    if (!holder) return false;

    // 先显示 modal + loading 态
    holder.innerHTML = '<div class="share-modal__loading">生成图片中…</div>';
    modal.hidden = false;
    document.body.style.overflow = "hidden";

    // 异步一帧，让浏览器渲染 loading 再画 canvas
    requestAnimationFrame(function () {
      var canvas;
      try {
        canvas = drawShareCard(item);
      } catch (e) {
        holder.innerHTML = '<div class="share-modal__loading">生成失败：' + escapeHtml(String(e)) + "</div>";
        return;
      }
      var dataUrl;
      try {
        dataUrl = canvas.toDataURL("image/png");
      } catch (e) {
        holder.innerHTML = '<div class="share-modal__loading">图片导出失败（可能是跨域污染）</div>';
        return;
      }
      holder.innerHTML = "";
      var img = document.createElement("img");
      img.src = dataUrl;
      img.alt = "分享图片 - " + (item.title_cn || "");
      img.className = "share-image";
      holder.appendChild(img);

      var dl = document.getElementById("share-download");
      if (dl) {
        dl.onclick = function () {
          var a = document.createElement("a");
          a.href = dataUrl;
          var name = (item.title_cn || "分享").replace(/[\\/:*?"<>|]/g, "").slice(0, 20);
          a.download = "嘲讽日报-" + name + ".png";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
        };
      }
    });
    return true;
  }

  function closeShareModal() {
    var modal = document.getElementById("share-modal");
    if (modal) modal.hidden = true;
    document.body.style.overflow = "";
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // 绑定弹层关闭交互（Esc、点 backdrop、点 ×）
  function bindModalClose() {
    var modal = document.getElementById("share-modal");
    if (!modal || modal.dataset.bound) return;
    modal.dataset.bound = "1";

    var closeBtn = document.getElementById("share-close");
    if (closeBtn) closeBtn.addEventListener("click", closeShareModal);

    // 点 backdrop（panel 外）关闭
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeShareModal();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !modal.hidden) closeShareModal();
    });
  }

  window.SatireDaily = window.SatireDaily || {};
  window.SatireDaily.openShareModal = openShareModal;
  window.SatireDaily.closeShareModal = closeShareModal;
  window.SatireDaily.bindModalClose = bindModalClose;

  // DOM 就绪后自动绑定关闭事件
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindModalClose);
  } else {
    bindModalClose();
  }
})();
