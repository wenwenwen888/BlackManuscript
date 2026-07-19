"""验证 CGTN 文章详情页正文 + 新华网国际列表结构。"""
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


# === CGTN 文章详情 ===
print("=== CGTN 文章详情 ===")
url = "https://news.cgtn.com/news/2026-07-03/China-s-air-conditioners-cool-Europe-s-hotheads-1OtJnEpLK80/p.html"
html = fetch(url)
print("长度:", len(html))

m = re.search(r"<title>(.*?)</title>", html)
print("TITLE:", m.group(1) if m else None)

# 元数据
for pat in [r'property="og:title"\s+content="([^"]+)"',
            r'property="og:description"\s+content="([^"]+)"',
            r'name="source"\s+content="([^"]+)"',
            r'name="publishdate"\s+content="([^"]+)"',
            r'name="pubdate"\s+content="([^"]+)"']:
    m = re.search(pat, html, re.I)
    if m:
        print("META:", m.group(1)[:120])

# 正文 class
print("\n正文 class 候选：")
for cls in ["CG-analyse-con", "text-con", "article-body", "news-body", "content",
            "main-text", "news_content", "text", "detail-content"]:
    if re.search(rf'class="[^"]*\b{cls}\b', html):
        print(f"  {cls}: 命中")

m = re.search(r'class="[^"]*CG-analyse-con[^"]*"[^>]*>(.*?)</div>\s*<div', html, re.DOTALL)
if m:
    text = re.sub(r"<[^>]+>", "", m.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    print(f"\n正文长度: {len(text)}")
    print(f"开头: {text[:400]}")
else:
    # 备选
    m = re.search(r'<div class="[^"]*\btext\b[^"]*"[^>]*>(.*?)</div>\s*<div', html, re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        print(f"\n备选正文: {len(text)} chars")
        print(text[:400])


# === 新华网国际列表 ===
print("\n\n=== 新华网国际 列表 ===")
html = fetch("http://www.xinhuanet.com/world/")
print("长度:", len(html))
links = re.findall(r'href="(http://www\.xinhuanet\.com/world/[^"]+\.(?:htm|html)|/world/\d{4}-\d{2}/\d{2}/c_\d+\.htm)"', html)
links = list(dict.fromkeys(links))
print(f"国际链接数: {len(links)}")
for u in links[:8]:
    print(" ", u)
