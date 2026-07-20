# 嘲讽日报 - 爬虫

每日抓取中媒涉外（及后续外媒涉华）新闻，用 LLM 分类/摘要/校验，输出 JSON 供 Astro 站点渲染。

推荐工作流：**本地跑爬虫 → `--sync-site` → git push → 静态托管自动构建**。

```bash
python scraper/main.py --sync-site --min-total 50
```

无 `OPENAI_API_KEY` 时自动用启发式门控（剔假链 / 赞叹稿）；有 key 则走 LLM 三段式。

## 架构

```
scraper/
├── main.py                CLI：日更 / 健康检查 / sync-site
├── config.py              源注册表 + 路径
├── sources/               源适配（统一 list + extract）
├── fetcher.py             HTTP（UA/超时/重试/限速）
├── llm/
│   ├── client.py          OpenAI 兼容（urllib）
│   ├── pipeline.py        blacklist → classify → process → validate
│   └── safety.py          黑名单 + drafts
├── utils/
│   └── json_io.py         组装 / 去重 / 截断 / 今日对擂
└── output/
    ├── daily/             正式发布归档
    └── drafts/            被拦截内容
```

## 运行

```bash
# LLM key（示例：DeepSeek）
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export LLM_MODEL=deepseek-chat

# 跑今天 + 同步到站点
python scraper/main.py --sync-site

# 只抓不调 LLM
python scraper/main.py --no-llm

# 源健康检查（列表+正文取样，不调 LLM）
python scraper/main.py --health-check

# 每边最多发布 12 条（默认，按荒诞指数截断）
python scraper/main.py --max-per-side 12 --sync-site
```

## 数据流

```
源 list_articles → extract_article
  → 黑名单 → classify → process → validate（失败硬拦截进 drafts）
  → 去重（同 URL / 标题前缀，保留荒诞指数更高）
  → 每边 rank_and_limit
  → detect_head_to_heads（同 topic + 同镜像议题才配对，不强凑）
  → output/daily/{date}.json
  → --sync-site → site/src/content/daily/articles.json（主）
                 → site/public/articles.json（副本）
```

## 设计要点

1. **源适配统一接口**：新增源只加一个 `sources/*.py`。
2. **validate 硬失败**：LLM 校验调用出错不放行。
3. **今日对擂稀有**：同 topic + 同镜像议题（如学术造假↔学术造假）+ 双边荒诞达标才写入 `head_to_head`。
4. **本地同步上线**：不做境外 cron 时，人工/本地跑完 `--sync-site` 后 push 即可。
