import json
from pathlib import Path

d = json.loads(Path("site/src/content/daily/articles.json").read_text(encoding="utf-8"))
hh = d["head_to_head"]
lines = [
    "【今日对擂】" + hh["note"],
    "左：" + hh["left"]["title_cn"],
    "  " + hh["left"]["summary_cn"],
    "  金句：" + str(hh["left"].get("quote_cn")),
    "右：" + hh["right"]["title_cn"],
    "  " + hh["right"]["summary_cn"],
    "  金句：" + str(hh["right"].get("quote_cn")),
    "",
    "【AP/CGTN 条目】",
]
for it in d["items"]:
    if it["source"] in ("Associated Press", "CGTN") or "cgtn" in it["source_url"] or "apnews" in it["source_url"]:
        lines.append(f"- [{it['side']}] {it['title_cn']}")
Path("verify_zh.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok", len(lines))
