"""按改进后的启发式重打主题标签，并同步各份 articles.json。"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scraper"))
from utils.heuristics import guess_topic  # noqa: E402

PATHS = [
    ROOT / "site" / "src" / "content" / "daily" / "articles.json",
    ROOT / "site" / "public" / "articles.json",
    ROOT / "scraper" / "output" / "daily" / "articles.json",
    ROOT / "scraper" / "output" / "daily" / "2026-07-20.json",
]


def main():
    data = json.loads(PATHS[0].read_text(encoding="utf-8"))
    changed = 0
    for item in data["items"]:
        text = " ".join([
            item.get("title_cn") or "",
            item.get("summary_cn") or "",
            item.get("quote_cn") or "",
        ])
        new_topic = guess_topic(text)
        if new_topic != item.get("topic"):
            changed += 1
            item["topic"] = new_topic

    if data.get("head_to_head"):
        for side in ("left", "right"):
            it = data["head_to_head"][side]
            text = " ".join([it.get("title_cn") or "", it.get("summary_cn") or "", it.get("quote_cn") or ""])
            it["topic"] = guess_topic(text)
        topic = data["head_to_head"]["left"].get("topic") or "今日"
        left_s = data["head_to_head"]["left"].get("source")
        right_s = data["head_to_head"]["right"].get("source")
        data["head_to_head"]["note"] = f"今日对擂 · {topic}：{left_s} vs {right_s}"

    text = json.dumps(data, ensure_ascii=False, indent=2)
    for p in PATHS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    c = Counter(i["topic"] for i in data["items"])
    print(f"retagged {changed} items")
    for t in ["股票", "政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"]:
        print(f"  {t}: {c.get(t, 0)}")


if __name__ == "__main__":
    main()
