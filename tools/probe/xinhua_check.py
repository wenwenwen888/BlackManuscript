"""确认新华网国际是否纯 SPA，有没有 SSR 数据。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

req = urllib.request.Request("http://www.xinhuanet.com/world/", headers=HEADERS)
html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="replace")

# 找所有 href 看链接形式
hrefs = re.findall(r'href="([^"]+)"', html)
print(f"总 href: {len(hrefs)}")

# 看有没有 c_ 这种新华网文章典型 URL（常出现在静态嵌入里）
c_links = [h for h in hrefs if "c_" in h or "/c_" in h]
print(f"c_ 文章链接: {len(c_links)}")
for u in c_links[:10]:
    print(" ", u)

# 找 data-src 或 JSON 注入迹象
print("\n=== SSR 数据迹象 ===")
for kw in ["data-src", "data-url", "window.__", "__INITIAL__", "dataList", "newsList", "listData"]:
    n = html.count(kw)
    if n:
        print(f"  {kw}: {n}")

# 取一段含 "c_" 周围看
i = html.find("c_")
if i > 0:
    print("\n=== c_ 周围 500 字 ===")
    print(html[max(0, i-200):i+500])
