"""探查左栏外媒列表结构（BBC / DW / AP）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRAPER = Path(__file__).resolve().parents[2] / "scraper"
sys.path.insert(0, str(SCRAPER))
import fetcher  # noqa: E402
fetch = fetcher.fetch


def probe_bbc():
    print("==== BBC ====")
    html = fetch("https://www.bbc.com/zhongwen/simp")
    paths = list(dict.fromkeys(re.findall(r'href="(/zhongwen/simp/[^"#?]+)"', html)))
    print("path links", len(paths))
    for p in paths[:25]:
        print(" ", p)
    # 试抓一篇正文
    for p in paths:
        if "/articles/" in p or re.search(r"/\d{8}$", p) or "china" in p.lower():
            url = "https://www.bbc.com" + p
            try:
                body_html = fetch(url)
            except Exception as e:
                print(" extract fail", url, e)
                continue
            title = re.search(r"<title>([^<]+)</title>", body_html)
            og = re.search(r'property="og:description" content="([^"]*)"', body_html)
            print(" SAMPLE", url)
            print("  title:", title.group(1)[:80] if title else None)
            print("  og:", (og.group(1)[:120] if og else None))
            break


def probe_dw():
    print("==== DW ====")
    html = fetch("https://www.dw.com/zh/")
    paths = list(dict.fromkeys(re.findall(r'href="(/zh/[^"#?]{10,})"', html)))
    print("path links", len(paths))
    for p in paths[:25]:
        print(" ", p[:100])


def probe_ap():
    print("==== AP China ====")
    try:
        html = fetch("https://apnews.com/hub/china")
    except Exception as e:
        print("fail", e)
        return
    links = list(dict.fromkeys(re.findall(r'href="(https://apnews.com/article/[^"#?]+)"', html)))
    print("article links", len(links))
    for u in links[:12]:
        print(" ", u)


if __name__ == "__main__":
    probe_bbc()
    probe_dw()
    probe_ap()
