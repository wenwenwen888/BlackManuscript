"""探查单个观察者网文章页结构，验证正文+元数据可提取性。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

URL = "https://www.guancha.cn/internation/2026_07_19_824295.shtml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

req = urllib.request.Request(URL, headers=HEADERS)
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

print("=== TITLE ===")
m = re.search(r"<title>(.*?)</title>", html)
print(m.group(1) if m else None)

print("\n=== METADATA ===")
for pat in [r"来源[:：]\s*([^\s<]+)", r"\d{4}-\d{2}-\d{2}", r"\d{4}年\d{1,2}月\d{1,2}日", r"作者[:：]\s*([^\s<]+)"]:
    for m in re.finditer(pat, html):
        print(" ", m.group(0))

print("\n=== all-txt content block ===")
m = re.search(r'class="[^"]*\ball-txt\b[^"]*"[^>]*>(.*?)</div>\s*<div\s+class="content-bottom-ad', html, re.DOTALL)
if not m:
    m = re.search(r'class="[^"]*\ball-txt\b[^"]*"[^>]*>(.*)', html, re.DOTALL)
    if m:
        raw = m.group(1)
        end = raw.find('</div>')
        raw = raw[:end] if end > 0 else raw[:5000]
    else:
        raw = None
else:
    raw = m.group(1)
if raw:
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    print(f"LENGTH: {len(text)} chars")
    print(f"FIRST 800: {text[:800]}")
    print(f"LAST 400: {text[-400:]}")
else:
    print("all-txt block NOT FOUND, dump all class names")
    for c in re.findall(r'class="([^"]+)"', html):
        print(" ", c)