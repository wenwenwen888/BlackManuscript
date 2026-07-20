# 嘲讽日报 - 站点

Astro 静态站点：空壳 SSR + 客户端无限滚动加载 `articles.json`。

## 目录结构

```
site/
├── astro.config.mjs
├── package.json
├── scripts/
│   └── copy-articles.mjs       构建/开发前：content → public
├── src/
│   ├── content/
│   │   ├── config.ts           articles schema（含可选 head_to_head）
│   │   └── daily/
│   │       └── articles.json   【唯一数据源】
│   ├── layouts/
│   │   └── BaseLayout.astro
│   ├── pages/
│   │   └── index.astro         首页壳层 + 主题 chip + 今日对擂容器
│   └── styles/
│       └── global.css
└── public/
    ├── articles.json           客户端 fetch 用（由 copy-articles 同步）
    ├── infinite-scroll.js
    └── share.js
```

## 数据约定

- **主文件**：`src/content/daily/articles.json`
- **副本**：`public/articles.json`（`npm run dev/build` 前自动复制）
- 爬虫：`python scraper/main.py --sync-site` 会先写 content，再拷 public

主题枚举与 `prompts/process.py` 对齐：
`政治 / 经济 / 社会 / 科技 / 军事 / 外交 / 文化 / 环境 / 电影 / 娱乐 / 其他`

## 运行

> Node.js ≥ 18.14.1（推荐 20.x）

```bash
cd site
npm install
npm run dev      # http://localhost:4321
npm run build    # → dist/
npm run preview
```

## 部署

- GitHub Actions：见仓库根 `.github/workflows/deploy.yml`（`prebuild` 会同步 articles）
- EdgeOne Pages：构建命令 `cd site && npm install && npm run build`，输出 `site/dist`
