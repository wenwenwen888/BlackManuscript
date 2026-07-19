"""每日 JSON 读写工具：对接 Astro content collection schema。

输出格式见 site/src/content/config.ts 的 daily schema。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sources.base import Article


def build_daily_dict(date: str, left: list[Article], right: list[Article], head_to_head: dict | None = None) -> dict:
    """把处理后的 Article 列表组装成 daily JSON dict。"""
    return {
        "date": date,
        "left": [_article_to_dict(a) for a in left],
        "right": [_article_to_dict(a) for a in right],
        "head_to_head": head_to_head,
    }


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


def write_daily_json(data: dict, output_dir: str | Path) -> str:
    """写入 output_dir/{date}.json，返回路径。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    date = data["date"]
    path = out / f"{date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(path)


def filter_passed(articles: list[Article]) -> list[Article]:
    """筛出通过所有阶段的文章。"""
    return [a for a in articles if a.classify_pass and a.validate_pass is not False and a.summary_cn]


def detect_head_to_head(left: list[Article], right: list[Article]) -> Optional[dict]:
    """简单检测是否有同一事件被左右栏同时报道。

    当前实现：用 topic+荒诞指数最高的左右各一条做配对。
    后续可升级为语义相似度判断。
    """
    if not left or not right:
        return None
    # 每边按荒诞指数降序取最高
    l = max(left, key=lambda a: a.absurdity)
    r = max(right, key=lambda a: a.absurdity)
    li = left.index(l)
    ri = right.index(r)
    return {
        "left_index": li,
        "right_index": ri,
        "note": f"今日左右栏最辛辣对擂：{l.source} vs {r.source}",
    }
