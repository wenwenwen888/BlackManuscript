"""探查文化/娱乐/电影相关列表页是否可抓。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scraper"))
from fetcher import fetch

CANDIDATES = [
    ("guancha_culture", "https://www.guancha.cn/culture"),
    ("guancha_internation", "https://www.guancha.cn/internation"),
    ("huanqiu_ent", "https://ent.huanqiu.com/"),
    ("huanqiu_world", "https://world.huanqiu.com/"),
    ("bbc_culture", "https://www.bbc.com/zhongwen/simp/topics/c1ezl7w9z1zt"),  # may 404
    ("bbc_home", "https://www.bbc.com/zhongwen/simp"),
    ("dw_culture", "https://www.dw.com/zh/文化与生活/s-12324"),
]


def main():
    for name, url in CANDIDATES:
        try:
            html = fetch(url, timeout=12, retries=2)
        except Exception as e:
            print(f"FAIL {name}: {e}")
            continue
        film = len(re.findall(r"电影|票房|好莱坞|院线|film|movie|奥斯卡", html, re.I))
        ent = len(re.findall(r"娱乐|明星|综艺|世界杯|足球", html))
        cult = len(re.findall(r"文化|审查|禁书|出版", html))
        print(f"OK {name} len={len(html)} film~{film} ent~{ent} cult~{cult}")


if __name__ == "__main__":
    main()
