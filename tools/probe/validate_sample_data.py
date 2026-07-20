"""验证扩展后的示例数据。"""
import json

PATH = r"G:\WorkSpaces\BlackManuscript\site\src\content\daily\2026-07-19.json"
TOPICS = {"政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"}

with open(PATH, encoding="utf-8") as f:
    d = json.load(f)

print(f"date: {d['date']}")
print(f"left: {len(d['left'])} articles")
print(f"right: {len(d['right'])} articles")
print(f"head_to_head: {d['head_to_head']}")
print()
for side in ["left", "right"]:
    print(f"=== {side} ===")
    for i, a in enumerate(d[side]):
        print(f"  [{i}] {a['source']:<28} abs={a['absurdity']} quote={'Y' if a.get('quote_cn') else 'N'}")
        print(f"      title: {a['title_cn']}")
        print(f"      summary ({len(a['summary_cn'])} chars): {a['summary_cn'][:60]}...")
        if a.get("quote_cn"):
            print(f"      quote: {a['quote_cn']}")
        print()

# 校验
errors = []
for side in ["left", "right"]:
    for i, a in enumerate(d[side]):
        if a["topic"] not in TOPICS:
            errors.append(f"{side}[{i}] topic={a['topic']}")
        if not (1 <= a["absurdity"] <= 10):
            errors.append(f"{side}[{i}] absurdity={a['absurdity']}")
        if not a["source_url"].startswith("http"):
            errors.append(f"{side}[{i}] url={a['source_url']}")
        if len(a["summary_cn"]) < 20:
            errors.append(f"{side}[{i}] summary too short")
        for k in ("source", "source_country", "published", "title_cn", "summary_cn"):
            if not a.get(k):
                errors.append(f"{side}[{i}] missing {k}")

if d["head_to_head"]:
    hh = d["head_to_head"]
    if not (0 <= hh["left_index"] < len(d["left"])):
        errors.append("hh.left_index out of range")
    if not (0 <= hh["right_index"] < len(d["right"])):
        errors.append("hh.right_index out of range")

print("=" * 60)
if errors:
    print("FAIL:")
    for e in errors:
        print(f"  {e}")
else:
    print("PASS - 数据符合 schema")
