"""探查右栏补充源：参考消息、CGTN、新华网国际、中国日报、人民日报海外版。
判断每个源是否能直接 HTTP + 正则抓，是否需要 headless。
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

SOURCES = [
    ("参考消息", "https://china.chinadaily.com.cn/"),
    ("参考消息-备用", "http://world.people.com.cn/"),
    ("CGTN", "https://www.cgtn.com/"),
    ("CGTN-opinion", "https://www.cgtn.com/opinions"),
    ("新华网-国际", "http://www.xinhuanet.com/world/"),
    ("中国日报-世界", "https://www.chinadaily.com.cn/world"),
    ("人民日报海外版", "http://paper.people.com.cn/rmrbhwb/"),
    ("中国新闻网-国际", "https://www.chinanews.com.cn/gj/"),
    ("国际在线", "http://gb.cri.cn/"),
    ("求是网-国际", "http://www.qstheory.cn/international/"),
]

for name, url in SOURCES:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        r = urllib.request.urlopen(req, timeout=12)
        html = r.read().decode("utf-8", errors="replace")
        # 计数关键标识
        n_links = len(re.findall(r'href="[^"]+\.(?:shtml|html|htm)"', html))
        n_textarea = len(re.findall(r"<textarea", html))
        n_article = len(re.findall(r"article", html, re.I))
        # 找一个 ahref 样本
        sample = re.findall(r'href="([^"]*(?:world|international|intl|guoji|gj)[^"]*\.(?:shtml|html))"', html, re.I)
        print(f"[OK] {name:<18} {r.status} {len(html):>7}B links={n_links:<4} textarea={n_textarea:<3} article={n_article:<4} sample={len(sample)}")
    except Exception as e:
        print(f"[ERR] {name:<18} {e}")
