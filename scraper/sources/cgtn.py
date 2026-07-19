"""CGTN 源（右栏：中媒涉外，英文）。

探查结论：
- 列表入口：https://www.cgtn.com/opinions
- 列表数据：文章 URL 直接在 HTML 链接里 SSR（不是 textarea）
- 详情 URL：https://news.cgtn.com/news/YYYY-MM-DD/{slug}-{id}/p.html
- 元数据：og:title / og:description
- 正文容器：class="text en"（多 class，含语言后缀）
"""
from __future__ import annotations

import re
import logging

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URL = "https://www.cgtn.com/opinions"


class CgtnSource(Source):
    name = "CGTN"
    side = "right"
    source_country = "cn"

    def list_articles(self, limit: int = 20) -> list[Article]:
        html = fetch(LIST_URL)
        # 文章 URL 规律
        pattern = r'href="(https://news\.cgtn\.com/news/\d{4}-\d{2}-\d{2}/[^"]+-[A-Za-z0-9]+/p\.html)"'
        seen = set()
        articles: list[Article] = []
        for m in re.finditer(pattern, html):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            # 从 URL 取日期
            date_m = re.search(r"/(\d{4}-\d{2}-\d{2})/", url)
            published = date_m.group(1) if date_m else ""
            # 从 slug 提取一个粗略标题（用横线分隔的英文短语）
            slug_m = re.search(r"/([^/]+)-[A-Za-z0-9]+/p\.html", url)
            slug_title = ""
            if slug_m:
                # 把 "China-s-air-conditioners-cool-Europe-s-hotheads" -> 原样保留，详情页再取真 title
                slug_title = slug_m.group(1).replace("-", " ")
            articles.append(self.make_article(url=url, title=slug_title, published=published))
            if len(articles) >= limit:
                break
        logger.info("CGTN list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("CGTN extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        # 用 og:title 覆盖 slug 标题
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
        if m:
            # 去掉 " - CGTN" 后缀
            title = re.sub(r"\s*[-–]\s*CGTN\s*$", "", m.group(1)).strip()
            if title:
                article.title = title

        # 正文：class="text en" / "text zh" 等
        m = re.search(r'class="text\s+(en|zh|fr|es)"[^>]*>(.*?)</div>\s*<div', html, re.DOTALL)
        if m:
            article.body_lang = m.group(1)
            raw = m.group(2)
            text = re.sub(r"<[^>]+>", "", raw)
            text = re.sub(r"\s+", " ", text).strip()
            article.body = text
        else:
            # 备选：所有 class 含 "text" 的 div 取最长的
            best_text = ""
            for m in re.finditer(r'class="[^"]*\btext\b[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL):
                raw = m.group(1)
                t = re.sub(r"<[^>]+>", "", raw)
                t = re.sub(r"\s+", " ", t).strip()
                if len(t) > len(best_text):
                    best_text = t
            article.body = best_text
            article.body_lang = "en"  # CGTN opinions 默认英文

        # og:description 作为补充摘要线索（若正文短，至少有描述）
        if len(article.body) < 100:
            m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)
            if m:
                article.body = (article.body + " " + m.group(1)).strip()

        return article
