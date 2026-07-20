"""德国之声中文源（左栏：外媒涉华）。"""
from __future__ import annotations

import re
import logging
from html import unescape
from urllib.parse import urljoin, quote

from fetcher import fetch
from sources.base import Source, Article

logger = logging.getLogger(__name__)

LIST_URL = "https://www.dw.com/zh/"
# 中国专题（path 用百分号编码，避免部分环境下 URL 编码问题）
TOPIC_URL = "https://www.dw.com/zh/" + quote("中国") + "/s-68398488"


class DwSource(Source):
    name = "德国之声"
    side = "left"
    source_country = "de"

    def list_articles(self, limit: int = 20) -> list[Article]:
        articles: list[Article] = []
        seen: set[str] = set()
        for list_url in (TOPIC_URL, LIST_URL):
            try:
                html = fetch(list_url)
            except Exception as e:
                logger.warning("DW list fetch failed %s: %s", list_url, e)
                continue
            for m in re.finditer(r'href="(/zh/[^"#?]+/a-\d+)"', html):
                path = m.group(1)
                # 跳过法律/无障碍等非新闻页
                if any(x in path for x in ("legal-notice", "accessibility", "gdpr", "data-protection")):
                    continue
                url = urljoin("https://www.dw.com", path)
                if url in seen:
                    continue
                seen.add(url)
                slug = path.split("/")[-2] if "/" in path else path
                articles.append(self.make_article(url=url, title=unescape(slug)))
                if len(articles) >= limit:
                    break
            if len(articles) >= limit:
                break
        logger.info("DW list: %d candidates", len(articles))
        return articles

    def extract_article(self, article: Article) -> Article:
        try:
            html = fetch(article.url)
        except Exception as e:
            logger.warning("DW extract failed %s: %s", article.url, e)
            article.body = ""
            return article

        article.body_lang = "zh"

        # 标题：title 标签 / h1
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            title = unescape(m.group(1)).strip()
            title = re.sub(r"\s*[|\-–]\s*DW\s*.*$", "", title).strip()
            if title:
                article.title = title
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.DOTALL)
        if m:
            h1 = unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
            if h1:
                article.title = h1

        # 日期
        m = re.search(r'(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}', html)
        if m:
            article.published = m.group(1)
        else:
            m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
            if m:
                article.published = m.group(1)

        # 正文：DW 新站 class 为哈希名，取足够长的段落拼接
        paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.I | re.DOTALL)
        texts: list[str] = []
        for raw in paras:
            t = unescape(re.sub(r"<[^>]+>", "", raw))
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) < 40:
                continue
            # 过滤导航/页脚噪声
            if any(k in t for k in ("跳转至", "Cookie", "接受全部", "法律信息", "无障碍声明")):
                continue
            texts.append(t)
        article.body = " ".join(texts)

        if len(article.body) < 80:
            # 备选：rich-text 容器
            m = re.search(
                r'class="[^"]*rich-text[^"]*"[^>]*>(.*?)</div>',
                html,
                re.I | re.DOTALL,
            )
            if m:
                t = unescape(re.sub(r"<[^>]+>", "", m.group(1)))
                t = re.sub(r"\s+", " ", t).strip()
                if len(t) > len(article.body):
                    article.body = t

        return article
