import re
import sys
from pathlib import Path
from html import unescape

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scraper"))
from fetcher import fetch

url = "https://www.dw.com/zh/习近平呼吁中国主导全球ai治理体系-挑战美国领先地位/a-78007555"
html = fetch(url)
Path("dw_sample.html").write_text(html, encoding="utf-8")
print("len", len(html))
for label, pat in [
    ("og:title", r'property="og:title" content="([^"]+)"'),
    ("og:desc", r'property="og:description" content="([^"]*)"'),
    ("richtext p", r'<p[^>]*class="[^"]*richtext[^"]*"[^>]*>(.*?)</p>'),
    ("richtext div", r'<div[^>]*class="[^"]*richtext[^"]*"[^>]*>(.*?)</div>'),
    ("any p long", r"<p[^>]*>([^<]{40,})</p>"),
]:
    ms = re.findall(pat, html, re.I | re.DOTALL)
    print(label, len(ms))
    if ms:
        s = unescape(re.sub(r"<[^>]+>", "", ms[0]))[:160]
        print(" ", s)

# class containing article
classes = sorted(set(re.findall(r'class="([^"]+)"', html)))
for c in classes:
    if any(k in c.lower() for k in ("rich", "article", "body", "text", "content")):
        print("CLS", c)
