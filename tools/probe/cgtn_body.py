"""找 CGTN 详情页真实正文容器 class。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

url = "https://news.cgtn.com/news/2026-07-03/China-s-air-conditioners-cool-Europe-s-hotheads-1OtJnEpLK80/p.html"
req = urllib.request.Request(url, headers=HEADERS)
html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="replace")

# 列出所有 class（去重），找正文候选
classes = set()
for m in re.finditer(r'class="([^"]+)"', html):
    for c in m.group(1).split():
        classes.add(c)
print("所有 class 名（去重）:")
for c in sorted(classes):
    if any(k in c.lower() for k in ["content", "body", "text", "article", "main", "detail", "con"]):
        print(" ", c)

# 看 og:description 是否给了摘要
m = re.search(r'property="og:description"\s+content="([^"]+)"', html, re.I)
print("\nog:description:", m.group(1) if m else None)

# 看 article-content 是否有数据
print("\n=== 找正文长文本块（任意 div 含 >500 字纯文本）===")
for m in re.finditer(r'<div[^>]*class="([^"]+)"[^>]*>(.*?)</div>', html, re.DOTALL):
    raw = m.group(2)
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 300:
        print(f"\n[{m.group(1)}] len={len(text)}")
        print(text[:300])
