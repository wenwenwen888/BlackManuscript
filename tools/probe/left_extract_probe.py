"""继续探查 BBC / DW / AP 正文提取。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scraper"))
from fetcher import fetch  # noqa: E402


def main():
    html = fetch("https://www.bbc.com/zhongwen/simp")
    print("bbc len", len(html))
    allh = re.findall(r"https?://[^\"']+zhongwen[^\"']+", html)
    print("zhongwen urls", len(allh))
    for u in list(dict.fromkeys(allh))[:20]:
        print(" ", u[:120])
    aids = re.findall(r"/articles/[a-z0-9]+", html)
    print("articles", len(set(aids)))
    for a in list(dict.fromkeys(aids))[:15]:
        print(" ", a)

    html2 = fetch("https://www.dw.com/zh/")
    arts = re.findall(r'href="(/zh/[^"]+/a-\d+)"', html2)
    uniq = list(dict.fromkeys(arts))
    print("dw arts", len(uniq))
    for a in uniq[:8]:
        print(" ", a)
    if uniq:
        url = "https://www.dw.com" + uniq[0]
        h = fetch(url)
        title = re.search(r'property="og:title" content="([^"]+)"', h)
        desc = re.search(r'property="og:description" content="([^"]*)"', h)
        print("DW sample", url)
        print(" title", title.group(1) if title else None)
        print(" desc", (desc.group(1)[:150] if desc else None))

    ap_url = (
        "https://apnews.com/article/"
        "china-ma-xingrui-politburo-xinjiang-corruption-95e5dba322ddc5bb6f2ee661ac3c2bff"
    )
    h = fetch(ap_url)
    title = re.search(r'property="og:title" content="([^"]+)"', h)
    desc = re.search(r'property="og:description" content="([^"]*)"', h)
    print("AP sample title", title.group(1) if title else None)
    print("AP desc", (desc.group(1)[:200] if desc else None))
    # 正文块
    body_m = re.search(
        r'<div[^>]+data-key="article"[^>]*>(.*?)</div>\s*<div[^>]+class="[^"]*Page-actions',
        h,
        re.DOTALL,
    )
    if not body_m:
        body_m = re.search(r'class="RichTextStoryBody[^"]*"[^>]*>(.*?)</div>', h, re.DOTALL)
    if body_m:
        text = re.sub(r"<[^>]+>", "", body_m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        print("AP body chars", len(text), text[:160])
    else:
        print("AP body not found; snip classes:")
        for m in re.findall(r'class="([^"]{0,80})"', h)[:30]:
            if "Rich" in m or "Story" in m or "Article" in m:
                print(" ", m)


if __name__ == "__main__":
    main()
