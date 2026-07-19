# 嘲讽日报 - 站点

Astro 静态站点骨架。

## 目录结构

```
site/
├── astro.config.mjs            Astro 配置（静态输出）
├── package.json
├── tsconfig.json
├── src/
│   ├── content/
│   │   ├── config.ts           每日数据 schema（content collection）
│   │   └── daily/
│   │       └── 2026-07-19.json 示例数据（基于真实抓取构造）
│   ├── components/
│   │   ├── Flag.astro          ISO 国家代码 -> emoji 国旗
│   │   ├── SourceBar.astro     来源条（国旗+媒体+日期+原文链接）
│   │   ├── NewsCard.astro      文章卡片（来源条+标题+摘要+标签+荒诞指数）
│   │   ├── VsColumn.astro      左/右栏容器
│   │   └── HeadToHead.astro    今日对擂高亮块
│   ├── layouts/
│   │   └── BaseLayout.astro    全站布局 + 免责声明页脚
│   ├── pages/
│   │   ├── index.astro         首页（最新一期）
│   │   └── archive/
│   │       ├── index.astro     历史归档列表
│   │       └── [date].astro    单日详情动态路由
│   └── styles/
│       └── global.css          全局样式（对擂分栏、卡片、响应式）
└── public/                     静态资源
```

## 运行

> **环境要求：Node.js ≥ 18.14.1**
>
> 已安装 Node 20.18.1 到 `C:\Program Files\nodejs\`。
> 新开 PowerShell 后 `node --version` 应直接显示 `v20.18.1`。
> 如果旧 shell 还指向 Node 14，刷新 PATH：
> ```powershell
> $env:Path = "C:\Program Files\nodejs;$env:Path"
> ```

```bash
cd site
npm install      # 首次需要，依赖已装过可跳过
npm run dev      # 本地预览 http://localhost:4321
npm run build    # 构建到 dist/
npm run preview  # 预览构建产物
```

后台启动 dev server（不占用当前终端）：
```powershell
Start-Process -FilePath "npx.cmd" -ArgumentList "astro","dev","--host" `
  -WorkingDirectory "G:\WorkSpaces\BlackManuscript\site" `
  -RedirectStandardOutput "dev-server.log" -RedirectStandardError "dev-server.log.err" `
  -WindowStyle Hidden
```
停止：`Get-Process node | Stop-Process`

## 数据来源

`src/content/daily/{YYYY-MM-DD}.json` 由上层 `tools/` 下的爬虫脚本生成。
当前 `2026-07-19.json` 是**示例数据**，基于探查阶段真实抓取到的文章构造，
用于验证渲染。爬虫就绪后会自动覆盖。

## 部署

构建产物在 `dist/`，部署到 Cloudflare Pages：
1. 在 Cloudflare Pages 新建项目，连接 Git 仓库
2. 构建命令 `npm run build`，输出目录 `site/dist`（或调整 root directory）
3. 自动部署

或推送到 GitHub 后用 GitHub Actions 自动构建部署。
