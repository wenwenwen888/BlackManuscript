"""看环球时报 world 列表页原始 HTML 内容，判断是不是纯 SPA。"""
import urllib.request
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

req = urllib.request.Request("https://world.huanqiu.com/", headers=HEADERS)
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
print(html)
