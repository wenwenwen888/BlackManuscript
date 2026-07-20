"""补抓文化/文娱栏目，把电影/娱乐/文化/环境类文章并入今日数据。"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "prompts"))

from config import get_enabled_sources  # noqa: E402
from utils.heuristics import enrich_without_llm, is_fake_url  # noqa: E402
from utils.json_io import (  # noqa: E402
    build_daily_dict,
    deduplicate,
    detect_head_to_head,
    write_daily_json,
)
from sources.base import Article  # noqa: E402

CONTENT = ROOT / "site" / "src" / "content" / "daily" / "articles.json"
PUBLIC = ROOT / "site" / "public" / "articles.json"
SOFT_TOPICS = {"电影", "娱乐", "文化", "环境"}


def article_from_item(it: dict) -> Article:
    return Article(
        url=it["source_url"],
        title=it.get("title_cn") or "",
        source=it.get("source") or "",
        source_country=it.get("source_country") or "",
        side=it["side"],
        published=it.get("published") or "",
        title_cn=it.get("title_cn") or "",
        summary_cn=it.get("summary_cn") or "",
        topic=it.get("topic") or "其他",
        absurdity=int(it.get("absurdity") or 5),
        quote_cn=it.get("quote_cn") or "",
        classify_pass=True,
        validate_pass=True,
        body="x" * 80,
        body_lang="zh",
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    date = datetime.now().strftime("%Y-%m-%d")
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    existing = [article_from_item(i) for i in data["items"]]
    seen = {a.url for a in existing}

    sources = get_enabled_sources(["guancha", "huanqiu"])
    new_arts: list[Article] = []
    for name, src in sources.items():
        logging.info("补抓 %s", name)
        try:
            cands = src.list_articles(limit=28)
        except Exception as e:
            logging.error("list fail %s: %s", name, e)
            continue
        for a in cands:
            if a.url in seen:
                continue
            try:
                src.extract_article(a)
            except Exception as e:
                logging.warning("extract fail %s: %s", a.url, e)
                continue
            if is_fake_url(a.url) or len(a.body or "") < 50:
                continue
            enriched = enrich_without_llm(a)
            if not enriched:
                continue
            # 只要软主题，或标题明显影娱
            text = (a.title_cn or a.title or "") + (a.summary_cn or "")
            if a.topic not in SOFT_TOPICS and not any(
                k in text for k in ("电影", "票房", "好莱坞", "院线", "综艺", "明星", "世界杯", "热浪", "气候")
            ):
                continue
            if not a.published:
                a.published = date
            new_arts.append(a)
            seen.add(a.url)
            logging.info("  + [%s] %s | %s", a.topic, a.source, (a.title_cn or "")[:40])

    logging.info("新增软主题候选 %d", len(new_arts))
    all_arts = existing + new_arts
    all_arts = deduplicate(all_arts)
    left = [a for a in all_arts if a.side == "left"]
    right = [a for a in all_arts if a.side == "right"]
    hh = detect_head_to_head(left, right)
    out = build_daily_dict(left, right, head_to_head=hh, date=date)

    text = json.dumps(out, ensure_ascii=False, indent=2)
    for p in (CONTENT, PUBLIC,
              ROOT / "scraper" / "output" / "daily" / "articles.json",
              ROOT / "scraper" / "output" / "daily" / f"{date}.json"):
        p.write_text(text, encoding="utf-8")

    c = Counter(i["topic"] for i in out["items"])
    print("total", len(out["items"]))
    for t in ["政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"]:
        print(f"  {t}: {c.get(t, 0)}")


if __name__ == "__main__":
    main()
