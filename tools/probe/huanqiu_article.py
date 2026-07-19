"""验证环球时报文章详情页结构，提取正文+元数据。"""
import urllib.request
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

URL = "https://world.huanqiu.com/article/4SRRiSqejA5"
req = urllib.request.Request(URL, headers=HEADERS)
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

print("HTML 长度:", len(html))

m = re.search(r"<title>(.*?)</title>", html)
print("TITLE:", m.group(1) if m else None)

# 元数据
print("\n=== METADATA ===")
for pat in [r"来源[:：]\s*([^\s<]+)", r"\d{4}-\d{2}-\d{2}[\s\d:]*", r"作者[:：]\s*([^\s<]+)"]:
    for m in re.finditer(pat, html):
        print(" ", m.group(0).strip())

# 正文 class 候选探测
print("\n=== 正文 class 命中 ===")
for cls in ["text", "text-area", "article-content", "content", "main-text",
            "text_con", "text_con01", "la_main_left", "text_content"]:
    if f'"{cls}"' in html or f"'{cls}'" in html or f'class="{cls} ' in html or f'class="{cls}"' in html:
        print(f"  {cls}: 命中")

# 看 textarea 注入的正文（环球时报常用模式）
print("\n=== textarea 内容（SSR 注水）===")
textareas = re.findall(r'<textarea[^>]*class="([^"]+)"[^>]*>(.*?)</textarea>', html, re.DOTALL)
print(f"textarea 总数: {len(textareas)}")
for cls, content in textareas[:15]:
    text = re.sub(r"\s+", " ", content).strip()
    if len(text) > 5:
        print(f"  [{cls}]: {text[:150]}")
