"""爬虫模块导入与单元测试。"""
import sys
from pathlib import Path

ROOT = Path(r"G:\WorkSpaces\BlackManuscript")
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "prompts"))

from llm.client import LLMClient, LLMError, get_client, _parse_json_response
from llm.pipeline import process_article
from llm.safety import hit_blacklist, save_to_drafts
from utils.json_io import build_daily_dict, write_daily_json, filter_passed, detect_head_to_head
from sources.base import Source, Article
from sources.guancha import GuanchaSource
from sources.huanqiu import HuanqiuSource
from sources.cgtn import CgtnSource
from config import get_all_sources, get_enabled_sources

print("All imports OK")
print("Registered sources:", list(get_all_sources().keys()))
print("Default enabled:", list(get_enabled_sources().keys()))

# 测试 _parse_json_response 容错
test_cases = [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Here is the result:\n{"a": 1}\nDone.',
    '{"a": 1, "b": "中文测试"}',
]
print("\n=== _parse_json_response 容错测试 ===")
for t in test_cases:
    try:
        result = _parse_json_response(t)
        print(f"  OK: {result}")
    except Exception as e:
        print(f"  FAIL: {e} (input={t[:30]})")

# 测试 Article 数据类
print("\n=== Article 数据类 ===")
a = Article(
    url="https://example.com/x",
    title="测试标题",
    source="测试源",
    source_country="cn",
    side="right",
    published="2026-07-19",
    body="测试正文",
    body_lang="zh",
)
print(f"  Article: {a.title} / side={a.side} / country={a.source_country}")

# 测试 safety 黑名单
print("\n=== safety 黑名单 ===")
import os
os.environ["BLACKLIST_KEYWORDS"] = "测试关键词,习近平"
print(f"  blacklist: {hit_blacklist('这文章里有测试关键词')} ")  # 应返回"测试关键词"
print(f"  blacklist: {hit_blacklist('没有命中')}")  # 应返回 None

# 测试 json_io
print("\n=== json_io ===")
a.summary_cn = "测试摘要"
a.topic = "政治"
a.absurdity = 7
a.quote_cn = "测试金句"
a.title_cn = "测试中文标题"
a.classify_pass = True
a.validate_pass = True

left = []
right = [a]
data = build_daily_dict("2026-07-19", left, right, None)
print(f"  daily dict: date={data['date']}, left={len(data['left'])}, right={len(data['right'])}")
print(f"  right[0]: {data['right'][0]['title_cn']}")

hh = detect_head_to_head(left, right)
print(f"  head_to_head (空左): {hh}")

passed = filter_passed(right)
print(f"  passed: {len(passed)}")

# 测试 source 实例化
print("\n=== Source 实例化 ===")
for name, src in get_all_sources().items():
    print(f"  {name}: {src.name} / side={src.side} / country={src.source_country}")

print("\n=== ALL TESTS PASSED ===")
