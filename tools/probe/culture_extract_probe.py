import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scraper"))
from fetcher import fetch

html = fetch("https://www.guancha.cn/culture")
paths = re.findall(
    r'href="(/(?:culture|internation|politics)/[\d_]+\.shtml)"[^>]*>([^<]{6,80})</a>',
    html,
)
print("guancha culture links", len(paths))
for p, t in list(dict.fromkeys(paths))[:15]:
    print(p, t.strip()[:50])

html2 = fetch("https://ent.huanqiu.com/")
# textarea style like world?
aids = re.findall(r'class="item-aid"[^>]*>([^<]+)', html2)
titles = re.findall(r'class="item-title"[^>]*>([^<]+)', html2)
print("huanqiu ent aids", len(aids), "titles", len(titles))
for a, t in list(zip(aids, titles))[:10]:
    print(a.strip(), t.strip()[:40])
# also regular links
links = re.findall(r'href="(https://[^"]*huanqiu\.com/article/[^"]+)"[^>]*>([^<]{6,60})', html2)
print("huanqiu ent hrefs", len(links))
for u, t in links[:10]:
    print(t.strip()[:40], u[:70])
