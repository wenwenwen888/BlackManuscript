"""BBC 中文源（左栏：外媒涉华）。"""
from __future__ import annotations

import re
import logging
from html import unescape

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URL = "https://www.bbc.com/zhongwen/simp"


class BbcSource(Source):
    name = "BBC 中文"
    side = "left"
    source_country = "uk"

    def list_articles(self, limit: int = 20) -> list[Article]:
        html = fetch(LIST_URL)
        # 新版 URL：/zhongwen/articles/{id}/simp
        ids = list(dict.fromkeys(re.findall(r"/zhongwen/articles/([a-z0-9]+)/simp", html)))
        articles: list[Article] = []
        for aid in ids:
            url = f"https://www.bbc.com/zhongwen/articles/{aid}/simp"
            articles.append(self.make_article(url=url, title=aid))
            if len(articles) >= limit:
                break
        logger.info("BBC list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("BBC extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        article.body_lang = "zh"

        m = re.search(r'property="og:title" content="([^"]+)"', html, re.I)
        if m:
            title = unescape(m.group(1)).strip()
            title = re.sub(r"\s*[-–]\s*BBC\s*.*$", "", title).strip()
            if title:
                article.title = title

        m = re.search(r'property="article:published_time" content="([^"]+)"', html, re.I)
        if m:
            article.published = m.group(1)[:10]
        elif not article.published:
            m = re.search(r'datetime="(\d{4}-\d{2}-\d{2})', html)
            if m:
                article.published = m.group(1)

        # 正文：多个 text-block 段落
        blocks = re.findall(
            r'data-component="text-block"[^>]*>.*?<p[^>]*>(.*?)</p>',
            html,
            re.DOTALL,
        )
        if not blocks:
            blocks = re.findall(r'<p[^>]*dir="ltr"[^>]*>(.*?)</p>', html, re.DOTALL)
        texts = []
        for raw in blocks:
            t = unescape(re.sub(r"<[^>]+>", "", raw))
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) >= 20:
                texts.append(t)
        article.body = " ".join(texts)

        if len(article.body) < 80:
            m = re.search(r'property="og:description" content="([^"]*)"', html, re.I)
            if m:
                article.body = (article.body + " " + unescape(m.group(1))).strip()

        return article
