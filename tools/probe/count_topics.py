"""统计当前各类型数量，计算需要补充多少。"""
import json
from collections import Counter

PATH = r"G:\WorkSpaces\BlackManuscript\site\src\content\daily\articles.json"
d = json.load(open(PATH, encoding="utf-8"))
c = Counter(it["topic"] for it in d["items"])

print(f"{'topic':<8} {'now':>4} {'need':>5}")
print("-" * 20)
total_need = 0
# 与 prompts/process.py 对齐
TOPICS = ["股票", "政治", "经济", "社会", "科技", "军事", "外交", "文化", "环境", "电影", "娱乐", "其他"]
for t in TOPICS:
    n = c.get(t, 0)
    need = max(0, 50 - n)
    total_need += need
    print(f"{t:<8} {n:>4} {need:>5}")
print("-" * 20)
print(f"total now: {sum(c.values())}, need to add: {total_need}")
