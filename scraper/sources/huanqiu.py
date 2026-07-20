"""环球时报源（右栏：中媒涉外）。

探查结论：
- 列表入口：https://world.huanqiu.com/
- 列表数据：嵌在 <textarea class="item-aid"> 等 SSR 注水里
- 详情 URL：https://{频道}.huanqiu.com/article/{aid}
- 详情正文：嵌在 <textarea class="article-content">（含 HTML 标签）
- 元数据：article-title / article-source-name（带链接，常转引）/ article-time（毫秒戳）
"""
from __future__ import annotations

import re
import time
import logging
from urllib.parse import urljoin

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URLS = [
    "https://world.huanqiu.com/",          # 国际频道
    "https://opinion.huanqiu.com/",        # 社评/国际锐评
    "https://ent.huanqiu.com/",            # 文娱/电影补源
]


class HuanqiuSource(Source):
    name = "环球时报"
    side = "right"
    source_country = "cn"

    def list_articles(self, limit: int = 20) -> list[Article]:
        seen = set()
        articles: list[Article] = []
        # 各频道均分配额，避免国际栏吃光额度导致文娱/电影为 0
        per = max(3, (limit + len(LIST_URLS) - 1) // len(LIST_URLS))
        for list_url in LIST_URLS:
            got = 0
            try:
                html = fetch(list_url)
            except Exception as e:
                logger.warning("Huanqiu list %s failed: %s", list_url, e)
                continue

            # SSR 注水数据：每条 item 含 aid / title / time
            items = re.findall(
                r'<div class="item">\s*'
                r'<textarea class="item-aid">(.*?)</textarea>\s*'
                r'(?:<textarea class="item-addltype">(.*?)</textarea>\s*)?'
                r'(?:<textarea class="item-cover">.*?</textarea>\s*)?'
                r'<textarea class="item-title">(.*?)</textarea>\s*'
                r'(?:<textarea class="item-cnf-host">(.*?)</textarea>\s*)?'
                r'(?:<textarea class="item-time">(.*?)</textarea>\s*)?',
                html, re.DOTALL,
            )
            for aid, atype, title, host, ts in items:
                # 只取 article 类型，跳过 gallery/专题
                if atype and atype.strip() != "article":
                    continue
                title_clean = re.sub(r"\s+", "", title).strip()
                if not title_clean or len(title_clean) < 5:
                    continue
                host_clean = host.strip() if host else "world.huanqiu.com"
                url = f"https://{host_clean}/article/{aid.strip()}"
                if url in seen:
                    continue
                seen.add(url)
                # 毫秒时间戳 -> YYYY-MM-DD
                published = ""
                if ts.strip():
                    try:
                        published = time.strftime("%Y-%m-%d", time.localtime(int(ts) / 1000))
                    except (ValueError, OSError):
                        pass
                articles.append(self.make_article(url=url, title=title_clean, published=published))
                got += 1
                if got >= per or len(articles) >= limit:
                    break
            if len(articles) >= limit:
                break

        logger.info("Huanqiu list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("Huanqiu extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        # 正文：textarea class="article-content" 含 HTML 标签
        m = re.search(r'<textarea class="article-content">(.*?)</textarea>', html, re.DOTALL)
        if m:
            raw = m.group(1)
            text = re.sub(r"<[^>]+>", "", raw)
            text = re.sub(r"\s+", " ", text).strip()
            article.body = text

        # 真实来源（环球常转引其他媒体）
        m = re.search(r'<textarea class="article-source-name">(.*?)</textarea>', html, re.DOTALL)
        if m:
            src_raw = m.group(1)
            # 提取 <a> 里文字，或纯文本
            src_text = re.sub(r"<[^>]+>", "", src_raw).strip()
            if src_text:
                # 改写 source 字段，保留"环球时报（转引 XXX）"形式
                if src_text and src_text != self.name:
                    article.source = f"环球时报（转引{src_text}）"
                # 也尝试提取原文链接
                link_m = re.search(r'href="([^"]+)"', src_raw)
                if link_m and link_m.group(1).startswith("http"):
                    article.url = link_m.group(1)

        # 时间戳
        m = re.search(r'<textarea class="article-time">(\d+)</textarea>', html)
        if m and not article.published:
            try:
                article.published = time.strftime("%Y-%m-%d", time.localtime(int(m.group(1)) / 1000))
            except (ValueError, OSError):
                pass

        article.body_lang = "zh"
        return article
