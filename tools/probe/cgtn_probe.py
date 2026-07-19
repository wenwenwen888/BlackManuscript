"""深入验证 3 个右栏补充源的结构。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="replace")


# === CGTN opinions ===
print("=== CGTN opinions 列表 ===")
html = fetch("https://www.cgtn.com/opinions")
# 找文章链接
links = re.findall(r'href="(/opinion/[^"]+)"', html)
links = list(dict.fromkeys(links))
print(f"opinion 链接数: {len(links)}")
for u in links[:8]:
    print(" ", u)

# 找标题（按结构猜）
titles = re.findall(r'<a[^>]+href="/opinion/[^"]+"[^>]*>([^<]{8,120})</a>', html)
print(f"内联标题数: {len(titles)}")
for t in titles[:5]:
    print(" ", t.strip()[:80])
