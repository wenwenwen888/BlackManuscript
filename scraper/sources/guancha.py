"""观察者网源（右栏：中媒涉外）。

探查结论（见 tools/probe/REPORT.md）：
- 列表入口：https://www.guancha.cn/internation
- 正文 URL：/YYYY_MM_DD_{aid}.shtml
- 正文选择器：class="content all-txt"（多 class）
- 元数据：来源（"来源：观察者网"）、日期（YYYY-MM-DD）、作者
- 无 RSS
"""
from __future__ import annotations

import re
import logging
from urllib.parse import urljoin

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URL = "https://www.guancha.cn/internation"


class GuanchaSource(Source):
    name = "观察者网"
    side = "right"
    source_country = "cn"

    def list_articles(self, limit: int = 20) -> list[Article]:
        html = fetch(LIST_URL)
        # 文章 URL 规律：/internation/YYYY_MM_DD_{aid}.shtml
        pattern = r'href="(/(?:internation|politics|military-affairs)/\d{4}_\d{2}_\d{2}_\d+\.shtml)"[^>]*>([^<]+)</a>'
        seen = set()
        articles: list[Article] = []
        for m in re.finditer(pattern, html):
            path, title = m.group(1), m.group(2).strip()
            if not title or len(title) < 5:
                continue
            # 过滤掉导航/栏目链接
            if any(k in title for k in ("首页", "更多", "评论", "下载", "登录")):
                continue
            url = urljoin("https://www.guancha.cn", path)
            if url in seen:
                continue
            seen.add(url)
            # 从 URL 提取日期
            date_match = re.search(r"(\d{4})_(\d{2})_(\d{2})", path)
            published = "-".join(date_match.groups()) if date_match else ""
            articles.append(self.make_article(url=url, title=title, published=published))
            if len(articles) >= limit:
                break
        logger.info("Guancha list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("Guancha extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        # 正文：class="content all-txt" 多 class
        m = re.search(
            r'class="[^"]*\ball-txt\b[^"]*"[^>]*>(.*?)</div>\s*<div\s+class="content-bottom-ad',
            html, re.DOTALL,
        )
        if m:
            raw = m.group(1)
            # 去 HTML 标签
            text = re.sub(r"<[^>]+>", "", raw)
            text = re.sub(r"\s+", " ", text).strip()
            # 清洗尾部声明
            text = re.sub(r"本文系观察者网独家稿件.*$", "", text).strip()
            text = re.sub(r"未经授权.*?转载.*?。", "", text).strip()
            article.body = text

        # 日期补全（若 list 阶段没拿到）
        if not article.published:
            m = re.search(r"\d{4}-\d{2}-\d{2}", html)
            if m:
                article.published = m.group(0)

        article.body_lang = "zh"
        return article
