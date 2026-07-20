"""按「栏位 + 标题冒号前骨架」对 articles.json 去重。

story_synth 生成流水线会产出换皮近重复稿：标题冒号前的「议题骨架」相同，
只替换中间一句填充短语。对读者而言就是同一条新闻重复 2-3 遍。

去重键: (side, title_cn 冒号前骨架)
保留策略（每组择优留 1）:
  1. 优先保留标题与 head_to_head 子条目完全一致的那条（避免对擂引用漂移）
  2. 否则保留 summary_cn 最长的一条（信息量最大）
顺序: 维持 items 原始出现顺序（按骨架首次出现的位置）

用法:
    python tools/dedup_articles.py            # dry-run，只打印前后统计
    python tools/dedup_articles.py --write    # 实际写回两个 JSON 文件
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "site" / "public" / "articles.json"
CONTENT = ROOT / "site" / "src" / "content" / "daily" / "articles.json"

COLONS = ("：", ":")


def skeleton(title: str) -> str:
    """标题冒号（全角/半角）前的议题骨架；无冒号则用整条标题。"""
    for sep in COLONS:
        if sep in title:
            return title.split(sep, 1)[0]
    return title


def dedup_key(item: dict) -> tuple[str, str]:
    return (item.get("side", ""), skeleton(item.get("title_cn", "")))


def h2h_titles(data: dict) -> set[str]:
    titles: set[str] = set()
    for grp in data.get("head_to_head", []):
        for side in ("left", "right"):
            sub = grp.get(side)
            if isinstance(sub, dict):
                titles.add(sub.get("title_cn", ""))
    return titles


def deduplicate(items: list[dict], h2h: set[str]) -> tuple[list[dict], int]:
    """返回 (去重后列表, 移除条数)，保持首次出现顺序，组内择优。"""
    best: dict[tuple[str, str], dict] = {}
    for it in items:
        k = dedup_key(it)
        cur = best.get(k)
        if cur is None:
            best[k] = it
            continue
        # 择优：h2h 命中优先；其次摘要更长
        cur_in_h2h = cur.get("title_cn", "") in h2h
        new_in_h2h = it.get("title_cn", "") in h2h
        if new_in_h2h and not cur_in_h2h:
            best[k] = it
        elif cur_in_h2h == new_in_h2h:
            if len(it.get("summary_cn", "")) > len(cur.get("summary_cn", "")):
                best[k] = it
    seen: set[tuple[str, str]] = set()
    kept: list[dict] = []
    for it in items:
        k = dedup_key(it)
        if k in seen:
            continue
        seen.add(k)
        kept.append(best[k])
    return kept, len(items) - len(kept)


def stat(items: list[dict]) -> str:
    topics = Counter(it.get("topic", "未知") for it in items)
    sides = Counter(it.get("side", "未知") for it in items)
    lines = [f"总计 {len(items)} 条 | 方向 {dict(sides)}", "各类型:"]
    for t, c in topics.most_common():
        mark = "OK" if c >= 50 else "不足"
        lines.append(f"  {t}: {c} [{mark}]")
    return "\n".join(lines)


def main() -> int:
    write = "--write" in sys.argv
    src = PUBLIC
    with src.open("r", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    h2h = h2h_titles(data)

    print("=== 去重前 ===")
    print(stat(items))

    kept, removed = deduplicate(items, h2h)
    print(f"\n=== 去重后（移除 {removed} 条近重复）===")
    print(stat(kept))

    if not write:
        print("\n[dry-run] 未写入。加 --write 实际写回两个 JSON 文件。")
        return 0

    data["items"] = kept
    for path in (PUBLIC, CONTENT):
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"已写入: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
