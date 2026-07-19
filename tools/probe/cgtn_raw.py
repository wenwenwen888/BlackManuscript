"""CGTN opinions 没拿到链接，dump 页面看真实结构。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

req = urllib.request.Request("https://www.cgtn.com/opinions", headers=HEADERS)
html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="replace")

# 看所有 ahref 域
hrefs = re.findall(r'href="([^"]+)"', html)
print("总 href 数:", len(hrefs))
# 含 /opinion 或 article 或 news 的
import collections
counter = collections.Counter()
for h in hrefs:
    if h.startswith("/") and not h.startswith("//"):
        # 取 path 前两段
        parts = h.strip("/").split("/")
        key = "/" + "/".join(parts[:2]) if len(parts) >= 2 else h
        counter[key] += 1
print("路径前缀 top 20:")
for k, v in counter.most_common(20):
    print(f"  {v:4}  {k}")
