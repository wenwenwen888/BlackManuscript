# 嘲讽日报 / Satire Daily

> 每日聚合"外媒嘲讽中国"与"中国官媒嘲讽海外"的现成报道，左右对擂呈现。
> 仅搬运摘要 + 原文链接，不创作讽刺内容。版权及立场归属原媒体。

---

## 目录

- [项目定位](#项目定位)
- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [爬虫与 LLM 流水线](#爬虫与-llm-流水线)
- [站点架构](#站点架构)
- [数据格式](#数据格式)
- [部署](#部署)
- [安全与合规](#安全与合规)
- [项目状态与路线图](#项目状态与路线图)
- [常见问题](#常见问题)

---

## 项目定位

**嘲讽日报**是一个左右对擂的舆情聚合站：

- **左栏**：外媒嘲讽/批评国内的报道（BBC、Reuters、NYT、WSJ、Economist 等）
- **右栏**：中国官媒嘲讽/批评海外的报道（环球时报、观察者网、CGTN 等）

核心卖点是 **"借嘴说话"**——戏剧性来自两侧报道的**对比本身**，而不是本站自己写讽刺。本站只做摘要 + 原文链接搬运，立场全部归属原媒体。

**受众与运营**：公开但低调运营，境外部署，不留主体信息。

---

## 核心特性

- **左右对擂布局**：左红右蓝分栏，同屏对比呈现，移动端自动堆叠
- **无限滚动**：客户端按 10 条/批加载，IntersectionObserver 触发，左右交替排列
- **金句高亮**：每张卡片可含 `quote_cn` 金句字段，带色条+衬线斜体高亮块
- **荒诞指数**：1-10 评分原文既有嘲讽力度，五星可视化，用于排序
- **分享到微信**：每张卡片可生成 Canvas 图片，长按发送给微信好友或下载
- **回到顶部**：滚动后左右下角各出现按钮，平滑回顶
- **来源溯源**：每张卡片强制标注媒体名 + 国旗 + 主题 + 原文链接
- **安全阀**：LLM 三段式 pipeline + 关键词黑名单 + 摘要歪曲校验 + drafts 池
- **静态输出**：Astro 静态构建，免数据库、免运维，托管免费

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 站点 | [Astro](https://astro.build/) 4.16 | 静态输出，content collections schema 校验 |
| 前端交互 | 原生 JS | 无框架，`infinite-scroll.js` + `share.js` |
| 样式 | 原生 CSS | CSS 变量 + 响应式，无预处理器 |
| 爬虫 | Python 3 + 标准库 | `urllib` + 正则，无 requests 依赖 |
| LLM | OpenAI 兼容 API | 支持 OpenAI / DeepSeek / 通义 / Kimi，纯 `urllib` 调用 |
| 数据 | JSON 文件 | 统一文章流，随 Git 入库即归档 |
| 部署 | 腾讯云 EdgeOne Pages | 全球边缘网络，默认域名免备案 |

---

## 项目结构

```
BlackManuscript/
├── PLAN.md                          # 项目总规划（定位/规则/架构/合规）
├── README.md                        # 本文档
├── .gitignore
│
├── prompts/                         # LLM prompt 模板
│   ├── README.md                    # prompt 设计原则与调用流程
│   ├── classify.py                  # 分类：是否在嘲讽对方（门控）
│   ├── process.py                   # 处理：摘要+主题+荒诞指数+金句
│   ├── validate.py                  # 校验：摘要是否歪曲原意（安全阀）
│   └── examples.py                  # 示例输入/输出，回归测试用
│
├── scraper/                         # 爬虫 + LLM 流水线
│   ├── README.md
│   ├── main.py                      # CLI 入口
│   ├── config.py                    # 源注册表 + 路径配置
│   ├── fetcher.py                   # HTTP 抓取（UA/超时/重试/限速）
│   ├── sources/                     # 源适配层（统一接口）
│   │   ├── base.py                  # Source 抽象基类 + Article 数据类
│   │   ├── guancha.py               # 观察者网
│   │   ├── huanqiu.py               # 环球时报（SSR textarea 注水）
│   │   └── cgtn.py                  # CGTN
│   ├── llm/
│   │   ├── client.py                # OpenAI 兼容客户端
│   │   ├── pipeline.py              # classify→process→validate 串联
│   │   └── safety.py                # 关键词黑名单 + drafts 池
│   ├── utils/
│   │   └── json_io.py               # JSON 读写 + head-to-head 检测
│   └── output/                      # 运行产物（gitignore，不入库）
│       ├── daily/                   # 正式发布的每日 JSON
│       └── drafts/                  # 被拦截的内容，待人工复核
│
├── site/                            # Astro 静态站点
│   ├── README.md
│   ├── astro.config.mjs
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── components/
│   │   │   ├── Flag.astro           # ISO 国家代码 → emoji 国旗
│   │   │   ├── SourceBar.astro      # 来源条
│   │   │   ├── NewsCard.astro       # 文章卡片（含金句块）
│   │   │   ├── VsColumn.astro       # 左/右栏容器（遗留，index 不再用）
│   │   │   └── HeadToHead.astro     # 今日对擂（已停用，CSS 留作死代码）
│   │   ├── content/
│   │   │   ├── config.ts            # articles collection schema
│   │   │   └── daily/
│   │   │       └── articles.json    # 统一文章流数据
│   │   ├── layouts/
│   │   │   └── BaseLayout.astro     # 全站布局 + 免责声明页脚
│   │   ├── pages/
│   │   │   ├── index.astro          # 首页（客户端无限滚动）
│   │   │   └── archive/             # 历史归档（遗留路由）
│   │   └── styles/
│   │       └── global.css           # 全局样式
│   └── public/                      # 静态资源（随构建部署）
│       ├── articles.json            # 供客户端 fetch 的文章流
│       ├── infinite-scroll.js       # 无限滚动 + 卡片渲染 + 回到顶部
│       └── share.js                 # Canvas 分享卡片绘制
│
└── tools/                           # 辅助工具
    ├── generate_articles.py         # 手写演示数据生成器（~100 条）
    └── probe/                       # 抓取源可行性探查
        ├── REPORT.md                # 探查结论报告
        ├── cgtn_*.py                # CGTN 抓取探查
        ├── huanqiu_*.py             # 环球时报抓取探查
        ├── guancha_article.py       # 观察者网正文探查
        ├── right_sources_scan.py    # 右栏源扫描
        ├── xinhua_check.py          # 新华网（已排除，纯 SPA）
        ├── validate_sample_data.py  # 示例数据校验
        ├── test_scraper.py          # scraper 模块单元测试
        └── find_quote_issues.py     # JSON 引号嵌套检查
```

---

## 快速开始

### 环境要求

- **Node.js** ≥ 18.14.1（推荐 20.x）
- **Python** ≥ 3.10（爬虫用，跑站点不需要）
- **Git**

### 安装与本地开发

```bash
# 克隆仓库
git clone git@github.com:wenwenwen888/BlackManuscript.git
cd BlackManuscript

# 安装站点依赖（首次）
cd site
npm install

# 启动开发服务器
npm run dev
# → http://localhost:4321
```

开发服务器支持热重载，改 `src/` 下的文件自动刷新。

### 构建

```bash
cd site
npm run build      # 输出到 site/dist/
npm run preview    # 本地预览构建产物
```

### 生成演示数据

仓库自带的 `site/public/articles.json` 是由 `tools/generate_articles.py` 生成的演示数据（约 100 条，左右交替）。重新生成：

```bash
python tools/generate_articles.py
# 会写入 site/src/content/daily/articles.json
# 需手动拷到 site/public/articles.json 供客户端 fetch
```

> 注意：演示数据的 `source_url` 多为 `example.com` 占位符，仅供样式与交互验证。

---

## 爬虫与 LLM 流水线

### 已支持的源

| 源 | 栏位 | 抓取方式 | 备注 |
|---|---|---|---|
| 观察者网（guancha.cn） | 右栏 | HTTP + 正则 | 国际/评论栏目，无 RSS |
| 环球时报（huanqiu.com） | 右栏 | HTTP + 正则 | SSR `<textarea>` 注水，含转引来源 |
| CGTN（cgtn.com） | 右栏 | HTTP + 正则 | 英文评论栏目，og:title/description |

### 待接入的源（需境外 VPS 验证）

左栏外媒涉华源在国内 GFW 不可达，必须在境外 VPS 上运行爬虫才能抓取：

- BBC 中文、RFI 法广、DW 德国之声
- Reuters / AP / NYT / WSJ / The Economist / The Guardian
- Reddit r/China、r/sino（二次搬运）

### 运行爬虫

```bash
# 只抓不调 LLM（调试抓取层）
python scraper/main.py --no-llm

# 跑今天的数据（需要 LLM key）
python scraper/main.py

# 跑指定日期
python scraper/main.py --date 2026-07-19

# 限定源
python scraper/main.py --sources guancha,huanqiu

# 每源最多抓 10 条候选
python scraper/main.py --limit 10

# 把输出同步到 site/src/content/daily/
python scraper/main.py --sync-site

# 详细日志
python scraper/main.py -v
```

### LLM 配置（环境变量）

爬虫调 LLM 需配置以下环境变量：

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `OPENAI_API_KEY` | 是 | — | API 密钥 |
| `OPENAI_BASE_URL` | 否 | `https://api.openai.com/v1` | 换 DeepSeek: `https://api.deepseek.com/v1`；通义: `https://dashscope.aliyuncs.com/compatible-mode/v1`；Kimi: `https://api.moonshot.cn/v1` |
| `LLM_MODEL` | 否 | `gpt-4o-mini` | 默认（便宜）模型，用于 classify/validate |
| `LLM_MODEL_STRONG` | 否 | 同 `LLM_MODEL` | 强模型，用于 process（摘要+金句） |
| `BLACKLIST_KEYWORDS` | 否 | 空 | 逗号分隔的关键词黑名单，命中即拦截 |

示例：

```bash
export OPENAI_API_KEY=sk-xxxxxxxx
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export LLM_MODEL=deepseek-chat
export LLM_MODEL_STRONG=deepseek-chat
export BLACKLIST_KEYWORDS="敏感词1,敏感词2"
python scraper/main.py --sync-site
```

### LLM 流水线

每篇文章经过 5 个阶段：

```
1. 黑名单预扫描（title + body 前 2000 字）
   └─ 命中 → drafts 池，结束
2. classify（便宜模型）—— 是否构成对另一方的嘲讽/批评
   └─ 不通过 → drafts 池，结束
3. process（强模型）—— 摘要 + 主题标签 + 荒诞指数 + 金句
4. 黑名单二次扫描（摘要 + 金句）
   └─ 命中 → drafts 池，结束
5. validate（便宜模型）—— 摘要是否歪曲原意
   └─ 歪曲 → drafts 池，结束
```

通过所有阶段的文章写入 `scraper/output/daily/{date}.json`，可用 `--sync-site` 同步到站点。

### 主题标签固定枚举

`政治 / 经济 / 社会 / 科技 / 军事 / 外交 / 文化 / 环境 / 其他`

固定枚举便于归档检索，避免 LLM 自由发挥导致标签碎片化。

### 荒诞指数（1-10）

基于原文**既有的**嘲讽力度，不是让 LLM 加嘲讽：

- **1-3**：温和批评、客观陈述带负面立场
- **4-6**：明确嘲讽、修辞手法（反讽、夸张）
- **7-8**：辛辣嘲讽、直接点名批评、扣帽子
- **9-10**：极端讽刺、激烈攻击

---

## 站点架构

### 客户端无限滚动

站点从 SSR 渲染改为客户端动态加载：

1. `index.astro` 输出空壳 HTML（左右栏容器 + 哨兵元素 + loader）
2. `infinite-scroll.js` fetch `/articles.json`，按 10 条/批 append 到左右栏
3. `IntersectionObserver` 监听哨兵，触底加载下一批
4. 卡片用模板字符串渲染，含入场动画（`news-card--entering` → `news-card--visible`）

每批 10 条按 `side` 字段分发到对应栏，左右交替排列保证视觉平衡。

### 分享功能

每张卡片右下角有"分享"按钮：

1. 点击 → `share.js` 用 Canvas 绘制该卡片的分享图（750px 宽，含国旗/来源/标题/摘要/金句/荒诞指数/原文链接/水印）
2. Canvas 转 dataURL 放入 `<img>` 显示在弹层
3. **微信内**：长按图片 → "发送给朋友" / "保存到手机"
4. **浏览器**：点"下载图片"按钮，手动发到微信

> 技术现实：微信未开放"网页直接发图到聊天"给普通网站（需公众号 + JSSDK + 备案域名）。本站境外部署走不通，改用"生成长按图片"方案。弹层里必须用 `<img>` 而非 `<canvas>`（微信只能长按 img 触发菜单）。

### 回到顶部

滚动超过 400px 后，页面左下、右下各出现一个圆形按钮，点击平滑回顶。移动端自动缩小。

---

## 数据格式

### `articles.json` schema

```typescript
{
  items: Array<{
    side: "left" | "right";          // 栏位
    source: string;                   // 媒体名或社交账号
    source_country: string;           // ISO 国家代码：cn/uk/us/de/fr...
    source_url: string;               // 原文链接
    topic: "政治" | "经济" | "社会" | "科技" | "军事" | "外交" | "文化" | "环境" | "其他";
    title_cn: string;                 // 中文标题
    summary_cn: string;               // 中文摘要（2-3 句）
    quote_cn?: string;                // 金句（可选，≤60 字）
    absurdity: number;                // 荒诞指数 1-10
  }>
}
```

数据文件有两份（内容相同）：
- `site/src/content/daily/articles.json` —— Astro content collection 校验用
- `site/public/articles.json` —— 客户端 fetch 用（部署时随构建输出）

### 国旗 emoji 映射

`infinite-scroll.js` 和 `share.js` 内置映射：`cn 🇨🇳 / uk 🇬🇧 / us 🇺🇸 / de 🇩🇪 / fr 🇫🇷 / jp 🇯🇵 / ru 🇷🇺 / eu 🇪🇺 / in 🇮🇳 / ir 🇮🇷 / kr 🇰🇷 / au 🇦🇺 / ca 🇨🇦 / hk 🇭🇰`，未知代码回退为 🌐。

---

## 部署

### GitHub 仓库

```
git@github.com:wenwenwen888/BlackManuscript.git
```

分支 `main`，push 后 EdgeOne 自动触发构建。

### 腾讯云 EdgeOne Pages 配置

| 配置项 | 值 |
|---|---|
| 框架预设 | Astro |
| 构建命令 | `cd site && npm install && npm run build` |
| 输出目录 | `site/dist` |
| 部署分支 | `main` |
| Node.js 版本 | 18.x 或 20.x |
| 加速区域 | 全球 / 海外（非中国大陆，免备案） |
| 环境变量 | 无需（纯静态构建） |

> **关键**：Astro 项目在 `site/` 子目录，构建命令必须先 `cd site`，否则找不到 `package.json`。

部署成功后会拿到默认预览域名（形如 `xxx.edgeone.pages.dev`），可直接公网访问，无需备案。自定义域名仅当加速区域含中国大陆时才需要备案。

### 自动部署

配置完成后，每次 `git push origin main`，EdgeOne 自动拉取重新构建部署，无需手动触发。

---

## 安全与合规

### 内容安全阀

- **三段式 LLM pipeline**：classify 门控 → process 处理 → validate 校验
- **关键词黑名单**：环境变量 `BLACKLIST_KEYWORDS` 配置，预扫描 + 生成内容二次扫描
- **drafts 池**：所有被拦截内容写入 `scraper/output/drafts/`，待人工复核，不发布
- **荒诞指数基于原文**：评分反映原文既有嘲讽力度，不让 LLM 加戏

### 版权与立场

- **仅摘要 + 原文链接**，不全文搬运
- **页脚固定免责声明**：明示"内容聚合，立场归属原媒体，不代表本站观点"
- **每张卡片强制来源标注**：媒体名 + 国旗 + 日期 + 原文链接 + 主题标签

### 运营匿名性

- 域名境外注册，不备案
- 托管在 EdgeOne Pages（免主体信息）
- 爬虫运行在境外 VPS
- Git 仓库私有

> 注意：真正的匿名需要更完整的 opsec（域名注册、VPS 计费、账号注册都留痕），本项目仅在架构层面降低可追溯性。

---

## 项目状态与路线图

### 当前状态（2026-07）

- ✅ Astro 站点可跑，客户端无限滚动 + 分享 + 回到顶部
- ✅ scraper 模块完整实现（3 个右栏源：观察者网/环球时报/CGTN）
- ✅ LLM 三段式 pipeline + 安全阀
- ✅ 演示数据 ~100 条（`generate_articles.py` 生成）
- ✅ 已部署 GitHub，准备上 EdgeOne Pages

### 待办

- [ ] **左栏源接入**：BBC/RFI/DW/Reuters/NYT/WSJ/Economist，待境外 VPS 验证
- [ ] **scraper 输出对接前端**：当前 scraper 输出旧格式 `{date, left, right}`，前端已改为扁平 `{items}`，需适配
- [ ] **去重逻辑**：同一事件多源报道合并/择优
- [ ] **cron 调度**：境外 VPS 定时跑爬虫
- [ ] **监控告警**：爬虫失败/站点过期检测
- [ ] **解析器健康检查**：源站点改版导致解析失效的监控
- [ ] **历史归档检索**：按日期/主题/来源搜索（archive 路由目前是遗留）
- [ ] **清理死代码**：`HeadToHead.astro` 组件 + `.head-to-head` CSS + `VsColumn.astro` 遗留

---

## 常见问题

### Q: 站点打开是空白的？

A: 检查 `site/public/articles.json` 是否存在且格式正确。客户端 fetch 失败会显示"加载失败，请刷新"。打开浏览器控制台看具体错误。

### Q: 分享图片里的国旗显示成字母代码（如 CN）？

A: Windows 系统字体不支持国旗 emoji 的字形渲染（已知限制）。Mac/iOS/Android 正常显示国旗图案。Canvas 绘制依赖系统字体，无法绕过。

### Q: 爬虫报 "OPENAI_API_KEY 未设置"？

A: 用 `--no-llm` 调试抓取层，或设置环境变量后再跑。见 [LLM 配置](#llm-配置环境变量)。

### Q: EdgeOne 构建失败？

A: 最常见原因是构建命令没 `cd site`，或输出目录写成了 `dist` 而不是 `site/dist`。在控制台"构建 & 部署"详情页看构建日志。

### Q: 演示数据的链接点开是 example.com？

A: `generate_articles.py` 生成的演示数据 URL 是占位符，仅供样式验证。真实数据需跑爬虫（`python scraper/main.py --sync-site`）替换。

---

## 相关文档

- [PLAN.md](./PLAN.md) —— 项目总规划
- [prompts/README.md](./prompts/README.md) —— LLM prompt 设计
- [scraper/README.md](./scraper/README.md) —— 爬虫架构与运行
- [site/README.md](./site/README.md) —— 站点运行细节
- [tools/probe/REPORT.md](./tools/probe/REPORT.md) —— 抓取源可行性探查报告
