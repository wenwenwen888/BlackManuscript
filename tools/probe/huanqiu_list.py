"""验证从环球时报列表页 SSR textarea 中提取每日文章列表。"""
import urllib.request
import re
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")


html = fetch("https://world.huanqiu.com/")

# 提取每条 item 的 aid + title + type + host
items = re.findall(
    r'<div class="item">\s*'
    r'<textarea class="item-aid">(.*?)</textarea>\s*'
    r'(?:<textarea class="item-addltype">(.*?)</textarea>\s*)?'
    r'(?:<textarea class="item-cover">.*?</textarea>\s*)?'
    r'<textarea class="item-title">(.*?)</textarea>\s*'
    r'(?:<textarea class="item-cnf-host">(.*?)</textarea>\s*)?'
    r'(?:<textarea class="item-time">(.*?)</textarea>\s*)?',
    html, re.DOTALL
)
print(f"列表项总数: {len(items)}")
print(f"{'aid':<14} {'type':<10} {'host':<22} {'time':<14} title")
for aid, atype, title, host, t in items:
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(t)/1000)) if t.strip() else "-"
    title_clean = re.sub(r"\s+", " ", title).strip()[:40]
    print(f"{aid:<14} {atype:<10} {host:<22} {ts:<14} {title_clean}")
