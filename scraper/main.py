"""CLI 入口：跑一天的数据。

用法：
  python main.py --sync-site                    跑今天并同步站点（无 key 时走启发式）
  python main.py --date 2026-07-20              指定日期
  python main.py --no-llm --sync-site           强制启发式（不调 LLM）
  python main.py --fetch-only                   只抓取打印，不写 JSON
  python main.py --health-check                 源健康检查
  python main.py --min-total 50                 总数不足时继续抓候选补足
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prompts"))

from config import get_enabled_sources, OUTPUT_DAILY_DIR, SITE_DAILY_DIR, SITE_DIR
from sources.base import Source, Article
from utils.json_io import (
    build_daily_dict,
    write_daily_json,
    filter_passed,
    deduplicate,
    rank_and_limit,
    detect_head_to_heads,
)
from utils.heuristics import enrich_without_llm, is_fake_url


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
    mode: str = "llm",  # llm | heuristic | fetch_only
) -> list[Article]:
    """跑一个源。mode=llm|heuristic|fetch_only。"""
    if source.side != side:
        return []

    logging.info("[%s] list_articles(limit=%d) mode=%s", source.name, limit, mode)
    try:
        candidates = source.list_articles(limit=limit)
    except Exception as e:
        logging.error("[%s] list_articles failed: %s", source.name, e)
        return []

    logging.info("[%s] got %d candidates", source.name, len(candidates))
    results: list[Article] = []

    for i, a in enumerate(candidates, 1):
        logging.info("[%s] processing %d/%d: %s", source.name, i, len(candidates), (a.title or "")[:50])
        try:
            source.extract_article(a)
        except Exception as e:
            logging.warning("[%s] extract failed %s: %s", source.name, a.url, e)
            continue

        if is_fake_url(a.url):
            logging.info("[%s] skip fake url: %s", source.name, a.url)
            continue
        if not a.body:
            logging.info("[%s] skip empty body: %s", source.name, a.url)
            continue

        if mode == "fetch_only":
            results.append(a)
            continue

        if mode == "llm":
            from llm.pipeline import process_article
            try:
                process_article(a)
            except Exception as e:
                logging.error("[%s] pipeline error %s: %s", source.name, a.url, e)
                continue
            if a.summary_cn and a.classify_pass is True and a.validate_pass is True:
                if is_fake_url(a.url):
                    continue
                results.append(a)
            else:
                logging.info("[%s] rejected: %s -> %s", source.name, (a.title or "")[:40], a.reject_reason)
            continue

        # heuristic
        enriched = enrich_without_llm(a)
        if enriched:
            results.append(enriched)
        else:
            logging.info("[%s] heuristic reject: %s -> %s", source.name, (a.title or "")[:40], a.reject_reason)

    logging.info("[%s] passed: %d/%d", source.name, len(results), len(candidates))
    return results


def sync_to_site(out_path: str | Path) -> None:
    """以 content/daily/articles.json 为唯一数据源，并同步到 public/。"""
    SITE_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    public_dir = SITE_DIR / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    content_target = SITE_DAILY_DIR / "articles.json"
    public_target = public_dir / "articles.json"
    shutil.copy2(out_path, content_target)
    shutil.copy2(content_target, public_target)
    logging.info("已同步到 site: content/daily/articles.json（主）+ public/articles.json（副本）")


def run_health_check(sources: dict[str, Source], sample: int = 3) -> int:
    ok_all = True
    for name, src in sources.items():
        logging.info("=== health: %s (%s) ===", name, src.side)
        try:
            candidates = src.list_articles(limit=sample)
        except Exception as e:
            logging.error("[%s] list_articles 失败: %s", name, e)
            ok_all = False
            continue

        n = len(candidates)
        if n == 0:
            logging.error("[%s] 列表为空（可能改版或被拦）", name)
            ok_all = False
            continue
        logging.info("[%s] 列表 OK: %d 条（取样 %d）", name, n, sample)

        bodies_ok = 0
        for a in candidates[:sample]:
            try:
                src.extract_article(a)
            except Exception as e:
                logging.warning("[%s] extract 失败 %s: %s", name, a.url, e)
                continue
            blen = len(a.body or "")
            if blen >= 50:
                bodies_ok += 1
                logging.info("[%s] body OK (%d chars): %s", name, blen, (a.title or "")[:40])
            else:
                logging.warning("[%s] body 过短 (%d): %s", name, blen, a.url)

        if bodies_ok == 0:
            logging.error("[%s] 取样正文全部失败", name)
            ok_all = False

    if ok_all:
        logging.info("健康检查通过")
        return 0
    logging.error("健康检查未通过，请查看上方日志")
    return 1


def pad_to_minimum(
    sources: dict[str, Source],
    left: list[Article],
    right: list[Article],
    *,
    min_total: int,
    mode: str,
    base_limit: int,
) -> tuple[list[Article], list[Article]]:
    """总数不足时提高每源抓取上限再补一轮。"""
    total = len(left) + len(right)
    if total >= min_total:
        return left, right

    logging.info("总数 %d < 最低 %d，提高 limit 补抓…", total, min_total)
    boost_limit = max(base_limit * 2, 30)
    seen = {a.url for a in left + right}

    for src in sources.values():
        more = run_pipeline_for_side(src, src.side, boost_limit, mode=mode)
        for a in more:
            if a.url in seen:
                continue
            seen.add(a.url)
            if a.side == "left":
                left.append(a)
            else:
                right.append(a)
        if len(left) + len(right) >= min_total:
            break

    logging.info("补抓后: left=%d right=%d total=%d", len(left), len(right), len(left) + len(right))
    return left, right


def main():
    parser = argparse.ArgumentParser(description="嘲讽日报爬虫")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="日报日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--sources", default=None,
                        help="逗号分隔的源名，默认全部启用")
    parser.add_argument("--limit", type=int, default=20,
                        help="每源最多抓多少条候选，默认 20")
    parser.add_argument("--max-per-side", type=int, default=0,
                        help="每边发布上限（按荒诞指数截断），0=不截断")
    parser.add_argument("--min-total", type=int, default=50,
                        help="发布总数下限，不足则补抓，默认 50")
    parser.add_argument("--no-llm", action="store_true",
                        help="强制启发式处理（不调 LLM），仍写 JSON")
    parser.add_argument("--fetch-only", action="store_true",
                        help="只抓取打印，不写 JSON")
    parser.add_argument("--sync-site", action="store_true",
                        help="把输出同步到 site（content 为主，并拷 public）")
    parser.add_argument("--health-check", action="store_true",
                        help="各源列表/正文健康检查后退出")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    source_names = args.sources.split(",") if args.sources else None
    sources = get_enabled_sources(source_names)
    logging.info("启用的源: %s", ", ".join(sources.keys()) or "(无)")

    if args.health_check:
        sys.exit(run_health_check(sources, sample=min(3, args.limit)))

    if args.fetch_only:
        mode = "fetch_only"
    elif args.no_llm or not os.environ.get("OPENAI_API_KEY"):
        mode = "heuristic"
        if not args.no_llm:
            logging.warning("未设置 OPENAI_API_KEY，自动使用启发式模式（--no-llm）")
    else:
        mode = "llm"

    left_sources = [s for s in sources.values() if s.side == "left"]
    right_sources = [s for s in sources.values() if s.side == "right"]

    left_articles: list[Article] = []
    right_articles: list[Article] = []

    for src in left_sources:
        left_articles.extend(run_pipeline_for_side(src, "left", args.limit, mode=mode))
    for src in right_sources:
        right_articles.extend(run_pipeline_for_side(src, "right", args.limit, mode=mode))

    if mode == "fetch_only":
        logging.info("--fetch-only 模式，跳过 JSON 输出")
        for a in left_articles + right_articles:
            print(f"  [{a.side}] {a.source:<20} {a.published}  body={len(a.body):>5}  {(a.title or '')[:60]}")
        return

    left_articles, right_articles = pad_to_minimum(
        sources, left_articles, right_articles,
        min_total=args.min_total, mode=mode, base_limit=args.limit,
    )

    passed_left = filter_passed(left_articles) if mode == "llm" else [
        a for a in left_articles if a.classify_pass and a.summary_cn and not is_fake_url(a.url)
    ]
    passed_right = filter_passed(right_articles) if mode == "llm" else [
        a for a in right_articles if a.classify_pass and a.summary_cn and not is_fake_url(a.url)
    ]

    # 再保险：剔除假链
    passed_left = [a for a in passed_left if not is_fake_url(a.url)]
    passed_right = [a for a in passed_right if not is_fake_url(a.url)]

    passed_left = deduplicate(passed_left)
    passed_right = deduplicate(passed_right)
    passed_left = rank_and_limit(passed_left, args.max_per_side)
    passed_right = rank_and_limit(passed_right, args.max_per_side)

    total = len(passed_left) + len(passed_right)
    logging.info("最终: left=%d right=%d total=%d (min_total=%d)",
                 len(passed_left), len(passed_right), total, args.min_total)
    if total < args.min_total:
        logging.warning("未能补足到 %d 条（真实可抓且通过门控的只有 %d）", args.min_total, total)

    # 缺 published 的填日报日期，便于首页按最新日期排序
    for a in passed_left + passed_right:
        if not a.published:
            a.published = args.date

    head_to_head = detect_head_to_heads(passed_left, passed_right, limit=5)
    if head_to_head:
        logging.info("今日对擂 %d 组: %s", len(head_to_head),
                     " | ".join(p.get("note", "") for p in head_to_head))
    else:
        logging.info("今日无镜像议题对擂（不强凑）")

    data = build_daily_dict(
        passed_left, passed_right,
        head_to_head=head_to_head,
        date=args.date,
    )
    out_path = write_daily_json(data, OUTPUT_DAILY_DIR, date=args.date)
    # 同时写一份 articles.json 便于直接 sync
    articles_path = write_daily_json(data, OUTPUT_DAILY_DIR, date=None)
    logging.info("写入归档: %s ; articles: %s (items=%d, h2h=%d)",
                 out_path, articles_path, len(data["items"]), len(head_to_head))

    if args.sync_site:
        sync_to_site(articles_path)


if __name__ == "__main__":
    main()
