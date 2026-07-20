"""每日 JSON 读写工具：对接 Astro content collection schema。

输出格式见 site/src/content/config.ts 的 daily schema。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from sources.base import Article

# 标题模糊去重时忽略的噪声字
_TITLE_NOISE = set("的了在是与和及对之被将把从为")


def build_daily_dict(
    left: list[Article],
    right: list[Article],
    *,
    head_to_head: Optional[dict | list] = None,
    date: str | None = None,
) -> dict:
    """把处理后的 Article 列表组装成前端 articles.json 格式。

    输出 {date?, items, head_to_head?}，对接 site/src/content/config.ts schema。
    left/right 合并成扁平 items：先按 published 降序，再左右交替。
    若有今日对擂（1~5 组），对擂卡片从 items 中移除，避免重复展示。
    """
    pairs: list[dict] = []
    if isinstance(head_to_head, list):
        pairs = [p for p in head_to_head if p]
    elif isinstance(head_to_head, dict):
        pairs = [head_to_head]

    featured_urls: set[str] = set()
    for pair in pairs:
        for side_key in ("left", "right"):
            side_item = pair.get(side_key) or {}
            url = side_item.get("source_url")
            if url:
                featured_urls.add(url)

    left_sorted = sorted(left, key=lambda a: a.published or "", reverse=True)
    right_sorted = sorted(right, key=lambda a: a.published or "", reverse=True)

    items = []
    max_len = max(len(left_sorted), len(right_sorted))
    for i in range(max_len):
        if i < len(left_sorted):
            if left_sorted[i].url not in featured_urls:
                d = _article_to_dict(left_sorted[i])
                d["side"] = "left"
                items.append(d)
        if i < len(right_sorted):
            if right_sorted[i].url not in featured_urls:
                d = _article_to_dict(right_sorted[i])
                d["side"] = "right"
                items.append(d)

    data: dict = {"items": items}
    if date:
        data["date"] = date
    if pairs:
        data["head_to_head"] = pairs
    return data


def _article_to_dict(a: Article) -> dict:
    d = {
        "source": a.source,
        "source_country": a.source_country,
        "source_url": a.url,
        "published": a.published,
        "topic": a.topic or "其他",
        "title_cn": a.title_cn or a.title,
        "summary_cn": a.summary_cn,
        "absurdity": a.absurdity or 5,
    }
    if a.quote_cn:
        d["quote_cn"] = a.quote_cn
    return d


def write_daily_json(data: dict, output_dir: str | Path, date: str | None = None) -> str:
    """写入 output_dir/{date}.json（归档用）或 articles.json（不传 date），返回路径。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"{date}.json" if date else "articles.json"
    path = out / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


def filter_passed(articles: list[Article]) -> list[Article]:
    """筛出通过所有阶段的文章（validate 必须显式通过）。"""
    return [
        a for a in articles
        if a.classify_pass is True and a.validate_pass is True and a.summary_cn
    ]


def deduplicate(articles: list[Article]) -> list[Article]:
    """去重：按 URL 精确去重 + 按标题前缀模糊去重。

    同一事件多源时保留荒诞指数更高者；同分保留先出现的。
    """
    ranked = sorted(
        articles,
        key=lambda a: (a.absurdity or 0, a.published or ""),
        reverse=True,
    )
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Article] = []
    for a in ranked:
        if a.url in seen_urls:
            continue
        title_key = _title_key(a.title_cn or a.title or "")
        if title_key and title_key in seen_titles:
            continue
        seen_urls.add(a.url)
        if title_key:
            seen_titles.add(title_key)
        result.append(a)
    return result


def rank_and_limit(articles: list[Article], max_n: int) -> list[Article]:
    """按荒诞指数降序，截断到每边上限。max_n<=0 表示不截断。"""
    ranked = sorted(articles, key=lambda a: a.absurdity or 0, reverse=True)
    if max_n and max_n > 0:
        return ranked[:max_n]
    return ranked


def _title_key(title: str) -> str:
    """取标题前若干有效字符作模糊键。"""
    cleaned = re.sub(r"\s+", "", title)
    cleaned = "".join(ch for ch in cleaned if ch not in _TITLE_NOISE)
    return cleaned[:10]


def detect_head_to_head(
    left: list[Article],
    right: list[Article],
    *,
    min_absurdity: int = 5,
) -> Optional[dict]:
    """兼容旧接口：返回最高分的一组对擂，或 None。"""
    pairs = detect_head_to_heads(left, right, min_absurdity=min_absurdity, limit=1)
    return pairs[0] if pairs else None


def detect_head_to_heads(
    left: list[Article],
    right: list[Article],
    *,
    min_absurdity: int = 5,
    limit: int = 5,
) -> list[dict]:
    """检测多组同主题今日对擂（默认最多 5 组）。

    同 topic + 双边荒诞指数达标才配对；按得分降序取前 limit 组。
    同一篇文章不会出现在多组对擂中。
    """
    if not left or not right or limit <= 0:
        return []

    candidates: list[tuple[float, Article, Article]] = []
    for l in left:
        for r in right:
            if not l.topic or l.topic != r.topic:
                continue
            la = l.absurdity or 0
            ra = r.absurdity or 0
            if la < min_absurdity or ra < min_absurdity:
                continue
            score = float(la + ra)
            lt = set(l.title_cn or l.title or "") - _TITLE_NOISE
            rt = set(r.title_cn or r.title or "") - _TITLE_NOISE
            overlap = len(lt & rt)
            score += min(overlap, 8) * 0.25
            candidates.append((score, l, r))

    candidates.sort(key=lambda x: x[0], reverse=True)
    used_urls: set[str] = set()
    pairs: list[dict] = []
    for score, l, r in candidates:
        if l.url in used_urls or r.url in used_urls:
            continue
        used_urls.add(l.url)
        used_urls.add(r.url)
        left_dict = _article_to_dict(l)
        left_dict["side"] = "left"
        right_dict = _article_to_dict(r)
        right_dict["side"] = "right"
        pairs.append({
            "left": left_dict,
            "right": right_dict,
            "note": f"今日对擂 · {l.topic}：{l.source} vs {r.source}",
        })
        if len(pairs) >= limit:
            break
    return pairs
