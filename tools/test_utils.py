"""核心工具回归测试（不依赖网络 / LLM）。

运行：python tools/test_utils.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "prompts"))

from sources.base import Article  # noqa: E402
from utils.json_io import (  # noqa: E402
    build_daily_dict,
    deduplicate,
    detect_head_to_head,
    filter_passed,
    rank_and_limit,
)
import process as process_prompt  # noqa: E402


def _art(**kwargs) -> Article:
    defaults = dict(
        url="https://example.com/a",
        title="标题",
        source="测试源",
        source_country="cn",
        side="right",
        published="2026-07-19",
        body="x" * 80,
        body_lang="zh",
        title_cn="中文标题",
        summary_cn="摘要",
        topic="政治",
        absurdity=6,
        classify_pass=True,
        validate_pass=True,
    )
    defaults.update(kwargs)
    return Article(**defaults)


class TestTopics(unittest.TestCase):
    def test_topics_include_film_entertainment(self):
        for t in ("股票", "电影", "娱乐", "政治", "其他"):
            self.assertIn(t, process_prompt.ALLOWED_TOPICS)


class TestFilterPassed(unittest.TestCase):
    def test_requires_validate_true(self):
        soft = _art(validate_pass=None, url="https://example.com/1")
        hard_fail = _art(validate_pass=False, url="https://example.com/2")
        ok = _art(validate_pass=True, url="https://example.com/3")
        passed = filter_passed([soft, hard_fail, ok])
        self.assertEqual(len(passed), 1)
        self.assertEqual(passed[0].url, "https://example.com/3")


class TestDeduplicate(unittest.TestCase):
    def test_keeps_higher_absurdity(self):
        # 标题前 12 有效字相同 → 视为同一事件
        low = _art(url="https://a.com/1", title_cn="中国电动车冲击欧洲市场分析报道", absurdity=4)
        high = _art(url="https://b.com/2", title_cn="中国电动车冲击欧洲市场深度评论", absurdity=9)
        out = deduplicate([low, high])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].absurdity, 9)

    def test_url_exact(self):
        a = _art(url="https://same.com/x", title_cn="完全不同标题一", absurdity=3)
        b = _art(url="https://same.com/x", title_cn="完全不同标题二", absurdity=8)
        out = deduplicate([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].absurdity, 8)


class TestRankLimit(unittest.TestCase):
    def test_limit(self):
        arts = [_art(url=f"https://e.com/{i}", title_cn=f"标题{i}", absurdity=i) for i in range(1, 6)]
        out = rank_and_limit(arts, 2)
        self.assertEqual([a.absurdity for a in out], [5, 4])


class TestHeadToHead(unittest.TestCase):
    def test_same_topic_pair(self):
        left = [_art(side="left", source="BBC", source_country="uk",
                     url="https://l.com/1", topic="文化", absurdity=8,
                     title_cn="中国学术造假屡禁不止撤稿潮",
                     summary_cn="外媒追踪中国高校论文造假与学术不端。")]
        right = [_art(side="right", source="观察者网",
                      url="https://r.com/1", topic="文化", absurdity=7,
                      title_cn="西方学术造假与论文工厂更忙",
                      summary_cn="中媒报道欧美撤稿潮与论文工厂产业链。")]
        hh = detect_head_to_head(left, right)
        self.assertIsNotNone(hh)
        self.assertEqual(hh["left"]["source"], "BBC")
        self.assertIn("学术", hh["note"])

    def test_no_force_pair_mismatched_issue(self):
        left = [_art(side="left", url="https://l.com/3", topic="社会", absurdity=9,
                     title_cn="中国校园霸凌处分书很漂亮",
                     summary_cn="外媒关注中国校园欺凌处置。")]
        right = [_art(side="right", url="https://r.com/3", topic="社会", absurdity=9,
                      title_cn="美国枪响成了背景音",
                      summary_cn="中媒评论美国枪击案与控枪立法卡壳。")]
        self.assertIsNone(detect_head_to_head(left, right))

    def test_no_force_pair_different_topic(self):
        left = [_art(side="left", url="https://l.com/2", topic="军事", absurdity=9)]
        right = [_art(side="right", url="https://r.com/2", topic="环境", absurdity=9)]
        self.assertIsNone(detect_head_to_head(left, right))


class TestBuildDaily(unittest.TestCase):
    def test_removes_featured_from_items(self):
        left = [_art(side="left", source="BBC", source_country="uk",
                     url="https://l.com/h", topic="科技", absurdity=8,
                     title_cn="中国AI审查内置进模型",
                     summary_cn="外媒测试中国大模型对齐红线与审查。",
                     mirror_issue="ai_alignment")]
        right = [_art(side="right", url="https://r.com/h", topic="科技", absurdity=8,
                      title_cn="ChatGPT幻觉写进美国新闻稿",
                      summary_cn="中媒评论生成式AI幻觉与媒体甩锅。",
                      mirror_issue="ai_alignment")]
        hh = detect_head_to_head(left, right)
        data = build_daily_dict(left, right, head_to_head=hh)
        self.assertTrue(data.get("head_to_head"))
        urls = {it["source_url"] for it in data["items"]}
        self.assertNotIn("https://l.com/h", urls)
        self.assertNotIn("https://r.com/h", urls)


if __name__ == "__main__":
    unittest.main()
