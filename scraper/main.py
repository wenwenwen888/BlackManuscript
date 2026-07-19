"""CLI 入口：跑一天的数据。

用法：
  python main.py                                跑今天
  python main.py --date 2026-07-19              跑指定日期
  python main.py --no-llm                       只抓不调 LLM（调试抓取）
  python main.py --sources guancha,huanqiu      限定源
  python main.py --limit 10                     每源最多抓 10 条
  python main.py --sync-site                    把输出拷到 site/src/content/daily/
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 把 scraper 目录加到 path，方便直接 import
sys.path.insert(0, str(Path(__file__).resolve().parent))
# prompts 目录也要加（pipeline.py 里需要）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prompts"))

from config import get_enabled_sources, OUTPUT_DAILY_DIR, OUTPUT_DRAFTS_DIR, SITE_DAILY_DIR
from fetcher import fetch
from sources.base import Source, Article
from utils.json_io import (
    build_daily_dict, write_daily_json, filter_passed, detect_head_to_head,
)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run_pipeline_for_side(
    source: Source,
    side: str,
    limit: int,
    *,
    use_llm: bool = True,
) -> list[Article]:
    """跑一个源的完整流水线，返回通过 LLM 处理的 Article 列表。"""
    if source.side != side:
        return []

    logging.info("[%s] list_articles(limit=%d)", source.name, limit)
    try:
        candidates = source.list_articles(limit=limit)
    except Exception as e:
        logging.error("[%s] list_articles failed: %s", source.name, e)
        return []

    logging.info("[%s] got %d candidates", source.name, len(candidates))

    if not use_llm:
        # 不调 LLM，只做 extract（用于调试抓取层）
        results = []
        for a in candidates:
            try:
                source.extract_article(a)
                results.append(a)
            except Exception as e:
                logging.warning("[%s] extract failed %s: %s", source.name, a.url, e)
        return results

    # 调 LLM pipeline
    from llm.pipeline import process_article
    results = []
    for i, a in enumerate(candidates, 1):
        logging.info("[%s] processing %d/%d: %s", source.name, i, len(candidates), a.title[:50])
        try:
            source.extract_article(a)
        except Exception as e:
            logging.warning("[%s] extract failed %s: %s", source.name, a.url, e)
            continue
        if not a.body:
            logging.info("[%s] skip (empty body): %s", source.name, a.url)
            continue
        try:
            process_article(a)
        except Exception as e:
            logging.error("[%s] pipeline error %s: %s", source.name, a.url, e)
            continue
        if a.summary_cn and a.classify_pass and a.validate_pass is not False:
            results.append(a)
        else:
            logging.info("[%s] rejected: %s -> %s", source.name, a.title[:40], a.reject_reason)

    logging.info("[%s] passed: %d/%d", source.name, len(results), len(candidates))
    return results


def main():
    parser = argparse.ArgumentParser(description="嘲讽日报爬虫")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="日报日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--sources", default=None,
                        help="逗号分隔的源名，默认全部启用")
    parser.add_argument("--limit", type=int, default=15,
                        help="每源最多抓多少条候选，默认 15")
    parser.add_argument("--no-llm", action="store_true",
                        help="只抓不调 LLM（调试抓取层）")
    parser.add_argument("--sync-site", action="store_true",
                        help="把输出拷贝到 site/src/content/daily/")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # 加载源
    source_names = args.sources.split(",") if args.sources else None
    sources = get_enabled_sources(source_names)
    logging.info("启用的源: %s", ", ".join(sources.keys()) or "(无)")

    # 按栏位分组
    left_sources = [s for s in sources.values() if s.side == "left"]
    right_sources = [s for s in sources.values() if s.side == "right"]

    use_llm = not args.no_llm
    if use_llm:
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            logging.error("use_llm=True 但 OPENAI_API_KEY 未设置，请设置或用 --no-llm 调试")
            sys.exit(1)

    left_articles: list[Article] = []
    right_articles: list[Article] = []

    for src in left_sources:
        left_articles.extend(run_pipeline_for_side(src, "left", args.limit, use_llm=use_llm))
    for src in right_sources:
        right_articles.extend(run_pipeline_for_side(src, "right", args.limit, use_llm=use_llm))

    if not use_llm:
        logging.info("--no-llm 模式，跳过 JSON 输出")
        # 打印抓到的列表
        for a in left_articles + right_articles:
            print(f"  [{a.side}] {a.source:<20} {a.published}  body={len(a.body):>5}  {a.title[:60]}")
        return

    # 构建并写入 daily JSON
    # head_to_head 检测
    passed_left = filter_passed(left_articles)
    passed_right = filter_passed(right_articles)
    head_to_head = detect_head_to_head(passed_left, passed_right)

    data = build_daily_dict(args.date, passed_left, passed_right, head_to_head)
    out_path = write_daily_json(data, OUTPUT_DAILY_DIR)
    logging.info("写入 daily JSON: %s (left=%d right=%d)",
                 out_path, len(passed_left), len(passed_right))

    if args.sync_site:
        SITE_DAILY_DIR.mkdir(parents=True, exist_ok=True)
        dest = SITE_DAILY_DIR / Path(out_path).name
        shutil.copy2(out_path, dest)
        logging.info("已同步到 site: %s", dest)


if __name__ == "__main__":
    main()
