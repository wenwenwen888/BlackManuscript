"""美联社 China hub（左栏：外媒涉华，英文）。"""
from __future__ import annotations

import re
import logging
from html import unescape

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URL = "https://apnews.com/hub/china"


class ApSource(Source):
    name = "Associated Press"
    side = "left"
    source_country = "us"

    def list_articles(self, limit: int = 20) -> list[Article]:
        html = fetch(LIST_URL)
        links = list(dict.fromkeys(
            re.findall(r'href="(https://apnews\.com/article/[^"#?]+)"', html)
        ))
        articles: list[Article] = []
        for url in links:
            slug = url.rsplit("/", 1)[-1]
            # 粗标题：去掉尾部 hash
            title = re.sub(r"-[a-f0-9]{10,}$", "", slug).replace("-", " ")
            articles.append(self.make_article(url=url, title=title))
            if len(articles) >= limit:
                break
        logger.info("AP list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("AP extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        article.body_lang = "en"

        m = re.search(r'property="og:title" content="([^"]+)"', html, re.I)
        if m:
            title = unescape(m.group(1)).strip()
            title = re.sub(r"\s*\|\s*AP\s*.*$", "", title, flags=re.I).strip()
            if title:
                article.title = title

        m = re.search(
            r'property="article:published_time" content="([^"]+)"',
            html,
            re.I,
        )
        if m:
            article.published = m.group(1)[:10]
        else:
            m = re.search(r'data-published="(\d{4}-\d{2}-\d{2})', html)
            if m:
                article.published = m.group(1)

        body_m = re.search(
            r'class="[^"]*RichTextStoryBody[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if not body_m:
            body_m = re.search(
                r'data-key="article"[^>]*>(.*?)</div>',
                html,
                re.DOTALL,
            )
        if body_m:
            text = unescape(re.sub(r"<[^>]+>", "", body_m.group(1)))
            text = re.sub(r"\s+", " ", text).strip()
            # 去掉 AP 尾部版权
            text = re.sub(r"Copyright\s+\d{4}.*$", "", text).strip()
            article.body = text

        if len(article.body) < 80:
            m = re.search(r'property="og:description" content="([^"]*)"', html, re.I)
            if m:
                article.body = (article.body + " " + unescape(m.group(1))).strip()

        return article
