# 嘲讽日报 - 爬虫

每日抓取"外媒涉华"+"中媒涉外"新闻，用 LLM 分类/摘要/校验，输出每日 JSON 供 Astro 站点渲染。

## 架构

```
scraper/
├── README.md              本文档
├── main.py                CLI 入口：跑一天的数据
├── config.py              全局配置（LLM key、源开关、输出路径）
├── sources/               源适配层，每个源一个文件，统一接口
│   ├── base.py            Source 抽象基类 + Article 数据类
│   ├── guancha.py         观察者网
│   ├── huanqiu.py         环球时报
│   ├── cgtn.py            CGTN
│   └── (待补)             参考消息、BBC 中文、Reuters 等
├── fetcher.py             HTTP 抓取（UA、超时、重试）
├── llm/
│   ├── client.py          OpenAI 兼容客户端（支持 OpenAI/DeepSeek/Claude 适配）
│   ├── pipeline.py        classify → process → validate 串联
│   └── safety.py          关键词黑名单 + drafts 池
├── utils/
│   └── json_io.py         每日 JSON 读写（对接 Astro content collection schema）
└── output/                运行产物
    ├── daily/             正式发布的每日 JSON（拷到 site/src/content/daily/）
    └── drafts/            被 LLM/安全阀拦截的内容，待人工复核
```

## 运行

```bash
# 设置环境变量（LLM API key）
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # 可选，换 DeepSeek 等兼容 API
export LLM_MODEL=deepseek-chat                        # 可选，默认 gpt-4o-mini

# 跑今天的数据
python scraper/main.py

# 跑指定日期
python scraper/main.py --date 2026-07-19

# 只抓不调 LLM（调试用）
python scraper/main.py --no-llm

# 限定源
python scraper/main.py --sources guancha,huanqiu
```

## 数据流

```
每个启用的源
  -> Source.list_articles()        返回候选文章列表（标题+URL+时间）
  -> Source.extract_article(url)   深入抓正文+元数据
  -> LLM.classify()                判断是否嘲讽对方，否→丢弃
  -> LLM.process()                 摘要+标签+荒诞指数+金句
  -> LLM.validate()                摘要是否歪曲原意，是→drafts
  -> 汇总写入 output/daily/{date}.json
```

## 部署位置

境外 VPS（Contabo/Hetzner 等），加 cron 每日定时跑。
dev 机国内网络只能跑右栏源（中媒涉外），左栏源（外媒涉华）必须 VPS。

## 与 Astro 站点的衔接

爬虫产物 `output/daily/{date}.json` 拷贝到 `site/src/content/daily/` 即可被 Astro content collection 读取。可以用符号链接或脚本同步。

## 设计要点

1. **源适配统一接口**：所有源继承 `Source` 基类，实现 `list_articles()` 和 `extract_article()` 两个方法。新增源只改一个文件。
2. **fetcher 单独抽出**：UA、超时、重试、限速统一管理，方便切代理或换 headless。
3. **LLM 客户端兼容 OpenAI API**：用 `openai` Python SDK，通过 `base_url` 切到 DeepSeek/通义/Kimi 等。Claude 用 Anthropic SDK 单独适配（或走 OpenAI 兼容层）。
4. **安全阀在 pipeline 里**：classify 失败、validate 失败、关键词命中，统一进 `drafts/` 不发布。
5. **可重入**：同一天可重复跑，覆盖输出；中断可断点续跑（草稿池保留）。
