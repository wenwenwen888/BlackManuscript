import json
from pathlib import Path

d = json.loads(Path("site/src/content/daily/articles.json").read_text(encoding="utf-8"))
lines = []
for i in d["items"]:
    lines.append(f"{i['side']}|{i['source']}|{i['title_cn']}")
Path("titles_check.txt").write_text("\n".join(lines), encoding="utf-8")
c = [i for i in d["items"] if "cgtn" in i["source_url"]]
print("cgtn", len(c))
for i in c:
    print(i["title_cn"][:90])
print("total", len(d["items"]))
