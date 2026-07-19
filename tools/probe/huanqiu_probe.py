"""探查环球时报国际版列表+正文结构。
环球时报名义上有 world.huanqiu.com 子域，验证是否能拿到列表+正文。
"""
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
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")


print("=== world.huanqiu.com 列表页 ===")
html = fetch("https://world.huanqiu.com/")
print("HTML length:", len(html))

# 提取所有文章链接
links = re.findall(r'href="(https?://[^"]*huanqiu\.com/article/[^"]+)"', html)
links = list(dict.fromkeys(links))
print(f"文章链接数: {len(links)}")
for u in links[:10]:
    print(" ", u)

# 看标题/摘要是否在列表页
titles = re.findall(r'<a[^>]*class="[^"]*"[^>]*href="[^"]*article/[^"]*"[^>]*>([^<]+)</a>', html)
print(f"\n列表页内联标题数: {len(titles)}")
for t in titles[:5]:
    print(" ", t.strip()[:80])

# 试一个详情页
if links:
    print(f"\n=== 详情页: {links[0]} ===")
    detail = fetch(links[0])
    print("详情页长度:", len(detail))
    m = re.search(r"<title>(.*?)</title>", detail)
    print("TITLE:", m.group(1) if m else None)
    # 正文 class 候选
    for cls in ["text", "text-area", "article-content", "content", "main-text", "text_con", "text_con01"]:
        if cls in detail:
            print(f"  class 候选命中: {cls}")
    # 提取正文
    m = re.search(r'class="[^"]*\btext-area\b[^"]*"[^>]*>(.*?)</div>', detail, re.DOTALL)
    if m:
        body = re.sub(r"<[^>]+>", "", m.group(1))
        body = re.sub(r"\s+", " ", body).strip()
        print(f"  正文长度: {len(body)}")
        print(f"  正文开头: {body[:300]}")
