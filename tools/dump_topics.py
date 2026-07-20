import json
from pathlib import Path

d = json.loads(Path("site/src/content/daily/articles.json").read_text(encoding="utf-8"))
lines = [f"{i['topic']}|{i['side']}|{i['title_cn']}" for i in d["items"]]
Path("topic_dump.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok", len(lines))
