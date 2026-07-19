"""CGTN dump 所有 href 样本，看是否有静态可解析链接。"""
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

hrefs = re.findall(r'href="([^"]+)"', html)
# 过滤
samples = [h for h in hrefs if "/opinion" in h or "/news" in h or "/article" in h or "/show" in h]
print(f"含文章特征的 href: {len(samples)}")
for h in samples[:30]:
    print(" ", h)
