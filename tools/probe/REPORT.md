# 抓取源可行性探查报告

探查日期：2026-07-19
探查环境：开发机在国内网络（受 GFW 限制）

## 一、关键结论

1. **国内源**（右栏素材：中国媒体嘲讽海外）：观察者网、环球时报**均可用纯 HTTP + 正则**抓取，无需 headless 浏览器
2. **境外中文源**（左栏素材：外媒嘲讽中国）：BBC 中文 / RFI / DW / Reuters 在国内均不可达（GFW 阻断），证实"爬虫必须部署在境外 VPS"的架构判断
3. **境外英文源**：AP 在国内可直连，Reuters 不可达；境外 VPS 部署后所有英文源应都可用
4. **环球时报的 SSR 注水技巧**：列表与详情数据均嵌在 HTML 的 `<textarea class="item-...">` 里，正则即可稳定提取

## 二、已验证的源

### ✅ 观察者网（guancha.cn）— 可用

- **列表页入口**：`https://www.guancha.cn/internation`（国际/涉外栏目）
- **正文页 URL 规律**：`https://www.guancha.cn/{栏目}/YYYY_MM_DD_{aid}.shtml`
- **正文选择器**：`<div class="content all-txt">…</div>`（注意是多 class）
- **元数据**：
  - 来源：`来源：观察者网`（正则 `来源[:：]\s*([^\s<]+)`）
  - 日期：`2026-07-19` 格式
  - 作者：`作者[:：]\s*([^\s<]+)`（专栏作者页）
- **正文清洗**：结尾常带 `本文系观察者网独家稿件，未经授权，不得转载` 等声明，需过滤
- **示例验证**：542 字正文 + 来源 + 日期全部成功提取
- **没有 RSS**：`/rss/*.xml` 全 404，走 HTML 列表抓取
- **涉外评论栏目**：观察者网"评论"板块有大量涉外嘲讽内容（沈逸、张维为、施洋等专栏），按专栏作者页抓取更精准

### ✅ 环球时报 / 环球网（huanqiu.com）— 可用，且更省力

- **列表页入口**：`https://world.huanqiu.com/`（国际频道）
- **正文页 URL 规律**：`https://{频道}.huanqiu.com/article/{aid}`（aid 是 11 位 base62 字符串，如 `4SRRiSqejA5`）
- **关键技术：SSR 注水** — 列表项和正文都嵌在 `<textarea>` 里，正则即可稳定提取
  - 列表项：`<textarea class="item-aid">`、`item-title`、`item-time`（毫秒时间戳）、`item-cnf-host`
  - 详情项：`article-title`、`article-content`（含 HTML 标签）、`article-source-name`（来源媒体，常带 `<a>` 链接）、`article-time`
- **来源链**：环球时报常转引其他媒体，`article-source-name` 直接给出真实源（如"新华网"带原文链接），正好契合"必须带来源"的要求
- **示例验证**：列表页 19 条全提取 + 详情页正文+来源+时间戳全提取
- **频道候选**：`world`（国际）、`opinion`（社评/国际锐评）、`oversea`（海外）、`mil`（军事/国际）

### ✅ CGTN（cgtn.com）— 可用，英文涉外评论丰富

- **列表页入口**：`https://www.cgtn.com/opinions`（评论栏目，文章链接直接 SSR 在 HTML 里）
- **正文页 URL 规律**：`https://news.cgtn.com/news/YYYY-MM-DD/{slug}-{id}/p.html`
- **元数据**（OG 协议，最稳）：
  - `property="og:title"` → 标题
  - `property="og:description"` → 文章摘要（LLM 之前可先用这个）
- **正文选择器**：`<div class="text en">…</div>`（class 是 `text {lang}` 多类形式，有 `en`/`zh` 等语言后缀），用正则 `class="[^"]*\btext\b[^"]*"` 后看后缀挑语言
- **示例验证**：1060 字英文正文成功提取，开头含 Editor's note + 内容明显嘲讽欧洲
- **优势**：英文涉外评论标题本身就带嘲讽性质，如 "China's air-conditioners cool Europe's hotheads"、"AI fabrications part of wider anti-China propaganda"，完美契合右栏定位

### ✅ 参考消息（chinadaily.com.cn 子站托管）— 可用
- 入口可达（59KB HTML + 140 链接），有 8 条 world 相关链接样本，结构常规，需补正则后可用

## 三、已排除的源

| 源 | 原因 |
|---|---|
| 新华网国际 (`xinhuanet.com/world/`) | 纯 SPA，无 SSR 注水，需 headless，性价比低 |
| 中国新闻网国际 (`chinanews.com.cn/gj/`) | 403 拒绝默认 UA，需伪造更完整头，留作备选 |
| 人民日报海外版 (`paper.people.com.cn/rmrbhwb/`) | 首页仅 264B，疑似跳转/异常，待后续验证 |
| 环球时报 RSS | 不提供 RSS（404）|
| 观察者网 RSS | 不提供 RSS（404）|

## 三之B、待验证的源（境外 VPS 部署后再测）

### 左栏（外媒涉华）— 国内不可达，待境外验证

| 源 | 语言 | 抓取入口 | 备注 |
|---|---|---|---|
| BBC 中文 | 中文 | `https://www.bbc.com/zhongwen/simp` | 国内超时，境外应可 |
| RFI 法广 | 中文 | `https://www.rfi.fr/cn/` | 国内超时 |
| DW 德国之声 | 中文 | `https://www.dw.com/zh/` | 国内超时 |
| Reuters China | 英文 | `https://www.reuters.com/world/china/` | 国内超时，AP 可达说明不是工具问题 |
| NYT / WSJ | 英文 | 各自 China 频道 | 需境外测 |
| The Economist | 英文 | China 板块 | 需境外测 |
| AP China | 英文 | `https://apnews.com/hub/china` | **国内可直连**，作为兜底英文源 |

### 右栏补充（中国媒体涉外）— 国内可达，已部分验证

| 源 | 抓取入口 | 状态 |
|---|---|---|
| CGTN opinions | `https://www.cgtn.com/opinions` | ✅ 已验证可用 |
| 参考消息 | `https://china.chinadaily.com.cn/` | ✅ 可达，待正则 |
| 中国日报-世界 | `https://www.chinadaily.com.cn/world` | ✅ 可达（81 链接），待正则 |
| 国际在线 | `http://gb.cri.cn/` | ✅ 可达（254 链接），待正则 |
| 求是网-国际 | `http://www.qstheory.cn/international/` | ✅ 可达（52 链接），待正则 |

## 四、对架构的修正

原 PLAN.md 假设"可能需要 headless 浏览器"，实际探查后修正为：

- **国内源全部走 HTTP + 正则**，不用 headless（轻量、快、稳）
- **爬虫主进程跑在境外 VPS**：左栏源必须境外，右栏源境外也能抓（不需要境内 IP）
- **dev 机只能开发/调试右栏逻辑**：左栏逻辑需在 VPS 上验证
- 备用 headless：若后续发现某个源加反爬或纯前端渲染，再上 Playwright，不要默认上

## 五、下一步

1. ✅ 抓取源探查完成（国内可达源全部验证，境外源待 VPS 验证）
2. 进入下一阶段：**LLM prompt 模板设计**（分类/翻译摘要/打标签）
3. 之后：Astro 站点骨架
